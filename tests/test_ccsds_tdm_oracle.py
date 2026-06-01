"""Cross-validate the TDM writer's output against the dev-only ccsds-ndm oracle.

ccsds-ndm is GPL-3.0 and is never a runtime/dev dependency, never imported by the package,
and never distributed; it is installed transiently in one CI job and pulled in here only
behind :func:`pytest.importorskip`. The check is independence: the writer emits a TDM (KVN and
XML), a separate CCSDS implementation parses it, and we assert it reads back the same number of
segments, the same participants, and a range observation the golden carries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("ccsds_ndm")

from ccsds_ndm.ndm_io import NdmIo

from orbit_formats import Tracking, read
from orbit_formats.writers.tdm import write_tdm

GOLDEN = Path(__file__).parent / "data" / "tdm" / "golden_tdm.tdm"


def _attr(obj: Any, *names: str) -> Any:
    """The first present attribute among ``names`` (snake_case / camelCase oracle shapes)."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    raise AttributeError(f"none of {names} on {type(obj).__name__}")


def _value(obj: Any) -> float:
    """A scalar value, unwrapping a typed value+units element if necessary."""
    return float(getattr(obj, "value", obj))


def _range_values(observations: Any) -> list[float]:
    """Every RANGE reading among a segment's observations, value-unwrapped."""
    values: list[float] = []
    for observation in observations:
        raw = getattr(observation, "range", None)
        if raw is not None:
            values.append(_value(raw))
    return values


def _assert_oracle_matches(tdm_bytes: bytes) -> None:
    parsed = NdmIo().from_string(tdm_bytes.decode("utf-8"))
    segments = _attr(parsed.body, "segment")
    assert len(segments) == 2

    metadata = segments[0].metadata
    assert _attr(metadata, "participant_1", "participant1") == "DSS-25"
    assert _attr(metadata, "participant_2", "participant2") == "1999-099A"

    observations = _attr(segments[0].data, "observation")
    assert min(_range_values(observations)) == pytest.approx(9.0e10)


def test_kvn_output_is_read_consistently_by_the_oracle() -> None:
    tracking = read(GOLDEN.read_bytes())
    assert isinstance(tracking, Tracking)
    _assert_oracle_matches(write_tdm(tracking, ".tdm"))


def test_xml_output_is_read_consistently_by_the_oracle() -> None:
    tracking = read(GOLDEN.read_bytes())
    assert isinstance(tracking, Tracking)
    _assert_oracle_matches(write_tdm(tracking, ".xml"))
