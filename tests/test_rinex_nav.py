"""The RINEX navigation reader: parsing, the per-constellation adaptation, the record set,
detection, read-only enforcement, the broadcast-vs-SGP4 conversion block, and the
no-silent-loss contract.

The committed ``sample_rinex3_mixed.rnx`` (RINEX 3.04, a GPS + Galileo + GLONASS mix) drives
the definition-of-done read; mutating its bytes covers the malformed-input edges (the file
*is* the reference — the reader is correct when it extracts exactly the values the file
states).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    IncompatibleMeanElementTheoryError,
    MalformedSourceError,
    MeanElementSet,
    StateVector,
    UnsupportedConversionError,
    UnsupportedFormatError,
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.canonical.elements import BROADCAST_MEAN_ELEMENT_THEORY
from orbit_formats.readers.rinex_nav import RinexNav, read_rinex_nav
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.source import SourceInput, load_source

DATA = Path(__file__).parent / "data" / "rinex"
MIXED = DATA / "sample_rinex3_mixed.rnx"

# The GPS constellation's broadcast gravitational parameter (m^3/s^2), used to verify the
# mean-motion the reader derives from sqrt(A) and Delta n.
_GM_GPS = 3.986005e14
_GM_GALILEO = 3.986004418e14


def _records(source: SourceInput = MIXED) -> RinexNav:
    nav = read(source).source_native
    assert isinstance(nav, RinexNav)
    return nav


def _mutate(replacements: tuple[tuple[bytes, bytes], ...]) -> bytes:
    """Return the committed sample's bytes with each (old, new) substitution applied."""
    data = MIXED.read_bytes()
    for old, new in replacements:
        assert old in data, f"{old!r} not found in the sample"
        data = data.replace(old, new)
    return data


# --- the definition-of-done read -------------------------------------------------------


def test_gps_reads_into_a_broadcast_mean_element_set() -> None:
    gps = read(MIXED)
    assert isinstance(gps, MeanElementSet)
    # The first record is the canonical spine; ITRF / Earth / GPS time, broadcast theory.
    assert gps.metadata.object_name == "G01"
    assert gps.metadata.object_id == "G01"
    assert gps.metadata.reference_frame == "ITRF"
    assert gps.metadata.central_body == "Earth"
    assert gps.metadata.time_scale == "GPS"
    assert gps.metadata.provenance is not None
    assert gps.metadata.provenance.source_format == "rinex-nav"
    assert gps.mean_element_theory == BROADCAST_MEAN_ELEMENT_THEORY
    # The element-line angles are the file's radians, in degrees; the eccentricity verbatim.
    assert gps.epoch == np.datetime64("2024-08-17T00:00:00", "ns")
    assert math.isclose(gps.eccentricity, 0.01, rel_tol=0, abs_tol=1e-15)
    assert math.isclose(gps.inclination, math.degrees(0.95))
    assert math.isclose(gps.raan, math.degrees(1.0))
    assert math.isclose(gps.arg_periapsis, math.degrees(0.3))
    assert math.isclose(gps.mean_anomaly, math.degrees(0.5))
    # The mean motion is sqrt(GM / A^3) + Delta n (here 0), converted rad/s -> rev/day.
    semi_major_axis = 5150.0**2
    expected = math.sqrt(_GM_GPS / semi_major_axis**3) * 86400.0 / (2.0 * math.pi)
    assert math.isclose(gps.mean_motion, expected, rel_tol=1e-12)
    # The SGP4 drag terms a broadcast set does not carry stay None.
    assert gps.bstar is None
    assert gps.mean_motion_dot is None


def test_glonass_reads_into_an_earth_fixed_state_vector() -> None:
    states = _records().to_canonical()
    glonass = states[2]
    assert isinstance(glonass, StateVector)
    assert glonass.metadata.object_name == "R01"
    assert glonass.metadata.reference_frame == "ITRF"
    assert glonass.metadata.central_body == "Earth"
    # GLONASS broadcast epochs are in UTC.
    assert glonass.metadata.time_scale == "UTC"
    assert glonass.epoch == np.datetime64("2024-08-17T00:15:00", "ns")
    np.testing.assert_array_equal(glonass.position, [7000.0, -12000.0, 21000.0])
    np.testing.assert_array_equal(glonass.velocity, [1.0, -2.0, 3.0])


def test_galileo_uses_its_own_gravitational_parameter_and_leaves_time_unset() -> None:
    galileo = _records().to_canonical()[1]
    assert isinstance(galileo, MeanElementSet)
    assert galileo.metadata.object_name == "E11"
    assert galileo.metadata.reference_frame == "ITRF"
    # Galileo system time is not one the canonical spine carries — left unset, like SP3.
    assert galileo.metadata.time_scale is None
    assert math.isclose(galileo.eccentricity, 0.02, rel_tol=0, abs_tol=1e-15)
    assert math.isclose(galileo.inclination, math.degrees(0.98))
    expected = math.sqrt(_GM_GALILEO / 5440.0**6) * 86400.0 / (2.0 * math.pi)
    assert math.isclose(galileo.mean_motion, expected, rel_tol=1e-12)


# --- the record set --------------------------------------------------------------------


def test_to_canonical_materialises_every_record_in_order() -> None:
    nav = _records()
    objects = nav.to_canonical()
    assert [o.metadata.object_name for o in objects] == ["G01", "E11", "R01"]
    assert [type(o).__name__ for o in objects] == [
        "MeanElementSet",
        "MeanElementSet",
        "StateVector",
    ]
    # Every record's canonical object carries the whole file as its source_native handle.
    assert all(o.source_native is nav for o in objects)


# --- fidelity preservation -------------------------------------------------------------


def test_source_native_preserves_the_header_and_raw_broadcast_fields() -> None:
    nav = _records()
    assert nav.version == "3.04"
    assert nav.file_type == "N"
    assert nav.satellite_system == "M"
    assert nav.program == "ORBIT-FORMATS"
    assert nav.run_by == "ASTRO-TOOLS"
    assert nav.leap_seconds == 18
    assert nav.ionospheric_corrections[0].startswith("GPSA")
    assert nav.time_system_corrections[0].startswith("GPUT")
    assert nav.comments[0].startswith("hand-authored")
    assert [r.sat_id for r in nav.records] == ["G01", "E11", "R01"]
    gps = nav.records[0]
    # The SV clock polynomial and the constellation-specific fields the canonical form has no
    # slot for ride on the record verbatim.
    np.testing.assert_allclose(gps.clock, [-1.234567890123e-04, -1.136868377216e-12, 0.0])
    assert gps.field("sqrt_a") == 5150.0
    assert gps.field("Toe") == 460800.0
    assert gps.field("Crs") == -15.625
    # A constellation-specific field the named layout does not cover (the GPS group delay TGD,
    # at broadcast-orbit line 6) is still preserved verbatim on the raw orbit tuple.
    assert math.isclose(gps.orbit[22], -5.122274160385e-09)
    assert gps.is_keplerian and not gps.is_cartesian
    assert nav.records[2].is_cartesian


def test_retain_source_keeps_the_verbatim_bytes() -> None:
    nav = read(MIXED, retain_source=True).source_native
    assert isinstance(nav, RinexNav)
    assert nav.raw_bytes == MIXED.read_bytes()
    default = read(MIXED).source_native
    assert isinstance(default, RinexNav)
    assert default.raw_bytes is None


# --- detection and registration --------------------------------------------------------


def test_detection_and_format_override() -> None:
    assert detect_format(MIXED) == "rinex-nav"
    # An explicit format= forces the RINEX reader.
    forced = read(MIXED, format="rinex-nav")
    assert isinstance(forced, MeanElementSet)


def test_rinex_nav_registers_a_reader_but_no_writer() -> None:
    assert get_reader("rinex-nav") is not None
    assert get_writer("rinex-nav") is None


def test_writing_rinex_nav_is_rejected_as_read_only(tmp_path: Path) -> None:
    gps = read(MIXED)
    with pytest.raises(UnsupportedFormatError, match="read-only"):
        write(gps, tmp_path / "out.rnx")


# --- the broadcast-vs-SGP4 conversion block --------------------------------------------


@pytest.mark.parametrize("target", ["tle", "ccsds-omm"])
def test_broadcast_mean_set_cannot_convert_to_an_sgp4_format(target: str) -> None:
    gps = read(MIXED)
    with pytest.raises(IncompatibleMeanElementTheoryError) as info:
        convert(gps, to=target)
    # The block is catchable as the general unsupported-conversion family.
    assert isinstance(info.value, UnsupportedConversionError)
    assert info.value.source_theory == BROADCAST_MEAN_ELEMENT_THEORY
    assert info.value.target_format == target


@pytest.mark.parametrize(("ext", "match"), [(".tle", "tle"), (".omm", "ccsds-omm")])
def test_writing_a_broadcast_set_to_an_sgp4_format_is_refused(
    ext: str, match: str, tmp_path: Path
) -> None:
    gps = read(MIXED)
    with pytest.raises(IncompatibleMeanElementTheoryError, match=match):
        write(gps, tmp_path / f"out{ext}")


def test_converting_to_the_same_read_only_format_is_an_identity() -> None:
    # A broadcast set "converted" to rinex-nav (its own read-only form) is the same object;
    # the block targets only the SGP4 mean-element formats.
    gps = read(MIXED)
    assert convert(gps, to="rinex-nav") is gps


# --- the no-silent-loss contract -------------------------------------------------------


def test_no_silent_loss(assert_no_silent_loss: Callable[..., None]) -> None:
    # Constellation-specific fields are preserved on source_native, so a read loses nothing.
    assert_no_silent_loss(lambda: read(MIXED), loses=False)


# --- malformed input -------------------------------------------------------------------


def test_rinex_2_is_rejected() -> None:
    source = _mutate(((b"     3.04", b"     2.11"),))
    with pytest.raises(MalformedSourceError, match="parses RINEX 3"):
        read(source, format="rinex-nav")


def test_rinex_4_is_rejected() -> None:
    source = _mutate(((b"     3.04", b"     4.00"),))
    with pytest.raises(MalformedSourceError, match="parses RINEX 3"):
        read(source, format="rinex-nav")


def test_missing_end_of_header_is_rejected() -> None:
    lines = [ln for ln in MIXED.read_text().splitlines() if "END OF HEADER" not in ln]
    source = ("\n".join(lines) + "\n").encode("utf-8")
    with pytest.raises(MalformedSourceError, match="END OF HEADER"):
        read(source, format="rinex-nav")


def test_unknown_constellation_is_rejected() -> None:
    source = _mutate(((b"G01 2024 08 17 00 00 00", b"X01 2024 08 17 00 00 00"),))
    with pytest.raises(MalformedSourceError, match="unknown RINEX constellation"):
        read(source, format="rinex-nav")


def test_truncated_record_is_rejected() -> None:
    # Drop the GLONASS record's last two broadcast-orbit lines, leaving it short of three.
    lines = MIXED.read_text().splitlines()
    source = ("\n".join(lines[:-2]) + "\n").encode("utf-8")
    with pytest.raises(MalformedSourceError, match="truncated"):
        read(source, format="rinex-nav")


def test_non_numeric_field_is_rejected() -> None:
    source = _mutate(((b"5.150000000000D+03", b"5.150000000Z00D+03"),))
    with pytest.raises(MalformedSourceError, match="non-numeric"):
        read(source, format="rinex-nav")


def test_no_records_is_rejected() -> None:
    header = MIXED.read_text().split("END OF HEADER")[0] + "END OF HEADER\n"
    with pytest.raises(MalformedSourceError, match="no broadcast records"):
        read(header.encode("utf-8"), format="rinex-nav")


def test_unparseable_epoch_is_rejected() -> None:
    source = _mutate(((b"G01 2024 08 17 00 00 00", b"G01 2024 08 17 00 00 XX"),))
    with pytest.raises(MalformedSourceError, match="epoch"):
        read(source, format="rinex-nav")


def test_read_rinex_nav_is_the_registered_reader() -> None:
    # The module-level function and the registry entry are the same reader.
    assert read_rinex_nav(load_source(MIXED)) == read(MIXED)
