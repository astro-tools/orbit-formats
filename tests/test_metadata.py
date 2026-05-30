"""Tests for the shared metadata spine (units, provenance, validated tags)."""

from __future__ import annotations

import pytest

from orbit_formats import DEFAULT_UNITS, Metadata, Provenance, UnitSpec
from orbit_formats.canonical.metadata import TIME_SCALES


def test_unitspec_defaults_and_custom() -> None:
    assert UnitSpec() == DEFAULT_UNITS
    assert (DEFAULT_UNITS.length, DEFAULT_UNITS.speed) == ("km", "km/s")
    assert (DEFAULT_UNITS.angle, DEFAULT_UNITS.time) == ("deg", "s")
    custom = UnitSpec(length="m", speed="m/s", angle="rad", time="min")
    assert custom != DEFAULT_UNITS
    # frozen value type -> hashable and usable in a set
    assert len({UnitSpec(), UnitSpec(), custom}) == 2


def test_metadata_defaults() -> None:
    meta = Metadata()
    assert meta.object_name is None
    assert meta.object_id is None
    assert meta.originator is None
    assert meta.reference_frame is None
    assert meta.central_body is None
    assert meta.time_scale is None
    assert meta.units == DEFAULT_UNITS
    assert meta.provenance is None


@pytest.mark.parametrize("scale", sorted(TIME_SCALES))
def test_metadata_accepts_every_recognised_time_scale(scale: str) -> None:
    assert Metadata(time_scale=scale).time_scale == scale


def test_metadata_rejects_unknown_time_scale() -> None:
    with pytest.raises(ValueError, match="unknown time_scale"):
        Metadata(time_scale="BOGUS")


def test_metadata_is_frozen_and_value_equal() -> None:
    prov = Provenance(source_format="ccsds-oem", creation_date="2026-01-01", header="h")
    a = Metadata(object_name="SAT", time_scale="UTC", provenance=prov)
    b = Metadata(object_name="SAT", time_scale="UTC", provenance=prov)
    assert a == b
    assert hash(a) == hash(b)
    with pytest.raises(AttributeError):
        a.object_name = "OTHER"  # type: ignore[misc]


def test_provenance_fields() -> None:
    prov = Provenance(source_format="tle", creation_date="2026-05-30", header="line0")
    assert prov.source_format == "tle"
    assert prov.creation_date == "2026-05-30"
    assert prov.header == "line0"
    assert Provenance() == Provenance(None, None, None)
