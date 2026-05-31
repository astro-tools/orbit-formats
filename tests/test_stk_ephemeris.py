"""The STK ephemeris (``.e``) reader and writer: parse, fidelity retention, and the three
write tiers (byte-lossless, content-lossless, synthesised) with the no-silent-loss contract.

Samples are authored inline (as in the OEM reader's tests): a parser is correct when it
extracts exactly the values the file states, so the file *is* the reference. The committed
golden corpus drives the byte-identical structural round trip.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Ephemeris,
    MalformedSourceError,
    Metadata,
    StateVector,
    UnsupportedConversionError,
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.stk_ephemeris import StkEphemerisFile, read_stk_ephemeris
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.stk_ephemeris import write_stk_ephemeris

GOLDEN = Path(__file__).parent / "data" / "stk" / "golden_roundtrip.e"

# A position/velocity ephemeris with a Gregorian ScenarioEpoch, a comment, and the full
# interpolation meta. ScenarioEpoch 12:00:00 + offsets 0/60/120 s → 12:00/12:01/12:02.
STK_POS_VEL = b"""stk.v.11.0
# WrittenBy GMAT R2026a

BEGIN Ephemeris

NumberOfEphemerisPoints 3
ScenarioEpoch 01 Jan 2000 12:00:00.000
CentralBody Earth
CoordinateSystem J2000
InterpolationMethod Lagrange
InterpolationSamplesM1 7
DistanceUnit Kilometers

EphemerisTimePosVel

0.0 7000.0 0.0 0.0 0.0 7.5 0.0
60.0 6999.0 449.0 0.0 -0.75 7.49 0.0
120.0 6997.0 898.0 0.0 -1.5 7.48 0.0

END Ephemeris
"""

# A position/velocity/acceleration ephemeris (the …Acc data section) — acceleration is kept
# on the fidelity model only, never down-projected into the canonical Ephemeris.
STK_POS_VEL_ACC = b"""stk.v.11.0

BEGIN Ephemeris

ScenarioEpoch 01 Jan 2000 12:00:00.000
CentralBody Earth
CoordinateSystem ICRF

EphemerisTimePosVelAcc

0.0 1.0 2.0 3.0 4.0 5.0 6.0 0.1 0.2 0.3
60.0 1.1 2.1 3.1 4.1 5.1 6.1 0.11 0.21 0.31

END Ephemeris
"""

# A numeric ScenarioEpoch — a GMAT Modified Julian Date. MJD 21545.0 is J2000.
STK_MODJULIAN = b"""stk.v.11.0
BEGIN Ephemeris
ScenarioEpoch 21545.0
CentralBody Earth
CoordinateSystem Fixed
EphemerisTimePosVel
0.0 7000.0 0.0 0.0 0.0 7.5 0.0
END Ephemeris
"""

# Deliberately messy: CRLF endings, padded columns, multi-space meta. A byte-identical
# re-emit is only possible from retained source; the structural serialiser canonicalises it.
MESSY_STK = (
    b"stk.v.11.0\r\n"
    b"\r\n"
    b"# messy but valid\r\n"
    b"BEGIN Ephemeris\r\n"
    b"ScenarioEpoch    01 Jan 2000 12:00:00.000\r\n"
    b"CentralBody      Earth\r\n"
    b"CoordinateSystem J2000\r\n"
    b"EphemerisTimePosVel\r\n"
    b"0.0    7000.0   0.0   0.0    0.0  7.5  0.0\r\n"
    b"60.0   6999.0   60.0  0.0   -0.1  7.5  0.0\r\n"
    b"END Ephemeris\r\n"
)


def _full_ephemeris() -> Ephemeris:
    """A synthesised ephemeris carrying every STK-required field (no source_native)."""
    return Ephemeris(
        metadata=Metadata(central_body="Earth", reference_frame="J2000", time_scale="UTC"),
        epochs=np.array(["2024-01-01T00:00:00", "2024-01-01T00:01:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0], [6999.0, 60.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0], [-0.1, 7.5, 0.0]]),
    )


# --- reader ----------------------------------------------------------------------------


def test_reader_is_registered_for_stk_ephemeris() -> None:
    assert get_reader("stk-ephemeris") is read_stk_ephemeris


def test_stk_signature_is_detected_before_reading() -> None:
    # The auto-detection contract: the stk.v.X.Y banner routes to the stk-ephemeris format id.
    assert detect_format(STK_POS_VEL) == "stk-ephemeris"


def test_read_returns_an_ephemeris_with_the_state_records() -> None:
    eph = read(STK_POS_VEL)  # no format= : exercises auto-detection routing to this reader
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 3
    np.testing.assert_allclose(eph.positions[0], (7000.0, 0.0, 0.0))
    np.testing.assert_allclose(eph.velocities[0], (0.0, 7.5, 0.0))
    np.testing.assert_allclose(eph.positions[-1], (6997.0, 898.0, 0.0))
    assert eph.epochs[0] == np.datetime64("2000-01-01T12:00:00", "ns")
    assert eph.epochs[-1] == np.datetime64("2000-01-01T12:02:00", "ns")


def test_read_tags_the_spine_from_the_meta() -> None:
    md = read(STK_POS_VEL).metadata
    assert md.reference_frame == "J2000"
    assert md.central_body == "Earth"
    assert md.time_scale == "UTC"  # the .e declares no scale; UTC is GMAT's STK-writer default
    assert md.provenance is not None
    assert md.provenance.source_format == "stk-ephemeris"


def test_read_carries_the_interpolation_hint() -> None:
    eph = read(STK_POS_VEL)
    assert isinstance(eph, Ephemeris)
    assert eph.interpolation == "Lagrange"
    assert eph.interpolation_degree == 7


def test_source_native_retains_the_full_fidelity_model() -> None:
    eph = read(STK_POS_VEL)
    stk = eph.source_native
    assert isinstance(stk, StkEphemerisFile)
    assert stk.format_name == "stk-ephemeris"
    assert stk.version == "stk.v.11.0"
    assert stk.header_comments == ("# WrittenBy GMAT R2026a",)
    assert stk.data_section == "EphemerisTimePosVel"
    assert stk.scenario_epoch == np.datetime64("2000-01-01T12:00:00", "ns")
    # Every meta keyword survives verbatim, including the ones the canonical form ignores.
    assert stk.meta_value("NumberOfEphemerisPoints") == "3"
    assert stk.meta_value("DistanceUnit") == "Kilometers"
    assert stk.meta_value("ScenarioEpoch") == "01 Jan 2000 12:00:00.000"
    assert stk.accelerations is None


def test_pos_vel_acc_acceleration_is_retained_on_the_fidelity_model_only() -> None:
    eph = read(STK_POS_VEL_ACC)
    assert isinstance(eph, Ephemeris)
    # The canonical Ephemeris holds position and velocity only.
    np.testing.assert_allclose(eph.positions[0], (1.0, 2.0, 3.0))
    np.testing.assert_allclose(eph.velocities[0], (4.0, 5.0, 6.0))
    stk = eph.source_native
    assert isinstance(stk, StkEphemerisFile)
    assert stk.data_section == "EphemerisTimePosVelAcc"
    assert stk.accelerations is not None
    np.testing.assert_allclose(stk.accelerations, [(0.1, 0.2, 0.3), (0.11, 0.21, 0.31)])


def test_numeric_scenario_epoch_is_read_as_a_gmat_modjulian_date() -> None:
    eph = read(STK_MODJULIAN)
    assert isinstance(eph, Ephemeris)
    assert eph.epochs[0] == np.datetime64("2000-01-01T12:00:00", "ns")
    assert eph.metadata.reference_frame == "Fixed"


def test_to_dataframe_carries_the_stk_spine() -> None:
    eph = read(STK_POS_VEL)
    assert isinstance(eph, Ephemeris)
    df = eph.to_dataframe()
    assert df.attrs["coordinate_system"] == "J2000"
    assert df.attrs["central_body"] == "Earth"
    assert df.attrs["time_scale"] == "UTC"
    assert df.attrs["interpolation"] == "Lagrange"
    assert len(df) == 3


# --- reader: malformed inputs ----------------------------------------------------------


def test_an_empty_file_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="version banner is missing"):
        read(b"   \n\n", format="stk-ephemeris")


def test_a_missing_version_banner_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="expected the stk"):
        read(b"garbage line\nstk.v.11.0\n", format="stk-ephemeris")


def test_begin_before_the_banner_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="BEGIN Ephemeris before the stk"):
        read(b"BEGIN Ephemeris\n", format="stk-ephemeris")


def test_a_duplicate_banner_is_rejected() -> None:
    broken = STK_POS_VEL.replace(b"stk.v.11.0\n", b"stk.v.11.0\nstk.v.12.0\n", 1)
    with pytest.raises(MalformedSourceError, match="duplicate stk"):
        read(broken, format="stk-ephemeris")


def test_a_missing_begin_block_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="'BEGIN Ephemeris' block is missing"):
        read(b"stk.v.11.0\n", format="stk-ephemeris")


def test_a_missing_scenario_epoch_is_rejected() -> None:
    broken = STK_POS_VEL.replace(b"ScenarioEpoch 01 Jan 2000 12:00:00.000\n", b"")
    with pytest.raises(MalformedSourceError, match="missing the required 'ScenarioEpoch'"):
        read(broken, format="stk-ephemeris")


def test_a_missing_data_section_is_rejected() -> None:
    no_data = b"stk.v.11.0\nBEGIN Ephemeris\nScenarioEpoch 21545.0\nEND Ephemeris\n"
    with pytest.raises(MalformedSourceError, match="has no data section"):
        read(no_data, format="stk-ephemeris")


def test_an_unsupported_data_section_is_rejected() -> None:
    broken = STK_POS_VEL.replace(b"EphemerisTimePosVel", b"EphemerisTimePos")
    with pytest.raises(MalformedSourceError, match="unsupported STK data section"):
        read(broken, format="stk-ephemeris")


def test_a_record_with_the_wrong_number_of_columns_is_rejected() -> None:
    broken = STK_POS_VEL.replace(b"0.0 7000.0 0.0 0.0 0.0 7.5 0.0\n", b"0.0 7000.0 0.0 0.0 0.0\n")
    with pytest.raises(MalformedSourceError, match="expected 7 columns"):
        read(broken, format="stk-ephemeris")


def test_a_non_numeric_record_value_is_rejected() -> None:
    broken = STK_POS_VEL.replace(
        b"0.0 7000.0 0.0 0.0 0.0 7.5 0.0\n", b"0.0 7000.0 oops 0.0 0.0 7.5 0.0\n"
    )
    with pytest.raises(MalformedSourceError, match="non-numeric value in the STK data record"):
        read(broken, format="stk-ephemeris")


def test_a_malformed_gregorian_scenario_epoch_is_rejected() -> None:
    broken = STK_POS_VEL.replace(b"01 Jan 2000 12:00:00.000", b"01 Foo 2000 12:00:00.000")
    with pytest.raises(MalformedSourceError, match="could not parse the STK ScenarioEpoch"):
        read(broken, format="stk-ephemeris")


def test_a_non_keyword_meta_line_is_rejected() -> None:
    broken = STK_POS_VEL.replace(b"CentralBody Earth\n", b"LoneToken\n")
    with pytest.raises(MalformedSourceError, match="expected an STK 'KEY VALUE' meta line"):
        read(broken, format="stk-ephemeris")


def test_content_after_end_ephemeris_is_rejected() -> None:
    broken = STK_POS_VEL + b"stray trailing content\n"
    with pytest.raises(MalformedSourceError, match="content after END Ephemeris"):
        read(broken, format="stk-ephemeris")


def test_a_non_integer_interpolation_samples_is_rejected() -> None:
    broken = STK_POS_VEL.replace(b"InterpolationSamplesM1 7", b"InterpolationSamplesM1 many")
    with pytest.raises(MalformedSourceError, match="InterpolationSamplesM1 must be an integer"):
        read(broken, format="stk-ephemeris")


# --- writer: byte-lossless (opt-in) and content-lossless (default) ---------------------


def test_writer_is_registered_for_stk_ephemeris() -> None:
    assert get_writer("stk-ephemeris") is write_stk_ephemeris


def test_retain_source_round_trip_is_byte_identical() -> None:
    eph = read(MESSY_STK, retain_source=True)
    assert isinstance(eph, Ephemeris)
    assert isinstance(eph.source_native, StkEphemerisFile)
    assert eph.source_native.raw_bytes == MESSY_STK
    assert write_stk_ephemeris(eph) == MESSY_STK


def test_default_read_retains_no_bytes() -> None:
    eph = read(MESSY_STK)
    assert isinstance(eph.source_native, StkEphemerisFile)
    assert eph.source_native.raw_bytes is None


def test_default_round_trip_reformats_but_preserves_content() -> None:
    eph = read(MESSY_STK)
    out = write_stk_ephemeris(eph)
    # The structural serialiser canonicalises formatting, so the bytes change ...
    assert out != MESSY_STK
    # ... but no orbital content does: the re-read canonical object is equal.
    assert read(out) == eph


def test_golden_round_trip_is_byte_identical() -> None:
    golden = GOLDEN.read_bytes()
    eph = read(golden)
    assert isinstance(eph, Ephemeris)
    assert write_stk_ephemeris(eph) == golden


def test_pos_vel_acc_round_trips_content_losslessly() -> None:
    eph = read(STK_POS_VEL_ACC)
    reread = read(write_stk_ephemeris(eph))
    before, after = eph.source_native, reread.source_native
    assert isinstance(before, StkEphemerisFile)
    assert isinstance(after, StkEphemerisFile)
    # The acceleration columns survive the structural round trip on the fidelity model.
    assert after.accelerations is not None and before.accelerations is not None
    np.testing.assert_array_equal(after.accelerations, before.accelerations)
    assert after.data_section == "EphemerisTimePosVelAcc"


# --- writer: synthesised / cross-format ------------------------------------------------


def test_synthesised_write_is_valid_and_round_trips_when_complete() -> None:
    eph = _full_ephemeris()
    reread = read(write_stk_ephemeris(eph))
    assert isinstance(reread, Ephemeris)
    assert reread.metadata.reference_frame == "J2000"
    assert reread.metadata.central_body == "Earth"
    assert reread.metadata.time_scale == "UTC"
    np.testing.assert_allclose(reread.positions, eph.positions)
    np.testing.assert_allclose(reread.velocities, eph.velocities)
    np.testing.assert_array_equal(reread.epochs, eph.epochs)


def test_synthesised_write_warns_for_each_missing_required_field() -> None:
    eph = Ephemeris(
        metadata=Metadata(time_scale="UTC"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.warns(Warning) as caught:
        out = write_stk_ephemeris(eph)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    # central_body and reference_frame are absent; ScenarioEpoch comes from the epoch.
    assert warned == {"CentralBody", "CoordinateSystem"}
    assert b"CentralBody UNKNOWN" in out
    assert b"CoordinateSystem UNKNOWN" in out


def test_synthesised_write_of_an_empty_ephemeris_warns_for_the_scenario_epoch() -> None:
    eph = Ephemeris(
        metadata=Metadata(central_body="Earth", reference_frame="J2000", time_scale="UTC"),
        epochs=np.empty(0, dtype="datetime64[ns]"),
        positions=np.empty((0, 3)),
        velocities=np.empty((0, 3)),
    )
    with pytest.warns(Warning) as caught:
        write_stk_ephemeris(eph)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert warned == {"ScenarioEpoch"}


def test_convert_to_an_ephemeris_target_is_a_same_form_passthrough() -> None:
    # stk-ephemeris prefers the ephemeris form, so routing an Ephemeris to it (or to another
    # ephemeris target such as ccsds-oem) is a no-op pass-through — the conversion-matrix cell.
    eph = read(STK_POS_VEL)
    assert convert(eph, to="stk-ephemeris") is eph
    assert convert(eph, to="ccsds-oem") is eph


def test_non_ephemeris_input_is_rejected() -> None:
    state = StateVector(
        metadata=Metadata(reference_frame="J2000"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 0.0, 0.0]),
        velocity=np.array([0.0, 7.5, 0.0]),
    )
    with pytest.raises(UnsupportedConversionError, match="stk-ephemeris"):
        write_stk_ephemeris(state)


# --- the no-silent-loss contract -------------------------------------------------------


def test_same_format_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    eph = read(GOLDEN.read_bytes())
    assert_no_silent_loss(lambda: write_stk_ephemeris(eph), loses=False)


def test_complete_synthesised_write_loses_nothing(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    assert_no_silent_loss(lambda: write_stk_ephemeris(_full_ephemeris()), loses=False)


def test_synthesised_write_with_missing_fields_warns(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    eph = Ephemeris(
        metadata=Metadata(time_scale="UTC"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    assert_no_silent_loss(lambda: write_stk_ephemeris(eph), loses=True)


# --- public write() surface ------------------------------------------------------------


def test_public_write_to_file_is_byte_identical_with_retained_source(tmp_path: Path) -> None:
    eph = read(MESSY_STK, retain_source=True)
    destination = tmp_path / "out.e"
    write(eph, destination)
    assert destination.read_bytes() == MESSY_STK
