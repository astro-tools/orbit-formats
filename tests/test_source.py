"""Resolving paths and buffers into a uniform :class:`Source`."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from orbit_formats import Source
from orbit_formats.source import load_source


def test_bytes_source_is_taken_directly() -> None:
    src = load_source(b"hello")
    assert src.read_bytes() == b"hello"
    assert src.read_text() == "hello"
    assert src.path is None
    assert src.name is None
    assert src.suffix is None


def test_bytearray_source_is_accepted() -> None:
    assert load_source(bytearray(b"abc")).read_bytes() == b"abc"


def test_path_source_reads_the_file(tmp_path: Path) -> None:
    target = tmp_path / "orbit.oem"
    target.write_bytes(b"CCSDS_OEM_VERS = 2.0\n")
    src = load_source(target)
    assert src.read_bytes() == b"CCSDS_OEM_VERS = 2.0\n"
    assert src.path == target
    assert src.name == "orbit.oem"
    assert src.suffix == ".oem"


def test_str_source_is_treated_as_a_path(tmp_path: Path) -> None:
    target = tmp_path / "data.sp3"
    target.write_text("#c\n")
    src = load_source(str(target))
    assert src.read_text() == "#c\n"
    assert src.suffix == ".sp3"


def test_binary_buffer_source_keeps_its_name() -> None:
    buffer = io.BytesIO(b"DAF/SPK ")
    buffer.name = "kernel.bsp"
    src = load_source(buffer)
    assert src.read_bytes() == b"DAF/SPK "
    assert src.name == "kernel.bsp"
    assert src.suffix == ".bsp"


def test_text_buffer_source_is_encoded() -> None:
    src = load_source(io.StringIO("stk.v.11.0\n"))
    assert src.read_bytes() == b"stk.v.11.0\n"
    assert src.name is None


def test_limit_truncates_the_loaded_prefix(tmp_path: Path) -> None:
    target = tmp_path / "big.tle"
    target.write_bytes(b"0123456789")
    assert load_source(target, limit=4).read_bytes() == b"0123"
    assert load_source(b"0123456789", limit=4).read_bytes() == b"0123"


def test_suffix_falls_back_to_name_when_no_path() -> None:
    assert Source(data=b"", name="thing.report").suffix == ".report"
    assert Source(data=b"", name="noextension").suffix is None


def test_unsupported_source_type_is_rejected() -> None:
    with pytest.raises(TypeError, match="unsupported source type"):
        load_source(object())  # type: ignore[arg-type]
