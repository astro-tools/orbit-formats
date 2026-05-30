"""The read / write / convert public surface and its dispatch to the registry."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from orbit_formats import (
    Canonical,
    Ephemeris,
    MeanElementSet,
    Metadata,
    Source,
    UnknownFormatError,
    UnsupportedConversionError,
    UnsupportedFormatError,
    convert,
    read,
    register_reader,
    register_writer,
    write,
)
from orbit_formats import registry as registry_module

TLE = (
    b"ISS (ZARYA)\n"
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)
OEM_KVN = b"CCSDS_OEM_VERS = 2.0\nCREATION_DATE = 2024-08-17T00:00:00\n"


@pytest.fixture
def isolated_registry() -> Iterator[None]:
    """Snapshot and restore the global reader/writer registry around a test."""
    readers = dict(registry_module._READERS)
    writers = dict(registry_module._WRITERS)
    loaded = registry_module._plugins_loaded
    try:
        yield
    finally:
        registry_module._READERS.clear()
        registry_module._READERS.update(readers)
        registry_module._WRITERS.clear()
        registry_module._WRITERS.update(writers)
        registry_module._plugins_loaded = loaded


def _ephemeris() -> Ephemeris:
    return Ephemeris(
        metadata=Metadata(
            object_name="SAT", reference_frame="TEME", central_body="Earth", time_scale="UTC"
        ),
        epochs=np.array(["2024-08-17T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )


def _mean_set() -> MeanElementSet:
    return MeanElementSet(
        metadata=Metadata(time_scale="UTC"),
        epoch=np.datetime64("2024-08-17T00:00:00", "ns"),
        mean_motion=15.7,
        eccentricity=0.0006,
        inclination=51.6,
        raan=247.5,
        arg_periapsis=130.5,
        mean_anomaly=325.0,
    )


# --- read ------------------------------------------------------------------------------


def test_read_without_a_registered_reader_is_unsupported(isolated_registry: None) -> None:
    with pytest.raises(UnsupportedFormatError, match="no reader is registered for format 'tle'"):
        read(TLE)


def test_read_dispatches_to_the_registered_reader(isolated_registry: None) -> None:
    captured: dict[str, Any] = {}
    expected = _mean_set()

    def fake_reader(src: Source) -> Canonical:
        captured["data"] = src.read_bytes()
        return expected

    register_reader("tle", fake_reader)
    result = read(TLE)
    assert result is expected
    assert captured["data"] == TLE


def test_read_explicit_format_overrides_detection(isolated_registry: None) -> None:
    seen: dict[str, str] = {}

    def fake_reader(src: Source) -> Canonical:
        seen["format"] = "tle"
        return _mean_set()

    register_reader("tle", fake_reader)
    # OEM content, but the caller forces the TLE reader.
    read(OEM_KVN, format="tle")
    assert seen["format"] == "tle"


# --- write -----------------------------------------------------------------------------


def test_write_without_a_registered_writer_is_unsupported(
    isolated_registry: None, tmp_path: Path
) -> None:
    with pytest.raises(UnsupportedFormatError, match="no writer is registered"):
        write(_ephemeris(), tmp_path / "out.oem")


def test_write_to_a_read_only_format_is_rejected(isolated_registry: None, tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFormatError, match="read-only"):
        write(_ephemeris(), tmp_path / "out.nav", format="rinex-nav")


def test_write_dispatches_and_serialises_to_the_destination(
    isolated_registry: None, tmp_path: Path
) -> None:
    def fake_writer(obj: Canonical) -> bytes:
        assert isinstance(obj, Ephemeris)
        return b"OEM-PAYLOAD"

    register_writer("ccsds-oem", fake_writer)
    destination = tmp_path / "out.oem"  # format inferred from the extension
    write(_ephemeris(), destination)
    assert destination.read_bytes() == b"OEM-PAYLOAD"


def test_write_with_an_unknown_explicit_format_is_rejected(
    isolated_registry: None, tmp_path: Path
) -> None:
    with pytest.raises(UnknownFormatError, match="unknown format 'bogus'"):
        write(_ephemeris(), tmp_path / "out.bin", format="bogus")


def test_write_requires_an_inferable_format(isolated_registry: None, tmp_path: Path) -> None:
    with pytest.raises(UnknownFormatError, match="could not infer the target format"):
        write(_ephemeris(), tmp_path / "out.unknownext")


# --- convert ---------------------------------------------------------------------------


def test_convert_to_the_same_form_returns_the_same_object() -> None:
    ephemeris = _ephemeris()
    # ccsds-oem prefers an ephemeris, and the object already is one.
    assert convert(ephemeris, to="ccsds-oem") is ephemeris


def test_convert_across_forms_without_a_path_is_unsupported() -> None:
    with pytest.raises(UnsupportedConversionError) as excinfo:
        convert(_mean_set(), to="ccsds-oem")  # mean-elements -> ephemeris
    assert excinfo.value.source_form == "mean-elements"
    assert excinfo.value.target_format == "ccsds-oem"


def test_convert_with_an_unknown_target_is_rejected() -> None:
    with pytest.raises(UnknownFormatError, match="unknown format 'bogus'"):
        convert(_ephemeris(), to="bogus")


def test_convert_reads_a_path_before_converting(isolated_registry: None) -> None:
    ephemeris = _ephemeris()
    register_reader("ccsds-oem", lambda src: ephemeris)
    assert convert(OEM_KVN, to="ccsds-oem") is ephemeris


def test_convert_rejects_an_unmapped_canonical_type() -> None:
    @dataclass(kw_only=True, eq=False)
    class Mystery(Canonical):
        def _eq_payload(self) -> tuple[Any, ...]:
            return ()

    with pytest.raises(UnsupportedConversionError):
        convert(Mystery(metadata=Metadata()), to="ccsds-oem")


# --- registry --------------------------------------------------------------------------


def test_register_reader_rejects_an_unknown_format(isolated_registry: None) -> None:
    with pytest.raises(UnknownFormatError):
        register_reader("bogus", lambda src: _ephemeris())


def test_register_writer_rejects_an_unknown_format(isolated_registry: None) -> None:
    with pytest.raises(UnknownFormatError):
        register_writer("bogus", lambda obj: b"")


def test_register_writer_rejects_a_read_only_format(isolated_registry: None) -> None:
    with pytest.raises(UnsupportedFormatError, match="read-only"):
        register_writer("rinex-nav", lambda obj: b"")
