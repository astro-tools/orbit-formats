"""The CCSDS OCM (Orbit Comprehensive Message) KVN reader and writer.

``golden_ocm.ocm`` exercises the orbit-relevant blocks the definition of done calls for — a
Cartesian trajectory, a covariance history, and a maneuver — alongside the physical,
perturbations, OD, and user-defined blocks the canonical ephemeris cannot represent. The
Cartesian trajectory is adapted into the canonical :class:`Ephemeris`; every block survives on
the :class:`OcmFile` ``source_native`` so a same-format write stays lossless.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Ephemeris,
    LossyConversionWarning,
    MalformedSourceError,
    Metadata,
    Provenance,
    convert,
    read,
    write,
)
from orbit_formats.readers.ccsds_ocm import OcmFile, Quantity
from orbit_formats.writers.ocm import write_ocm

DATA = Path(__file__).parent / "data" / "ocm"
GOLDEN_KVN = DATA / "golden_ocm.ocm"

# A trajectory block whose TRAJ_TYPE is not Cartesian: carried faithfully on the fidelity
# model, but contributing no states to the canonical ephemeris.
_OCM_KEPLERIAN = b"""CCSDS_OCM_VERS = 3.0
ORIGINATOR = ASTRO-TOOLS

META_START
TIME_SYSTEM = UTC
EPOCH_TZERO = 2024-01-01T00:00:00
META_STOP

TRAJ_START
CENTER_NAME = EARTH
TRAJ_REF_FRAME = EME2000
TRAJ_TYPE = KEPLERIAN
0.0 6800.0 0.001 51.6 247.0 130.0 325.0
TRAJ_STOP
"""


# A man block whose composition carries duration, mass change, and m/s Δv across two manLines —
# exercising MAN_DURA / DELTA_MASS extraction, the m/s → km/s scaling, and one record per line.
_OCM_MANEUVERS = b"""CCSDS_OCM_VERS = 3.0
ORIGINATOR = ASTRO-TOOLS

META_START
TIME_SYSTEM = UTC
EPOCH_TZERO = 2024-01-01T00:00:00
META_STOP

TRAJ_START
CENTER_NAME = EARTH
TRAJ_REF_FRAME = EME2000
TRAJ_TYPE = CARTPV
0.0 7000.0 0.0 0.0 0.0 7.5 0.0
TRAJ_STOP

MAN_START
MAN_ID = MAN-1
MAN_DEVICE_ID = THR-1
MAN_REF_FRAME = RTN
DC_TYPE = TIME
MAN_COMPOSITION = TIME_RELATIVE,MAN_DURA,DELTA_MASS,DV_X,DV_Y,DV_Z
MAN_UNITS = s,kg,m/s,m/s,m/s
60.0 30.0 -1.5 10.0 0.0 0.0
120.0 0.0 -0.5 0.0 5.0 0.0
MAN_STOP
"""

# A man block timed against an absolute epoch whose composition carries no Δv (only thrust, which
# the canonical record does not model) and no MAN_UNITS — the record still places the burn in time.
_OCM_ABSOLUTE_NO_DV = b"""CCSDS_OCM_VERS = 3.0
ORIGINATOR = ASTRO-TOOLS

META_START
TIME_SYSTEM = UTC
EPOCH_TZERO = 2024-01-01T00:00:00
META_STOP

TRAJ_START
CENTER_NAME = EARTH
TRAJ_REF_FRAME = EME2000
TRAJ_TYPE = CARTPV
0.0 7000.0 0.0 0.0 0.0 7.5 0.0
TRAJ_STOP

MAN_START
MAN_ID = MAN-1
MAN_DEVICE_ID = THR-1
MAN_REF_FRAME = RTN
DC_TYPE = TIME
MAN_COMPOSITION = TIME_ABSOLUTE,THR_X,THR_Y,THR_Z
2024-01-01T02:00:00 0.5 0.0 0.0
MAN_STOP
"""


def _full_ephemeris() -> Ephemeris:
    """A synthesised ephemeris carrying every field the OCM writer needs without a warning."""
    return Ephemeris(
        metadata=Metadata(
            object_name="SAT",
            object_id="2024-001A",
            originator="ASTRO-TOOLS",
            reference_frame="EME2000",
            central_body="EARTH",
            time_scale="UTC",
            provenance=Provenance(source_format="ccsds-ocm", creation_date="2024-01-01T00:00:00"),
        ),
        epochs=np.array(["2024-01-01T00:00:00", "2024-01-01T00:10:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0], [6999.0, 60.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0], [-0.1, 7.5, 0.0]]),
    )


# --- reader ----------------------------------------------------------------------------


def test_read_kvn_returns_an_ephemeris() -> None:
    eph = read(GOLDEN_KVN.read_bytes())
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 3
    assert eph.metadata.reference_frame == "EME2000"
    assert eph.metadata.central_body == "EARTH"
    assert eph.metadata.time_scale == "UTC"
    assert eph.metadata.object_id == "2024-013A"


def test_reader_carries_every_block_on_source_native() -> None:
    native = read(GOLDEN_KVN.read_bytes()).source_native
    assert isinstance(native, OcmFile)
    assert native.serialization == "kvn"
    assert len(native.trajectories) == 1
    assert len(native.covariances) == 1
    assert len(native.maneuvers) == 1
    assert native.physical is not None
    assert native.perturbations is not None
    assert native.orbit_determination is not None
    assert native.user_defined is not None
    # the covariance and maneuver data lines survive verbatim on the fidelity model
    assert native.covariances[0].lines[-1] == "0.0 0.0 0.0 0.0 0.0 0.0001"
    assert native.maneuvers[0].lines == ("1800.0 0.0 0.0 0.012",)


def test_read_exposes_maneuvers_on_the_canonical_ephemeris() -> None:
    eph = read(GOLDEN_KVN.read_bytes())
    assert isinstance(eph, Ephemeris)
    assert len(eph.maneuvers) == 1
    (man,) = eph.maneuvers
    # TIME_RELATIVE 1800 s after EPOCH_TZERO 2024-03-12T00:00:00.
    assert man.epoch_ignition == np.datetime64("2024-03-12T00:30:00", "ns")
    assert man.ref_frame == "RTN"
    assert man.duration == 0.0
    assert man.delta_v == pytest.approx([0.0, 0.0, 0.012])
    assert man.delta_mass is None  # the composition states no DELTA_MASS column
    assert man.comments == ("stationkeeping burn",)


def test_man_composition_reads_duration_mass_and_scales_m_per_s_delta_v() -> None:
    eph = read(_OCM_MANEUVERS)
    assert isinstance(eph, Ephemeris)
    assert len(eph.maneuvers) == 2  # one canonical record per manLine
    first, second = eph.maneuvers
    assert first.epoch_ignition == np.datetime64("2024-01-01T00:01:00", "ns")
    assert first.duration == pytest.approx(30.0)
    assert first.delta_mass == pytest.approx(-1.5)
    assert first.delta_v == pytest.approx([0.01, 0.0, 0.0])  # 10 m/s → km/s
    assert second.epoch_ignition == np.datetime64("2024-01-01T00:02:00", "ns")
    assert second.duration == 0.0
    assert second.delta_v == pytest.approx([0.0, 0.005, 0.0])  # 5 m/s → km/s


def test_man_block_without_a_delta_v_column_still_places_the_burn() -> None:
    eph = read(_OCM_ABSOLUTE_NO_DV)
    assert isinstance(eph, Ephemeris)
    (man,) = eph.maneuvers
    assert man.epoch_ignition == np.datetime64("2024-01-01T02:00:00", "ns")  # TIME_ABSOLUTE
    assert man.ref_frame == "RTN"
    assert man.delta_v is None  # thrust columns are not modelled on the canonical record
    assert man.duration == 0.0


def test_a_maneuver_line_with_the_wrong_column_count_is_rejected() -> None:
    bad = _OCM_MANEUVERS.replace(b"60.0 30.0 -1.5 10.0 0.0 0.0", b"60.0 30.0 -1.5")
    with pytest.raises(MalformedSourceError, match="MAN_COMPOSITION names"):
        read(bad)


def test_a_non_numeric_maneuver_value_is_rejected() -> None:
    bad = _OCM_MANEUVERS.replace(b"60.0 30.0 -1.5 10.0 0.0 0.0", b"60.0 30.0 -1.5 oops 0.0 0.0")
    with pytest.raises(MalformedSourceError, match="DV_X value must be a number"):
        read(bad)


def test_a_man_block_without_a_time_column_yields_no_canonical_record() -> None:
    # A composition with no time column cannot place the burn in time, so the block contributes no
    # canonical maneuver — it still survives verbatim on the fidelity model.
    no_time = _OCM_ABSOLUTE_NO_DV.replace(
        b"MAN_COMPOSITION = TIME_ABSOLUTE,THR_X,THR_Y,THR_Z\n2024-01-01T02:00:00 0.5 0.0 0.0",
        b"MAN_COMPOSITION = THR_X,THR_Y,THR_Z\n0.5 0.0 0.0",
    )
    eph = read(no_time)
    assert isinstance(eph, Ephemeris)
    assert eph.maneuvers == ()
    native = eph.source_native
    assert isinstance(native, OcmFile)
    assert len(native.maneuvers) == 1


def test_man_units_may_list_a_token_per_column_including_time() -> None:
    # MAN_UNITS with one token per composition column (the time column included) still scales Δv.
    per_column = _OCM_MANEUVERS.replace(
        b"MAN_UNITS = s,kg,m/s,m/s,m/s", b"MAN_UNITS = s,s,kg,m/s,m/s,m/s"
    )
    eph = read(per_column)
    assert isinstance(eph, Ephemeris)
    assert eph.maneuvers[0].delta_v == pytest.approx([0.01, 0.0, 0.0])  # 10 m/s → km/s


def test_mismatched_man_units_count_falls_back_to_canonical_km_per_s() -> None:
    # A MAN_UNITS list matching neither the column count nor the non-time count is ignored, and Δv
    # is read in the canonical km/s (no scaling) rather than guessing a unit.
    mismatched = _OCM_MANEUVERS.replace(b"MAN_UNITS = s,kg,m/s,m/s,m/s", b"MAN_UNITS = s,kg")
    eph = read(mismatched)
    assert isinstance(eph, Ephemeris)
    assert eph.maneuvers[0].delta_v == pytest.approx([10.0, 0.0, 0.0])  # treated as km/s


def test_cross_format_write_drops_maneuvers_naming_the_loss(tmp_path: Path) -> None:
    # OEM has no maneuver block, so converting the maneuver-bearing OCM and writing it must report
    # the maneuvers as dropped rather than lose them silently.
    eph = read(GOLDEN_KVN.read_bytes())
    with pytest.warns(LossyConversionWarning) as record:
        write(convert(eph, to="ccsds-oem"), tmp_path / "out.oem")
    dropped = {field.name for warning in record for field in warning.message.dropped}  # type: ignore[union-attr]
    assert "maneuvers" in dropped


def test_dimensioned_metadata_value_parses_with_its_unit() -> None:
    native = read(GOLDEN_KVN.read_bytes()).source_native
    assert isinstance(native, OcmFile)
    assert native.metadata.get("TAIMUTC_AT_TZERO") == Quantity(37.0, "s")
    assert native.physical is not None
    assert native.physical.get("WET_MASS") == Quantity(1500.0, "kg")


def test_relative_trajectory_times_resolve_against_epoch_tzero() -> None:
    eph = read(GOLDEN_KVN.read_bytes())
    assert isinstance(eph, Ephemeris)
    tzero = np.datetime64("2024-03-12T00:00:00", "ns")
    expected = tzero + np.array([0, 600, 1200], dtype="timedelta64[s]").astype("timedelta64[ns]")
    np.testing.assert_array_equal(eph.epochs, expected)


def test_absolute_trajectory_times_are_read_directly() -> None:
    absolute = GOLDEN_KVN.read_bytes().replace(
        b"0.0 6800.0 0.0 0.0 0.0 7.5 1.0",
        b"2024-03-12T00:00:00 6800.0 0.0 0.0 0.0 7.5 1.0",
    )
    eph = read(absolute)
    assert isinstance(eph, Ephemeris)
    assert eph.epochs[0] == np.datetime64("2024-03-12T00:00:00", "ns")


def test_non_cartesian_trajectory_is_carried_but_not_projected() -> None:
    eph = read(_OCM_KEPLERIAN)
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 0  # a Keplerian state history contributes no Cartesian states
    native = eph.source_native
    assert isinstance(native, OcmFile)
    assert native.trajectories[0].get("TRAJ_TYPE") == "KEPLERIAN"
    assert native.trajectories[0].lines == ("0.0 6800.0 0.001 51.6 247.0 130.0 325.0",)


# --- writer tiers ----------------------------------------------------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    golden = GOLDEN_KVN.read_bytes()
    eph = read(golden, retain_source=True)
    assert write_ocm(eph, ".ocm") == golden


def test_default_round_trip_is_byte_stable_against_the_golden() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_ocm(read(golden), ".ocm") == golden


def test_synthesised_kvn_write_round_trips() -> None:
    eph = _full_ephemeris()
    reread = read(write_ocm(eph, ".ocm"))
    assert reread == eph


# --- no-silent-loss --------------------------------------------------------------------


def test_golden_round_trip_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    eph = read(GOLDEN_KVN.read_bytes())
    assert_no_silent_loss(lambda: write_ocm(eph, ".ocm"), loses=False)


def test_complete_synthesised_kvn_write_loses_nothing(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    assert_no_silent_loss(lambda: write_ocm(_full_ephemeris(), ".ocm"), loses=False)


def test_synthesised_kvn_write_with_missing_fields_warns(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    eph = Ephemeris(
        metadata=Metadata(object_name="SAT"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    assert_no_silent_loss(lambda: write_ocm(eph, ".ocm"), loses=True)


# --- malformed input -------------------------------------------------------------------


def test_missing_version_keyword_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="CCSDS_OCM_VERS"):
        read(GOLDEN_KVN.read_bytes().replace(b"CCSDS_OCM_VERS = 3.0\n", b""), format="ccsds-ocm")


def test_missing_required_metadata_keyword_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="TIME_SYSTEM"):
        read(GOLDEN_KVN.read_bytes().replace(b"TIME_SYSTEM = UTC\n", b""), format="ccsds-ocm")


def test_unknown_keyword_in_a_block_is_rejected() -> None:
    broken = GOLDEN_KVN.read_bytes().replace(b"OPS_STATUS = OPERATIONAL\n", b"BOGUS_KEY = X\n")
    with pytest.raises(MalformedSourceError, match="unexpected OCM META keyword 'BOGUS_KEY'"):
        read(broken, format="ccsds-ocm")


def test_unclosed_block_is_rejected() -> None:
    # Dropping the final block's STOP marker runs the scanner to EOF inside the block.
    with pytest.raises(MalformedSourceError, match="USER block was not closed"):
        read(GOLDEN_KVN.read_bytes().replace(b"USER_STOP\n", b""), format="ccsds-ocm")
