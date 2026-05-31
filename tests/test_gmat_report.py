"""The GMAT ReportFile reader: report table -> canonical Ephemeris / StateVector.

Samples are authored inline and mirror real GMAT R2026a report layouts (the multi-spacecraft
position-only report and the ``<resource>.<coordsys>.<component>`` / default-frame column
forms seen in the installed samples): the file *is* the reference, so a parser is correct
when it extracts exactly what the file states. Fixtures use implicit byte concatenation so
each source line stays within the line-length limit; the column separator is the run of two
or more spaces GMAT writes, so the wrapping does not change how a row parses.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Ephemeris,
    MalformedSourceError,
    MissingFieldWarning,
    StateVector,
    UnsupportedFormatError,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.gmat_report import GmatReportFile, read_gmat_report
from orbit_formats.registry import get_reader

NoSilentLossCheck = Callable[..., None]

# Full Cartesian state (position + velocity), Gregorian UTC epochs, one coordinate system.
REPORT_FULL = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5   0.0\n"
    b"26 Nov 2026 12:01:00.000   6999.0   450.0   0.0   -0.5   7.49   0.0\n"
)

# Two spacecraft, each position-only (no velocity) — the layout of the installed
# Starship_to_Mars_1_v2.report. The first group is adapted; the second is preserved verbatim.
REPORT_POSITION_ONLY = (
    b"StarshipLEO.UTCGregorian   StarshipLEO.EarthMJ2000Eq.X   "
    b"StarshipLEO.EarthMJ2000Eq.Y   StarshipLEO.EarthMJ2000Eq.Z   "
    b"StarshipMars.UTCGregorian   StarshipMars.EarthMJ2000Eq.X   "
    b"StarshipMars.EarthMJ2000Eq.Y   StarshipMars.EarthMJ2000Eq.Z\n"
    b"26 Nov 2026 12:00:00.000   -5696.263   3288.739   0   "
    b"03 Aug 2027 12:00:00.000   -262988794.36   -46960176.96   -19777695.87\n"
    b"26 Nov 2026 12:01:00.000   -5600.0   3300.0   0   "
    b"03 Aug 2027 11:59:15.701   -262988386.06   -46958887.17   -19777018.46\n"
)

# A single row in GMAT's A1 scale (which the canonical spine does not carry) — ModJulian.
REPORT_A1_SINGLE = (
    b"Sat.A1ModJulian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"21545.0   7000.0   0.0   0.0   0.0   7.5   0.0\n"
)

# Components named without a coordinate system (GMAT's default frame, undeclared), UTC MJD.
REPORT_NO_COORDSYS = (
    b"LEOsat.UTCModJulian   LEOsat.X   LEOsat.Y   LEOsat.Z   LEOsat.VX   LEOsat.VY   LEOsat.VZ\n"
    b"21545.0   7000.0   0.0   0.0   0.0   7.5   0.0\n"
)

# Full position but only two of three velocity components — VZ is absent from the group.
REPORT_PARTIAL = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5\n"
    b"26 Nov 2026 12:01:00.000   6999.0   450.0   0.0   -0.5   7.49\n"
)

# The header re-emitted at a mission-sequence segment boundary, mid-file.
REPORT_HEADER_REPEAT = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5   0.0\n"
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:01:00.000   6999.0   450.0   0.0   -0.5   7.49   0.0\n"
)

# A blank line between two data rows (GMAT pads its output): it is skipped, not parsed.
REPORT_BLANK_DATA_LINE = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5   0.0\n"
    b"\n"
    b"26 Nov 2026 12:01:00.000   6999.0   450.0   0.0   -0.5   7.49   0.0\n"
)

# The epoch column belongs to a different resource than the Cartesian state's: epoch
# selection falls back to the first recognised epoch column.
REPORT_EPOCH_OTHER_RESOURCE = (
    b"Clock.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5   0.0\n"
)

# A column with no resource qualifier (``Index``) and an incomplete state group
# (``Probe`` has only X) precede the first complete state group (``Sat``): both are
# skipped when choosing the state to adapt.
REPORT_MIXED_NONSTATE = (
    b"Sat.UTCGregorian   Index   Probe.EarthMJ2000Eq.X   "
    b"Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   Sat.EarthMJ2000Eq.Z   "
    b"Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   0   1.0   7000.0   0.0   0.0   0.0   7.5   0.0\n"
)


def test_reader_is_registered_for_gmat_report() -> None:
    assert get_reader("gmat-report") is read_gmat_report


def test_explicit_format_reads_the_report() -> None:
    # The GMAT report has no content signature, so format="gmat-report" is the named path.
    eph = read(REPORT_FULL, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 2


def test_read_extracts_the_full_cartesian_state() -> None:
    eph = read(REPORT_FULL, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    np.testing.assert_allclose(eph.positions[0], (7000.0, 0.0, 0.0))
    np.testing.assert_allclose(eph.velocities[0], (0.0, 7.5, 0.0))
    np.testing.assert_allclose(eph.positions[-1], (6999.0, 450.0, 0.0))
    np.testing.assert_allclose(eph.velocities[-1], (-0.5, 7.49, 0.0))


def test_read_tags_the_spine_from_the_column_names() -> None:
    md = read(REPORT_FULL, format="gmat-report").metadata
    assert md.reference_frame == "EarthMJ2000Eq"
    assert md.time_scale == "UTC"
    assert md.object_name == "Sat"
    assert md.central_body is None  # a report does not declare a central body; not inferred
    assert md.provenance is not None
    assert md.provenance.source_format == "gmat-report"


def test_gregorian_epochs_parse_to_the_instant() -> None:
    eph = read(REPORT_FULL, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    assert eph.epochs[0] == np.datetime64("2026-11-26T12:00:00", "ns")
    assert eph.epochs[1] == np.datetime64("2026-11-26T12:01:00", "ns")


def test_gregorian_fractional_seconds_are_kept() -> None:
    report = REPORT_FULL.replace(b"12:00:00.000", b"12:00:00.500")
    eph = read(report, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    assert eph.epochs[0] == np.datetime64("2026-11-26T12:00:00.500", "ns")


def test_modjulian_epoch_uses_the_gmat_mjd_origin() -> None:
    # GMAT MJD 21545.0 is J2000: 2000-01-01 12:00:00.
    sv = read(REPORT_A1_SINGLE, format="gmat-report")
    assert isinstance(sv, StateVector)
    assert sv.epoch == np.datetime64("2000-01-01T12:00:00", "ns")


def test_a_single_row_becomes_a_state_vector() -> None:
    sv = read(REPORT_A1_SINGLE, format="gmat-report")
    assert isinstance(sv, StateVector)
    np.testing.assert_allclose(sv.position, (7000.0, 0.0, 0.0))
    np.testing.assert_allclose(sv.velocity, (0.0, 7.5, 0.0))


def test_the_a1_scale_is_left_untagged_but_the_raw_column_survives() -> None:
    # A1 is a valid GMAT scale but not one the canonical spine carries; nothing is lost.
    sv = read(REPORT_A1_SINGLE, format="gmat-report")
    assert sv.metadata.time_scale is None
    report = sv.source_native
    assert isinstance(report, GmatReportFile)
    assert "Sat.A1ModJulian" in report.columns


def test_a_column_without_a_coordinate_system_leaves_the_frame_untagged() -> None:
    sv = read(REPORT_NO_COORDSYS, format="gmat-report")
    assert isinstance(sv, StateVector)
    assert sv.metadata.reference_frame is None  # report did not declare a frame; not inferred
    assert sv.metadata.time_scale == "UTC"
    assert sv.metadata.object_name == "LEOsat"


def test_position_only_report_fills_velocity_with_nan_and_warns() -> None:
    with pytest.warns(MissingFieldWarning) as record:
        eph = read(REPORT_POSITION_ONLY, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    np.testing.assert_allclose(eph.positions[0], (-5696.263, 3288.739, 0.0))
    assert np.isnan(eph.velocities).all()
    warning = next(r.message for r in record if isinstance(r.message, MissingFieldWarning))
    assert warning.fields == ("VX", "VY", "VZ")
    assert warning.source_format == "gmat-report"
    assert all(field.reason for field in warning.dropped)


def test_position_only_report_adapts_the_first_group_and_preserves_the_second() -> None:
    with pytest.warns(MissingFieldWarning):
        eph = read(REPORT_POSITION_ONLY, format="gmat-report")
    assert eph.metadata.object_name == "StarshipLEO"
    report = eph.source_native
    assert isinstance(report, GmatReportFile)
    # The second spacecraft's columns are not placed in the canonical object, but survive.
    assert "StarshipMars.EarthMJ2000Eq.X" in report.columns
    assert "StarshipMars.UTCGregorian" in report.columns


def test_a_partly_present_velocity_nan_fills_only_the_absent_component() -> None:
    with pytest.warns(MissingFieldWarning) as record:
        eph = read(REPORT_PARTIAL, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    np.testing.assert_allclose(eph.velocities[:, 0], (0.0, -0.5))
    np.testing.assert_allclose(eph.velocities[:, 1], (7.5, 7.49))
    assert np.isnan(eph.velocities[:, 2]).all()
    warning = next(r.message for r in record if isinstance(r.message, MissingFieldWarning))
    assert warning.fields == ("VZ",)


def test_repeated_header_rows_are_skipped() -> None:
    eph = read(REPORT_HEADER_REPEAT, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 2
    assert eph.epochs[1] == np.datetime64("2026-11-26T12:01:00", "ns")
    np.testing.assert_allclose(eph.positions[1], (6999.0, 450.0, 0.0))


def test_to_dataframe_carries_the_report_spine() -> None:
    eph = read(REPORT_FULL, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    df = eph.to_dataframe()
    assert df.attrs["coordinate_system"] == "EarthMJ2000Eq"
    assert df.attrs["time_scale"] == "UTC"
    assert df.attrs["object_name"] == "Sat"
    assert len(df) == 2


def test_read_from_a_path_routes_through_detection(tmp_path: Path) -> None:
    # The .report extension is the only way to detect a signature-less GMAT report.
    target = tmp_path / "mission.report"
    target.write_bytes(REPORT_FULL)
    assert detect_format(target) == "gmat-report"
    eph = read(target)  # no format= : exercises extension detection -> this reader
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 2


def test_retain_source_keeps_the_raw_bytes() -> None:
    eph = read(REPORT_FULL, format="gmat-report", retain_source=True)
    report = eph.source_native
    assert isinstance(report, GmatReportFile)
    assert report.raw_bytes == REPORT_FULL


def test_an_ordinary_read_holds_no_raw_bytes() -> None:
    eph = read(REPORT_FULL, format="gmat-report")
    report = eph.source_native
    assert isinstance(report, GmatReportFile)
    assert report.raw_bytes is None


def test_a_full_state_read_loses_nothing(assert_no_silent_loss: NoSilentLossCheck) -> None:
    assert_no_silent_loss(lambda: read(REPORT_FULL, format="gmat-report"), loses=False)


def test_a_position_only_read_warns_about_the_loss(
    assert_no_silent_loss: NoSilentLossCheck,
) -> None:
    assert_no_silent_loss(lambda: read(REPORT_POSITION_ONLY, format="gmat-report"), loses=True)


# --- malformed inputs ------------------------------------------------------------------


def test_an_empty_report_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match=r"empty"):
        read(b"   \n\n", format="gmat-report")


def test_a_report_with_no_epoch_column_is_rejected() -> None:
    no_epoch = (
        b"Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   Sat.EarthMJ2000Eq.Z   "
        b"Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   Sat.EarthMJ2000Eq.VZ\n"
        b"7000.0   0.0   0.0   0.0   7.5   0.0\n"
    )
    with pytest.raises(MalformedSourceError, match=r"no recognised epoch column"):
        read(no_epoch, format="gmat-report")


def test_a_report_with_no_cartesian_state_is_rejected() -> None:
    scalars_only = (
        b"Sat.UTCGregorian   Sat.Earth.SMA   Sat.Earth.ECC\n"
        b"26 Nov 2026 12:00:00.000   7000.0   0.001\n"
    )
    with pytest.raises(MalformedSourceError, match=r"no Cartesian state"):
        read(scalars_only, format="gmat-report")


def test_a_data_row_with_the_wrong_column_count_is_rejected() -> None:
    broken = (
        b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
        b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
        b"Sat.EarthMJ2000Eq.VZ\n"
        b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0\n"
    )
    with pytest.raises(MalformedSourceError, match=r"has 4 column.* but the header declares 7"):
        read(broken, format="gmat-report")


def test_a_non_numeric_state_value_is_rejected() -> None:
    broken = REPORT_FULL.replace(b"7000.0", b"oops", 1)
    with pytest.raises(MalformedSourceError, match=r"non-numeric value 'oops'"):
        read(broken, format="gmat-report")


def test_an_unparseable_gregorian_month_is_rejected() -> None:
    broken = REPORT_FULL.replace(b"26 Nov 2026", b"26 Zzz 2026")
    with pytest.raises(MalformedSourceError, match=r"unknown month 'Zzz'"):
        read(broken, format="gmat-report")


def test_a_malformed_gregorian_epoch_is_rejected() -> None:
    broken = REPORT_FULL.replace(b"26 Nov 2026 12:00:00.000", b"26 Nov 2026")
    with pytest.raises(MalformedSourceError, match=r"could not parse the GMAT epoch"):
        read(broken, format="gmat-report")


def test_a_non_numeric_modjulian_epoch_is_rejected() -> None:
    broken = REPORT_A1_SINGLE.replace(b"21545.0", b"notanumber")
    with pytest.raises(MalformedSourceError, match=r"could not parse the GMAT epoch"):
        read(broken, format="gmat-report")


def test_a_gregorian_epoch_with_a_malformed_time_of_day_is_rejected() -> None:
    # Four space-separated tokens, but the time of day is HH:MM, not HH:MM:SS.
    broken = REPORT_FULL.replace(b"26 Nov 2026 12:00:00.000", b"26 Nov 2026 12:00")
    with pytest.raises(MalformedSourceError, match=r"expected HH:MM:SS"):
        read(broken, format="gmat-report")


def test_a_gregorian_epoch_with_a_non_numeric_field_is_rejected() -> None:
    # Well-formed shape and a known month, but the day is not an integer.
    broken = REPORT_FULL.replace(b"26 Nov 2026 12:00:00.000", b"XX Nov 2026 12:00:00.000")
    with pytest.raises(MalformedSourceError, match=r"could not parse the GMAT epoch"):
        read(broken, format="gmat-report")


# --- column / epoch-selection edge cases -----------------------------------------------


def test_a_blank_line_among_data_rows_is_skipped() -> None:
    eph = read(REPORT_BLANK_DATA_LINE, format="gmat-report")
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 2  # the blank line is skipped, not counted as a row
    assert eph.epochs[1] == np.datetime64("2026-11-26T12:01:00", "ns")


def test_epoch_column_for_a_different_resource_falls_back_to_the_first() -> None:
    # No epoch column belongs to the state's resource ("Sat"), so the first recognised
    # epoch column ("Clock.UTCGregorian") is used.
    sv = read(REPORT_EPOCH_OTHER_RESOURCE, format="gmat-report")
    assert isinstance(sv, StateVector)
    assert sv.epoch == np.datetime64("2026-11-26T12:00:00", "ns")
    assert sv.metadata.object_name == "Sat"
    np.testing.assert_allclose(sv.velocity, (0.0, 7.5, 0.0))


def test_non_state_and_incomplete_columns_are_skipped_for_the_first_complete_state() -> None:
    sv = read(REPORT_MIXED_NONSTATE, format="gmat-report")
    assert isinstance(sv, StateVector)
    # "Index" (no resource qualifier) and "Probe" (X only, no triplet) are skipped; the
    # first complete group, "Sat", is adapted.
    assert sv.metadata.object_name == "Sat"
    np.testing.assert_allclose(sv.position, (7000.0, 0.0, 0.0))
    np.testing.assert_allclose(sv.velocity, (0.0, 7.5, 0.0))
    # The skipped columns still survive verbatim on the fidelity model.
    report = sv.source_native
    assert isinstance(report, GmatReportFile)
    assert "Index" in report.columns
    assert "Probe.EarthMJ2000Eq.X" in report.columns


def test_writing_a_gmat_report_is_rejected_as_read_only(tmp_path: Path) -> None:
    # A GMAT ReportFile is a GMAT output we only read; the format is catalogued read-only.
    eph = read(REPORT_FULL, format="gmat-report")
    with pytest.raises(UnsupportedFormatError, match="read-only"):
        write(eph, tmp_path / "out.report")
