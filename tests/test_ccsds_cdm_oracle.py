"""Cross-validate the CDM writer's output against the dev-only ccsds-ndm oracle.

ccsds-ndm is GPL-3.0 and is never a runtime/dev dependency, never imported by the package,
and never distributed; it is installed transiently in one CI job and pulled in here only
behind :func:`pytest.importorskip`. The check is independence: the writer emits a CDM (KVN and
XML), a separate CCSDS implementation parses it, and we assert it reads back the same object
designators, TCA, miss distance, and a covariance element the canonical conjunction holds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("ccsds_ndm")

from ccsds_ndm.ndm_io import NdmIo

from orbit_formats import Conjunction, read
from orbit_formats.writers.cdm import write_cdm

GOLDEN = Path(__file__).parent / "data" / "cdm" / "golden_cdm.cdm"


def _attr(obj: Any, *names: str) -> Any:
    """The first present attribute among ``names`` (snake_case / camelCase oracle shapes)."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    raise AttributeError(f"none of {names} on {type(obj).__name__}")


def _value(obj: Any) -> float:
    """A scalar value, unwrapping a typed value+units element if necessary."""
    return float(getattr(obj, "value", obj))


def _assert_oracle_matches(cdm_bytes: bytes, conjunction: Conjunction) -> None:
    parsed = NdmIo().from_string(cdm_bytes.decode("utf-8"))
    body = parsed.body
    segments = _attr(body, "segment")
    assert len(segments) == 2

    designators = [_attr(seg.metadata, "object_designator") for seg in segments]
    assert designators == [obj.object_designator for obj in conjunction.objects]

    relative = _attr(body, "relative_metadata_data", "relativeMetadataData")
    assert _value(_attr(relative, "miss_distance")) == pytest.approx(conjunction.miss_distance)

    covariance = _attr(segments[0].data, "covariance_matrix", "covarianceMatrix")
    assert _value(_attr(covariance, "cr_r")) == pytest.approx(
        float(conjunction.objects[0].covariance[0, 0])
    )


def test_kvn_output_is_read_consistently_by_the_oracle() -> None:
    conjunction = read(GOLDEN.read_bytes())
    assert isinstance(conjunction, Conjunction)
    _assert_oracle_matches(write_cdm(conjunction, ".cdm"), conjunction)


def test_xml_output_is_read_consistently_by_the_oracle() -> None:
    conjunction = read(GOLDEN.read_bytes())
    assert isinstance(conjunction, Conjunction)
    _assert_oracle_matches(write_cdm(conjunction, ".xml"), conjunction)
