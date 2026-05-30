"""The in-house CCSDS OEM (KVN) reader: OEM -> canonical Ephemeris, fidelity retained.

The samples are authored inline (as in the TLE reader's tests): a parser is correct when
it extracts exactly the values the file states, so the file *is* the reference. The
committed golden corpus and the ccsds-ndm oracle cross-validation are the OEM writer's
concern (a later issue), not this reader's.
"""

from __future__ import annotations

import numpy as np
import pytest

from orbit_formats import Ephemeris, MalformedSourceError, detect_format, read
from orbit_formats.readers.ccsds import OemFile, read_oem
from orbit_formats.registry import get_reader

# A single-segment OEM with calendar epochs and position/velocity only.
OEM_SINGLE = b"""CCSDS_OEM_VERS = 2.0
CREATION_DATE = 2002-11-04T17:22:31
ORIGINATOR = NASA/JPL
COMMENT This is an OEM file for testing.

META_START
OBJECT_NAME = MARS GLOBAL SURVEYOR
OBJECT_ID = 1996-062A
CENTER_NAME = MARS BARYCENTER
REF_FRAME = EME2000
TIME_SYSTEM = UTC
START_TIME = 1996-12-18T12:00:00.331
USEABLE_START_TIME = 1996-12-18T12:00:00.331
USEABLE_STOP_TIME = 1996-12-18T12:02:00.331
STOP_TIME = 1996-12-18T12:02:00.331
INTERPOLATION = HERMITE
INTERPOLATION_DEGREE = 7
META_STOP

COMMENT ephemeris data follows
1996-12-18T12:00:00.331 2789.619 -280.045 -1746.755 4.73372 -2.49586 -1.04195
1996-12-18T12:01:00.331 2783.419 -308.143 -1877.071 5.18604 -2.42124 -1.99608
1996-12-18T12:02:00.331 2776.033 -336.859 -2008.682 5.63563 -2.33815 -1.96402
"""

# Two contiguous segments of the same object/frame/time — concatenated into one ephemeris.
OEM_MULTI = b"""CCSDS_OEM_VERS = 2.0
ORIGINATOR = GSOC

META_START
OBJECT_NAME = EUTELSAT W4
OBJECT_ID = 2000-028A
CENTER_NAME = EARTH
REF_FRAME = TOD
TIME_SYSTEM = UTC
START_TIME = 2000-06-03T00:00:00.000
STOP_TIME = 2000-06-03T00:01:00.000
META_STOP
2000-06-03T00:00:00.000 6655.998 -40218.443 -82.838 3.11548 0.47042 -0.00563
2000-06-03T00:01:00.000 6843.196 -40189.453 -83.075 3.10707 0.50456 -0.00547

META_START
OBJECT_NAME = EUTELSAT W4
OBJECT_ID = 2000-028A
CENTER_NAME = EARTH
REF_FRAME = TOD
TIME_SYSTEM = UTC
START_TIME = 2000-06-03T00:02:00.000
STOP_TIME = 2000-06-03T00:02:00.000
META_STOP
2000-06-03T00:02:00.000 7030.187 -40158.491 -83.311 3.09864 0.53869 -0.00531
"""

# Day-of-year epochs, acceleration columns, and a non-standard META keyword to preserve.
OEM_DOY_ACCEL = b"""CCSDS_OEM_VERS = 1.0
CREATION_DATE = 2004-281T17:26:06
ORIGINATOR = ME

META_START
COMMENT segment-level comment
OBJECT_NAME = STARLETTE
OBJECT_ID = 1975-010A
CENTER_NAME = EARTH
REF_FRAME = ITRF2000
TIME_SYSTEM = UTC
START_TIME = 2004-100T00:00:00.000
STOP_TIME = 2004-100T00:01:00.000
USER_DEFINED_THING = keep me
META_STOP
2004-100T00:00:00.000 1.0 2.0 3.0 4.0 5.0 6.0 0.1 0.2 0.3
2004-100T00:01:00.000 1.1 2.1 3.1 4.1 5.1 6.1 0.11 0.21 0.31
"""

# A covariance block following the ephemeris data.
OEM_COVARIANCE = b"""CCSDS_OEM_VERS = 2.0

META_START
OBJECT_NAME = SAT
OBJECT_ID = 2000-000A
CENTER_NAME = EARTH
REF_FRAME = EME2000
TIME_SYSTEM = UTC
START_TIME = 2000-01-01T00:00:00.000
STOP_TIME = 2000-01-01T00:00:00.000
META_STOP
2000-01-01T00:00:00.000 1.0 2.0 3.0 4.0 5.0 6.0

COVARIANCE_START
EPOCH = 2000-01-01T00:00:00.000
COV_REF_FRAME = RTN
 0.31
 0.32 0.33
 0.34 0.35 0.36
 0.37 0.38 0.39 0.40
 0.41 0.42 0.43 0.44 0.45
 0.46 0.47 0.48 0.49 0.50 0.51
COVARIANCE_STOP
"""


def test_reader_is_registered_for_ccsds_oem() -> None:
    assert get_reader("ccsds-oem") is read_oem


def test_ccsds_oem_signature_is_detected_before_reading() -> None:
    # The auto-detection contract: CCSDS-OEM KVN content routes to the ccsds-oem format id.
    assert detect_format(OEM_SINGLE) == "ccsds-oem"


def test_read_returns_an_ephemeris_with_the_state_records() -> None:
    eph = read(OEM_SINGLE)  # no format= : exercises auto-detection routing to this reader
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 3
    np.testing.assert_allclose(eph.positions[0], (2789.619, -280.045, -1746.755))
    np.testing.assert_allclose(eph.velocities[0], (4.73372, -2.49586, -1.04195))
    np.testing.assert_allclose(eph.positions[-1], (2776.033, -336.859, -2008.682))
    assert eph.epochs[0] == np.datetime64("1996-12-18T12:00:00.331", "ns")
    assert eph.epochs[-1] == np.datetime64("1996-12-18T12:02:00.331", "ns")


def test_read_tags_the_spine_from_the_oem_meta() -> None:
    md = read(OEM_SINGLE).metadata
    assert md.reference_frame == "EME2000"
    assert md.central_body == "MARS BARYCENTER"
    assert md.time_scale == "UTC"
    assert md.object_name == "MARS GLOBAL SURVEYOR"
    assert md.object_id == "1996-062A"
    assert md.originator == "NASA/JPL"
    assert md.provenance is not None
    assert md.provenance.source_format == "ccsds-oem"
    assert md.provenance.creation_date == "2002-11-04T17:22:31"


def test_read_carries_the_interpolation_hint() -> None:
    eph = read(OEM_SINGLE)
    assert isinstance(eph, Ephemeris)
    assert eph.interpolation == "HERMITE"
    assert eph.interpolation_degree == 7


def test_source_native_retains_the_full_oem_fidelity_model() -> None:
    eph = read(OEM_SINGLE)
    oem = eph.source_native
    assert isinstance(oem, OemFile)
    assert oem.format_name == "ccsds-oem"
    assert oem.ccsds_version == "2.0"
    assert oem.creation_date == "2002-11-04T17:22:31"
    assert oem.originator == "NASA/JPL"
    assert oem.comments == ("This is an OEM file for testing.",)
    assert len(oem.segments) == 1
    meta = oem.segments[0].meta
    assert meta.useable_start_time == "1996-12-18T12:00:00.331"
    assert meta.useable_stop_time == "1996-12-18T12:02:00.331"
    assert meta.start_time == "1996-12-18T12:00:00.331"
    assert meta.stop_time == "1996-12-18T12:02:00.331"
    assert oem.segments[0].comments == ("ephemeris data follows",)


def test_to_dataframe_carries_the_oem_spine() -> None:
    eph = read(OEM_SINGLE)
    assert isinstance(eph, Ephemeris)
    df = eph.to_dataframe()
    assert df.attrs["coordinate_system"] == "EME2000"
    assert df.attrs["central_body"] == "MARS BARYCENTER"
    assert df.attrs["time_scale"] == "UTC"
    assert df.attrs["object_name"] == "MARS GLOBAL SURVEYOR"
    assert df.attrs["interpolation"] == "HERMITE"
    assert len(df) == 3


def test_multi_segment_files_concatenate_into_one_ephemeris() -> None:
    eph = read(OEM_MULTI)
    assert isinstance(eph, Ephemeris)
    # 2 + 1 records across the two segments, in file order.
    assert len(eph) == 3
    assert eph.epochs[0] == np.datetime64("2000-06-03T00:00:00.000", "ns")
    assert eph.epochs[-1] == np.datetime64("2000-06-03T00:02:00.000", "ns")
    np.testing.assert_allclose(eph.positions[-1], (7030.187, -40158.491, -83.311))


def test_multi_segment_preserves_per_segment_metadata_on_the_fidelity_model() -> None:
    oem = read(OEM_MULTI).source_native
    assert isinstance(oem, OemFile)
    assert len(oem.segments) == 2
    assert oem.segments[0].meta.start_time == "2000-06-03T00:00:00.000"
    assert oem.segments[1].meta.start_time == "2000-06-03T00:02:00.000"
    assert [len(s.epochs) for s in oem.segments] == [2, 1]


def test_day_of_year_epochs_parse() -> None:
    eph = read(OEM_DOY_ACCEL)
    assert isinstance(eph, Ephemeris)
    # 2004 is a leap year, so day-of-year 100 is 2004-04-09.
    assert eph.epochs[0] == np.datetime64("2004-04-09T00:00:00", "ns")
    assert eph.epochs[1] == np.datetime64("2004-04-09T00:01:00", "ns")


def test_acceleration_columns_are_retained_on_the_fidelity_model_only() -> None:
    eph = read(OEM_DOY_ACCEL)
    assert isinstance(eph, Ephemeris)
    # The canonical Ephemeris holds position and velocity only.
    np.testing.assert_allclose(eph.positions[0], (1.0, 2.0, 3.0))
    np.testing.assert_allclose(eph.velocities[0], (4.0, 5.0, 6.0))
    oem = eph.source_native
    assert isinstance(oem, OemFile)
    accelerations = oem.segments[0].accelerations
    assert accelerations is not None
    np.testing.assert_allclose(accelerations, [(0.1, 0.2, 0.3), (0.11, 0.21, 0.31)])


def test_non_standard_meta_keywords_are_preserved_not_dropped() -> None:
    oem = read(OEM_DOY_ACCEL).source_native
    assert isinstance(oem, OemFile)
    assert oem.segments[0].meta.extra == (("USER_DEFINED_THING", "keep me"),)
    assert oem.segments[0].meta.comments == ("segment-level comment",)


def test_an_unrecognised_time_system_leaves_the_scale_untagged_but_keeps_the_raw_value() -> None:
    # TCB is a valid OEM TIME_SYSTEM but not one the canonical spine tags; nothing is lost.
    tcb = OEM_SINGLE.replace(b"TIME_SYSTEM = UTC", b"TIME_SYSTEM = TCB")
    eph = read(tcb)
    assert eph.metadata.time_scale is None
    oem = eph.source_native
    assert isinstance(oem, OemFile)
    assert oem.segments[0].meta.time_system == "TCB"


def test_covariance_blocks_are_parsed_onto_the_fidelity_model() -> None:
    oem = read(OEM_COVARIANCE).source_native
    assert isinstance(oem, OemFile)
    covariances = oem.segments[0].covariances
    assert len(covariances) == 1
    cov = covariances[0]
    assert cov.epoch == np.datetime64("2000-01-01T00:00:00.000", "ns")
    assert cov.cov_ref_frame == "RTN"
    assert len(cov.matrix) == 21
    assert cov.matrix[0] == pytest.approx(0.31)
    assert cov.matrix[-1] == pytest.approx(0.51)


def test_odd_whitespace_and_crlf_are_tolerated() -> None:
    messy = (
        b"CCSDS_OEM_VERS=2.0\r\n"
        b"\r\n"
        b"META_START\r\n"
        b"   OBJECT_NAME    =    ODD WHITESPACE SAT   \r\n"
        b"OBJECT_ID = 2001-001A\r\n"
        b"CENTER_NAME = EARTH\r\n"
        b"REF_FRAME = EME2000\r\n"
        b"TIME_SYSTEM = UTC\r\n"
        b"START_TIME = 2001-01-01T00:00:00.000\r\n"
        b"STOP_TIME = 2001-01-01T00:00:00.000\r\n"
        b"META_STOP\r\n"
        b"\r\n"
        b"2001-01-01T00:00:00.000    1.0   2.0    3.0     4.0  5.0   6.0\r\n"
    )
    eph = read(messy)
    assert isinstance(eph, Ephemeris)
    assert eph.metadata.object_name == "ODD WHITESPACE SAT"
    np.testing.assert_allclose(eph.positions[0], (1.0, 2.0, 3.0))


# --- malformed inputs ------------------------------------------------------------------


def test_missing_required_meta_keyword_is_rejected() -> None:
    broken = OEM_SINGLE.replace(b"CENTER_NAME = MARS BARYCENTER\n", b"")
    with pytest.raises(MalformedSourceError, match="missing required keyword"):
        read(broken, format="ccsds-oem")


def test_a_state_line_with_the_wrong_number_of_columns_is_rejected() -> None:
    broken = OEM_SINGLE.replace(
        b"1996-12-18T12:00:00.331 2789.619 -280.045 -1746.755 4.73372 -2.49586 -1.04195\n",
        b"1996-12-18T12:00:00.331 2789.619 -280.045 -1746.755 4.73372\n",
    )
    with pytest.raises(MalformedSourceError, match="epoch plus 6 or 9"):
        read(broken, format="ccsds-oem")


def test_segments_disagreeing_on_frame_are_rejected() -> None:
    # Flip the second segment's frame; concatenation across frames is not supported in v0.1.
    broken = OEM_MULTI.replace(b"REF_FRAME = TOD", b"REF_FRAME = EME2000", 1)
    with pytest.raises(MalformedSourceError, match="disagree on REF_FRAME"):
        read(broken, format="ccsds-oem")


def test_mixed_accel_and_non_accel_lines_are_rejected() -> None:
    broken = OEM_DOY_ACCEL.replace(
        b"2004-100T00:01:00.000 1.1 2.1 3.1 4.1 5.1 6.1 0.11 0.21 0.31\n",
        b"2004-100T00:01:00.000 1.1 2.1 3.1 4.1 5.1 6.1\n",
    )
    with pytest.raises(MalformedSourceError, match="mixes 6-column and 9-column"):
        read(broken, format="ccsds-oem")


def test_a_file_with_no_segment_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="no META_START segment"):
        read(b"CCSDS_OEM_VERS = 2.0\n", format="ccsds-oem")


def test_missing_version_header_is_rejected() -> None:
    no_version = OEM_SINGLE.replace(b"CCSDS_OEM_VERS = 2.0\n", b"")
    with pytest.raises(MalformedSourceError, match="CCSDS_OEM_VERS"):
        read(no_version, format="ccsds-oem")


def test_an_unparseable_epoch_is_rejected() -> None:
    broken = OEM_SINGLE.replace(b"1996-12-18T12:00:00.331 2789.619", b"not-a-date 2789.619")
    with pytest.raises(MalformedSourceError, match="could not parse the CCSDS epoch"):
        read(broken, format="ccsds-oem")


def test_an_unclosed_meta_block_is_rejected() -> None:
    truncated = b"CCSDS_OEM_VERS = 2.0\nMETA_START\nOBJECT_NAME = X\n"
    with pytest.raises(MalformedSourceError, match="not closed with META_STOP"):
        read(truncated, format="ccsds-oem")


def test_a_covariance_matrix_with_too_few_values_is_rejected() -> None:
    broken = OEM_COVARIANCE.replace(b" 0.46 0.47 0.48 0.49 0.50 0.51\n", b" 0.46 0.47 0.48\n")
    with pytest.raises(MalformedSourceError, match="21 lower-triangular values"):
        read(broken, format="ccsds-oem")


def test_a_duplicate_meta_keyword_is_rejected() -> None:
    broken = OEM_SINGLE.replace(
        b"OBJECT_ID = 1996-062A\n", b"OBJECT_ID = 1996-062A\nOBJECT_ID = X\n"
    )
    with pytest.raises(MalformedSourceError, match="duplicate OEM META keyword 'OBJECT_ID'"):
        read(broken, format="ccsds-oem")


def test_a_non_integer_interpolation_degree_is_rejected() -> None:
    broken = OEM_SINGLE.replace(b"INTERPOLATION_DEGREE = 7", b"INTERPOLATION_DEGREE = many")
    with pytest.raises(MalformedSourceError, match="INTERPOLATION_DEGREE must be an integer"):
        read(broken, format="ccsds-oem")


def test_a_non_keyword_line_in_the_meta_block_is_rejected() -> None:
    broken = OEM_SINGLE.replace(
        b"TIME_SYSTEM = UTC\n", b"TIME_SYSTEM = UTC\nthis is not a keyword\n"
    )
    with pytest.raises(MalformedSourceError, match="expected 'KEYWORD = value' in the OEM META"):
        read(broken, format="ccsds-oem")


def test_an_unknown_header_keyword_is_rejected() -> None:
    broken = OEM_SINGLE.replace(b"CCSDS_OEM_VERS = 2.0\n", b"CCSDS_OEM_VERS = 2.0\nMYSTERY = 1\n")
    with pytest.raises(
        MalformedSourceError, match="unexpected keyword 'MYSTERY' in the OEM header"
    ):
        read(broken, format="ccsds-oem")


def test_a_non_keyword_line_in_the_header_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="expected 'KEYWORD = value' in the OEM header"):
        read(b"garbage line\nCCSDS_OEM_VERS = 2.0\n", format="ccsds-oem")


def test_a_non_numeric_state_value_is_rejected() -> None:
    broken = OEM_SINGLE.replace(
        b"1996-12-18T12:00:00.331 2789.619 -280.045 -1746.755 4.73372 -2.49586 -1.04195\n",
        b"1996-12-18T12:00:00.331 2789.619 -280.045 oops 4.73372 -2.49586 -1.04195\n",
    )
    with pytest.raises(MalformedSourceError, match="non-numeric value in the OEM state line"):
        read(broken, format="ccsds-oem")


def test_an_out_of_range_calendar_epoch_is_rejected() -> None:
    broken = OEM_SINGLE.replace(
        b"1996-12-18T12:00:00.331 2789.619", b"1996-99-99T00:00:00.000 2789.619"
    )
    with pytest.raises(MalformedSourceError, match="could not parse the CCSDS epoch"):
        read(broken, format="ccsds-oem")


def test_a_day_of_year_epoch_without_full_time_of_day_is_rejected() -> None:
    broken = OEM_DOY_ACCEL.replace(b"2004-100T00:00:00.000 1.0", b"2004-100T00:00 1.0")
    with pytest.raises(MalformedSourceError, match="could not parse the CCSDS epoch"):
        read(broken, format="ccsds-oem")


def test_trailing_content_after_a_segment_is_rejected() -> None:
    broken = OEM_COVARIANCE + b"\nstray trailing content\n"
    with pytest.raises(MalformedSourceError, match="unexpected content outside an OEM segment"):
        read(broken, format="ccsds-oem")


# --- covariance edge cases -------------------------------------------------------------

OEM_TWO_COVARIANCES = b"""CCSDS_OEM_VERS = 2.0

META_START
OBJECT_NAME = SAT
OBJECT_ID = 2000-000A
CENTER_NAME = EARTH
REF_FRAME = EME2000
TIME_SYSTEM = UTC
START_TIME = 2000-01-01T00:00:00.000
STOP_TIME = 2000-01-01T00:01:00.000
META_STOP
2000-01-01T00:00:00.000 1.0 2.0 3.0 4.0 5.0 6.0

COVARIANCE_START
COMMENT two matrices in one block
EPOCH = 2000-01-01T00:00:00.000
 0.1
 0.0 0.2
 0.0 0.0 0.3
 0.0 0.0 0.0 0.4
 0.0 0.0 0.0 0.0 0.5
 0.0 0.0 0.0 0.0 0.0 0.6
EPOCH = 2000-01-01T00:01:00.000
 1.1
 0.0 1.2
 0.0 0.0 1.3
 0.0 0.0 0.0 1.4
 0.0 0.0 0.0 0.0 1.5
 0.0 0.0 0.0 0.0 0.0 1.6
COVARIANCE_STOP
"""


def test_multiple_covariance_matrices_in_one_block_are_each_parsed() -> None:
    oem = read(OEM_TWO_COVARIANCES).source_native
    assert isinstance(oem, OemFile)
    covariances = oem.segments[0].covariances
    assert len(covariances) == 2
    assert covariances[0].epoch == np.datetime64("2000-01-01T00:00:00.000", "ns")
    assert covariances[1].epoch == np.datetime64("2000-01-01T00:01:00.000", "ns")
    assert covariances[0].comments == ("two matrices in one block",)
    assert covariances[0].matrix[0] == pytest.approx(0.1)
    assert covariances[1].matrix[-1] == pytest.approx(1.6)


def test_an_unexpected_keyword_in_a_covariance_block_is_rejected() -> None:
    broken = OEM_COVARIANCE.replace(b"COV_REF_FRAME = RTN\n", b"BOGUS = 1\n")
    with pytest.raises(
        MalformedSourceError, match="unexpected keyword 'BOGUS' in the OEM COVARIANCE"
    ):
        read(broken, format="ccsds-oem")


def test_a_non_numeric_covariance_value_is_rejected() -> None:
    broken = OEM_COVARIANCE.replace(b" 0.31\n", b" oops\n")
    with pytest.raises(
        MalformedSourceError, match="non-numeric value in the OEM covariance matrix"
    ):
        read(broken, format="ccsds-oem")


def test_covariance_data_with_no_epoch_is_rejected() -> None:
    broken = OEM_COVARIANCE.replace(b"EPOCH = 2000-01-01T00:00:00.000\n", b"")
    with pytest.raises(MalformedSourceError, match="covariance data has no preceding EPOCH"):
        read(broken, format="ccsds-oem")


def test_an_unclosed_covariance_block_is_rejected() -> None:
    broken = OEM_COVARIANCE.replace(b"COVARIANCE_STOP\n", b"")
    with pytest.raises(MalformedSourceError, match="not closed with COVARIANCE_STOP"):
        read(broken, format="ccsds-oem")


def test_a_segment_with_covariance_but_no_states_yields_an_empty_ephemeris() -> None:
    # A covariance-only segment: no ephemeris lines. The canonical ephemeris is empty, but
    # the covariance is still preserved on the fidelity model.
    no_states = OEM_COVARIANCE.replace(b"2000-01-01T00:00:00.000 1.0 2.0 3.0 4.0 5.0 6.0\n", b"")
    eph = read(no_states)
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 0
    oem = eph.source_native
    assert isinstance(oem, OemFile)
    assert len(oem.segments[0].covariances) == 1
