"""The STK attitude (``.a``) reader and writer: parse, fidelity retention, and the three
write tiers (byte-lossless, content-lossless, synthesised) with the no-silent-loss contract.

Samples are authored inline (as in the OEM / STK-ephemeris reader tests): a parser is correct
when it extracts exactly the values the file states, so the file *is* the reference. The
committed golden drives the byte-identical structural round trip. The reader was additionally
validated against real STK output kept out-of-repo (it has no clean licence) — including files
that omit the ``END Attitude`` terminator, the case ``STK_QUAT_NO_END`` covers here.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Attitude,
    MalformedSourceError,
    Metadata,
    StateVector,
    UnsupportedConversionError,
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.stk_attitude import StkAttitudeFile, read_stk_attitude
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.stk_attitude import write_stk_attitude

GOLDEN = Path(__file__).parent / "data" / "stk" / "golden_roundtrip.a"

# A scalar-last quaternion attitude with a comment and the full STK header. ScenarioEpoch
# 12:00:00 + offsets 0/60/120 s → 12:00 / 12:01 / 12:02. The 4th component is the scalar.
STK_QUAT = b"""stk.v.11.0
# WrittenBy STK 11

BEGIN Attitude

NumberOfAttitudePoints 3
ScenarioEpoch 01 Jan 2000 12:00:00.000
CentralBody Earth
CoordinateAxes J2000
BlockingFactor 20
InterpolationOrder 1

AttitudeTimeQuaternions

0.0 0.0 0.0 0.0 1.0
60.0 0.0 0.0 0.5 0.8660254037844386
120.0 0.0 0.0 0.8660254037844386 0.5

END Attitude
"""

# Real STK output routinely omits END Attitude — the data section runs to EOF. The reader
# tolerates it (the AGI spec calls END Attitude required; the wild disagrees).
STK_QUAT_NO_END = b"""stk.v.5.0
BEGIN Attitude
NumberOfAttitudePoints 2
ScenarioEpoch 01 Jan 2000 12:00:00.000
CentralBody Earth
CoordinateAxes J2000
AttitudeTimeQuaternions
0.0 0.0 0.0 0.0 1.0
60.0 0.0 0.0 0.5 0.8660254037844386
"""

# The scalar-first quaternion section (QC Q1 Q2 Q3); the reader reorders to canonical
# scalar-last, and a content-lossless write re-emits it scalar-first under its own section.
STK_QUAT_SCALAR_FIRST = b"""stk.v.11.0
BEGIN Attitude
ScenarioEpoch 01 Jan 2000 12:00:00.000
CentralBody Earth
CoordinateAxes J2000
AttitudeTimeQuatScalarFirst
0.0 1.0 0.0 0.0 0.0
60.0 0.8660254037844386 0.0 0.0 0.5
END Attitude
"""

# Euler angles need a Sequence keyword naming the rotation order (313 = ZXZ), in degrees.
STK_EULER = b"""stk.v.11.0
BEGIN Attitude
ScenarioEpoch 01 Jan 2000 12:00:00.000
CentralBody Earth
CoordinateAxes J2000
Sequence 313
AttitudeTimeEulerAngles
0.0 0.0 0.0 0.0
60.0 30.0 0.0 0.0
END Attitude
"""


def _full_attitude() -> Attitude:
    """A synthesised quaternion attitude carrying every STK-required field (no source_native)."""
    return Attitude(
        metadata=Metadata(central_body="Earth", time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00", "2024-01-01T00:01:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.5, 0.8660254037844386]]),
        frame_a="J2000",
    )


# --- reader ----------------------------------------------------------------------------


def test_reader_is_registered_for_stk_attitude() -> None:
    assert get_reader("stk-attitude") is read_stk_attitude


def test_stk_attitude_signature_is_detected_before_reading() -> None:
    # The banner is shared with stk-ephemeris; BEGIN Attitude routes to stk-attitude.
    assert detect_format(STK_QUAT) == "stk-attitude"


def test_stk_ephemeris_and_attitude_signatures_do_not_collide() -> None:
    # Tightening _sig_stk to require BEGIN Ephemeris keeps the two STK formats disjoint.
    ephem = b"stk.v.11.0\nBEGIN Ephemeris\nScenarioEpoch 21545.0\nEphemerisTimePosVel\n"
    assert detect_format(ephem) == "stk-ephemeris"
    assert detect_format(STK_QUAT) == "stk-attitude"


def test_read_returns_an_attitude_with_the_quaternion_records() -> None:
    att = read(STK_QUAT)  # no format= : exercises auto-detection routing to this reader
    assert isinstance(att, Attitude)
    assert att.attitude_type == "QUATERNION"
    assert len(att) == 3
    np.testing.assert_allclose(att.records[0], (0.0, 0.0, 0.0, 1.0))
    np.testing.assert_allclose(att.records[-1], (0.0, 0.0, 0.8660254037844386, 0.5))
    assert att.epochs[0] == np.datetime64("2000-01-01T12:00:00", "ns")
    assert att.epochs[-1] == np.datetime64("2000-01-01T12:02:00", "ns")


def test_read_tags_the_spine_and_reference_frame() -> None:
    att = read(STK_QUAT)
    assert isinstance(att, Attitude)
    assert att.frame_a == "J2000"  # CoordinateAxes -> the named reference frame
    assert att.frame_b is None  # STK leaves the body frame implicit
    assert att.euler_rot_seq is None
    assert att.metadata.central_body == "Earth"
    assert att.metadata.time_scale == "UTC"  # a .a declares no scale; UTC is STK's default
    assert att.metadata.provenance is not None
    assert att.metadata.provenance.source_format == "stk-attitude"


def test_scalar_first_quaternions_are_reordered_to_scalar_last() -> None:
    att = read(STK_QUAT_SCALAR_FIRST)
    assert isinstance(att, Attitude)
    # File row 0 is "1 0 0 0" (scalar first); canonical scalar-last is "0 0 0 1".
    np.testing.assert_allclose(att.records[0], (0.0, 0.0, 0.0, 1.0))
    np.testing.assert_allclose(att.records[1], (0.0, 0.0, 0.5, 0.8660254037844386))


def test_euler_angles_carry_the_sequence() -> None:
    att = read(STK_EULER)
    assert isinstance(att, Attitude)
    assert att.attitude_type == "EULER_ANGLE"
    assert att.euler_rot_seq == "313"
    np.testing.assert_allclose(att.records[1], (30.0, 0.0, 0.0))


def test_missing_end_attitude_is_tolerated() -> None:
    # Real STK output omits END Attitude; the data section runs to EOF.
    att = read(STK_QUAT_NO_END)
    assert isinstance(att, Attitude)
    assert len(att) == 2
    stk = att.source_native
    assert isinstance(stk, StkAttitudeFile)
    assert stk.has_end_marker is False


def test_a_section_with_no_records_reads_as_an_empty_attitude() -> None:
    empty = (
        b"stk.v.11.0\nBEGIN Attitude\nScenarioEpoch 01 Jan 2000 12:00:00.000\n"
        b"CentralBody Earth\nCoordinateAxes J2000\nAttitudeTimeQuaternions\nEND Attitude\n"
    )
    att = read(empty, format="stk-attitude")
    assert isinstance(att, Attitude)
    assert len(att) == 0
    assert att.records.shape == (0, 4)


def test_source_native_retains_the_full_fidelity_model() -> None:
    att = read(STK_QUAT)
    stk = att.source_native
    assert isinstance(stk, StkAttitudeFile)
    assert stk.format_name == "stk-attitude"
    assert stk.version == "stk.v.11.0"
    assert stk.header_comments == ("# WrittenBy STK 11",)
    assert stk.data_section == "AttitudeTimeQuaternions"
    assert stk.has_end_marker is True
    assert stk.scenario_epoch == np.datetime64("2000-01-01T12:00:00", "ns")
    # Every meta keyword survives verbatim, including the ones the canonical form ignores.
    assert stk.meta_value("NumberOfAttitudePoints") == "3"
    assert stk.meta_value("BlockingFactor") == "20"
    assert stk.meta_value("ScenarioEpoch") == "01 Jan 2000 12:00:00.000"


# --- reader: malformed inputs ----------------------------------------------------------


def test_an_empty_file_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="version banner is missing"):
        read(b"   \n\n", format="stk-attitude")


def test_a_missing_version_banner_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="expected the stk"):
        read(b"garbage line\nstk.v.11.0\n", format="stk-attitude")


def test_begin_before_the_banner_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="BEGIN Attitude before the stk"):
        read(b"BEGIN Attitude\n", format="stk-attitude")


def test_a_duplicate_banner_is_rejected() -> None:
    broken = STK_QUAT.replace(b"stk.v.11.0\n", b"stk.v.11.0\nstk.v.12.0\n", 1)
    with pytest.raises(MalformedSourceError, match="duplicate stk"):
        read(broken, format="stk-attitude")


def test_a_missing_begin_block_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="'BEGIN Attitude' block is missing"):
        read(b"stk.v.11.0\n", format="stk-attitude")


def test_a_missing_scenario_epoch_is_rejected() -> None:
    broken = STK_QUAT.replace(b"ScenarioEpoch 01 Jan 2000 12:00:00.000\n", b"")
    with pytest.raises(MalformedSourceError, match="missing the required 'ScenarioEpoch'"):
        read(broken, format="stk-attitude")


def test_a_missing_data_section_is_rejected() -> None:
    no_data = b"stk.v.11.0\nBEGIN Attitude\nScenarioEpoch 21545.0\nEND Attitude\n"
    with pytest.raises(MalformedSourceError, match="has no data section"):
        read(no_data, format="stk-attitude")


def test_an_unsupported_attitude_section_is_rejected() -> None:
    broken = STK_QUAT.replace(b"AttitudeTimeQuaternions", b"AttitudeTimeDCM")
    with pytest.raises(MalformedSourceError, match="unsupported STK attitude section"):
        read(broken, format="stk-attitude")


def test_euler_without_a_sequence_is_rejected() -> None:
    broken = STK_EULER.replace(b"Sequence 313\n", b"")
    with pytest.raises(MalformedSourceError, match="requires a 'Sequence'"):
        read(broken, format="stk-attitude")


def test_a_record_with_the_wrong_number_of_columns_is_rejected() -> None:
    broken = STK_QUAT.replace(b"0.0 0.0 0.0 0.0 1.0\n", b"0.0 0.0 0.0 1.0\n")
    with pytest.raises(MalformedSourceError, match="expected an offset plus 4 QUATERNION"):
        read(broken, format="stk-attitude")


def test_a_non_numeric_record_value_is_rejected() -> None:
    broken = STK_QUAT.replace(b"0.0 0.0 0.0 0.0 1.0\n", b"0.0 oops 0.0 0.0 1.0\n")
    with pytest.raises(MalformedSourceError, match="non-numeric value in the STK attitude record"):
        read(broken, format="stk-attitude")


def test_content_after_end_attitude_is_rejected() -> None:
    broken = STK_QUAT + b"stray trailing content\n"
    with pytest.raises(MalformedSourceError, match="content after END Attitude"):
        read(broken, format="stk-attitude")


# --- writer: byte-lossless (opt-in) and content-lossless (default) ---------------------


def test_writer_is_registered_for_stk_attitude() -> None:
    assert get_writer("stk-attitude") is write_stk_attitude


def test_retain_source_round_trip_is_byte_identical() -> None:
    att = read(STK_QUAT, retain_source=True)
    assert isinstance(att, Attitude)
    assert isinstance(att.source_native, StkAttitudeFile)
    assert att.source_native.raw_bytes == STK_QUAT
    assert write_stk_attitude(att) == STK_QUAT


def test_retain_source_round_trip_is_byte_identical_without_end_marker() -> None:
    # The byte-identical tier echoes the source, so a no-END file re-emits END-less verbatim.
    att = read(STK_QUAT_NO_END, retain_source=True)
    assert write_stk_attitude(att) == STK_QUAT_NO_END


def test_default_round_trip_preserves_content() -> None:
    att = read(STK_QUAT_NO_END)  # no retained bytes
    out = write_stk_attitude(att)
    assert read(out) == att  # content equal on re-read


def test_golden_round_trip_is_byte_identical() -> None:
    golden = GOLDEN.read_bytes()
    att = read(golden)
    assert isinstance(att, Attitude)
    assert write_stk_attitude(att) == golden


def test_scalar_first_round_trips_under_its_own_section() -> None:
    att = read(STK_QUAT_SCALAR_FIRST)
    out = write_stk_attitude(att)
    # The content-lossless write re-emits the scalar-first section it was read from ...
    assert b"AttitudeTimeQuatScalarFirst" in out
    # ... and re-reading recovers the same canonical (scalar-last) records.
    assert read(out) == att


# --- writer: synthesised / cross-format ------------------------------------------------


def test_synthesised_write_is_valid_and_round_trips_when_complete() -> None:
    att = _full_attitude()
    reread = read(write_stk_attitude(att))
    assert isinstance(reread, Attitude)
    assert reread.attitude_type == "QUATERNION"
    assert reread.frame_a == "J2000"
    assert reread.metadata.central_body == "Earth"
    np.testing.assert_allclose(reread.records, att.records)
    np.testing.assert_array_equal(reread.epochs, att.epochs)


def test_synthesised_write_warns_for_each_missing_required_field() -> None:
    att = Attitude(
        metadata=Metadata(time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0]]),
    )  # no central_body, no frame_a
    with pytest.warns(Warning) as caught:
        out = write_stk_attitude(att)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert warned == {"CentralBody", "CoordinateAxes"}
    assert b"CentralBody UNKNOWN" in out
    assert b"CoordinateAxes UNKNOWN" in out


def test_synthesised_euler_without_a_sequence_warns() -> None:
    att = Attitude(
        metadata=Metadata(central_body="Earth", time_scale="UTC"),
        attitude_type="EULER_ANGLE",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0]]),
        frame_a="J2000",
    )  # EULER_ANGLE with no euler_rot_seq
    with pytest.warns(Warning) as caught:
        out = write_stk_attitude(att)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "Sequence" in warned
    assert b"Sequence UNKNOWN" in out


def test_synthesised_write_of_an_empty_attitude_warns_for_the_scenario_epoch() -> None:
    att = Attitude(
        metadata=Metadata(central_body="Earth", time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.empty(0, dtype="datetime64[ns]"),
        records=np.empty((0, 4)),
        frame_a="J2000",
    )
    with pytest.warns(Warning) as caught:
        out = write_stk_attitude(att)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert warned == {"ScenarioEpoch"}
    # The sentinel ScenarioEpoch keeps the file structurally valid, so it re-reads as an empty
    # attitude rather than a placeholder STK cannot parse.
    reread = read(out)
    assert isinstance(reread, Attitude)
    assert len(reread) == 0


def test_unrepresentable_fields_warn_when_present() -> None:
    # An attitude that names its object and body frame loses those crossing into a .a.
    att = Attitude(
        metadata=Metadata(object_name="SAT", object_id="2024-001A", central_body="Earth"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0]]),
        frame_a="J2000",
        frame_b="SC_BODY",
    )
    with pytest.warns(Warning) as caught:
        write_stk_attitude(att)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert {"OBJECT_NAME", "OBJECT_ID", "REF_FRAME_B"} <= warned


def test_a_spin_attitude_cannot_be_written() -> None:
    att = Attitude(
        metadata=Metadata(central_body="Earth"),
        attitude_type="SPIN",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[10.0, 20.0, 30.0, 1.0]]),
        frame_a="J2000",
    )
    with pytest.raises(UnsupportedConversionError, match="stk-attitude"):
        write_stk_attitude(att)


def test_convert_to_an_attitude_target_is_a_same_form_passthrough() -> None:
    # stk-attitude prefers the attitude form, so routing an Attitude to it (or to another
    # attitude target such as ccsds-aem) is a no-op pass-through — the conversion-matrix cell.
    att = read(STK_QUAT)
    assert convert(att, to="stk-attitude") is att
    assert convert(att, to="ccsds-aem") is att


def test_non_attitude_input_is_rejected() -> None:
    state = StateVector(
        metadata=Metadata(reference_frame="J2000"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 0.0, 0.0]),
        velocity=np.array([0.0, 7.5, 0.0]),
    )
    with pytest.raises(UnsupportedConversionError, match="stk-attitude"):
        write_stk_attitude(state)


# --- the no-silent-loss contract -------------------------------------------------------


def test_same_format_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    att = read(GOLDEN.read_bytes())
    assert_no_silent_loss(lambda: write_stk_attitude(att), loses=False)


def test_complete_synthesised_write_loses_nothing(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    assert_no_silent_loss(lambda: write_stk_attitude(_full_attitude()), loses=False)


def test_synthesised_write_with_missing_fields_warns(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    att = Attitude(
        metadata=Metadata(time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0]]),
    )
    assert_no_silent_loss(lambda: write_stk_attitude(att), loses=True)


def test_aem_attitude_to_stk_attitude_warns_for_dropped_identity(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    # An AEM names the object and both frames; crossing into a .a drops what STK cannot hold.
    aem = read(Path(__file__).parent / "data" / "aem" / "golden_aem.aem")
    assert isinstance(aem, Attitude)
    assert_no_silent_loss(lambda: write_stk_attitude(aem), loses=True)


# --- public write() surface ------------------------------------------------------------


def test_public_write_to_file_is_byte_identical_with_retained_source(tmp_path: Path) -> None:
    att = read(STK_QUAT, retain_source=True)
    destination = tmp_path / "out.a"
    write(att, destination)
    assert destination.read_bytes() == STK_QUAT
