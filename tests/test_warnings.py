"""The lossy-conversion warning framework: a catchable family, structured payloads, and
the no-silent-loss contract every converter must satisfy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Attitude,
    Conjunction,
    ConjunctionObject,
    DroppedField,
    DroppedFieldWarning,
    Ephemeris,
    LossyConversionWarning,
    MeanElementSet,
    Metadata,
    ModelApproximationWarning,
    PrecisionLossWarning,
    StateVector,
    convert,
    read,
    warn_lossy,
)
from orbit_formats.formats import is_writable, known_format_ids
from orbit_formats.registry import get_writer
from orbit_formats.writers.aem import write_aem
from orbit_formats.writers.apm import write_apm
from orbit_formats.writers.cdm import write_cdm
from orbit_formats.writers.oem import write_oem
from orbit_formats.writers.omm import write_omm
from orbit_formats.writers.opm import write_opm
from orbit_formats.writers.stk_ephemeris import write_stk_ephemeris
from orbit_formats.writers.tle import write_tle

CONCRETE_WARNINGS = [DroppedFieldWarning, ModelApproximationWarning, PrecisionLossWarning]


def _sample(cls: type[LossyConversionWarning]) -> LossyConversionWarning:
    """A representative instance of each concrete warning, with full context."""
    if cls is DroppedFieldWarning:
        return DroppedFieldWarning("covariance", target_format="ccsds-oem")
    if cls is PrecisionLossWarning:
        return PrecisionLossWarning("epoch", target_format="tle")
    if cls is ModelApproximationWarning:
        return ModelApproximationWarning(
            source_kind="mean elements", target_kind="state", fields=["state"], model="SGP4"
        )
    raise AssertionError(f"unhandled warning type {cls!r}")


# --- the hierarchy -----------------------------------------------------------------


def test_every_warning_descends_from_the_base() -> None:
    assert issubclass(LossyConversionWarning, Warning)
    for cls in CONCRETE_WARNINGS:
        assert issubclass(cls, LossyConversionWarning)


def test_a_lossy_warning_must_name_a_dropped_field() -> None:
    with pytest.raises(ValueError, match="at least one"):
        LossyConversionWarning("nothing was lost", dropped=[])
    with pytest.raises(ValueError, match="at least one"):
        ModelApproximationWarning(source_kind="mean elements", target_kind="state", fields=[])


# --- the structured payload --------------------------------------------------------


@pytest.mark.parametrize("cls", CONCRETE_WARNINGS)
def test_each_warning_names_what_was_lost(cls: type[LossyConversionWarning]) -> None:
    warning = _sample(cls)
    assert warning.dropped
    for field in warning.dropped:
        assert isinstance(field, DroppedField)
        assert field.name
        assert field.reason
        assert field.name in str(warning)
    assert warning.fields == tuple(field.name for field in warning.dropped)


def test_warnings_build_without_optional_context() -> None:
    dropped = DroppedFieldWarning("covariance")
    assert "covariance" in str(dropped)
    assert dropped.target_format is None
    assert dropped.dropped[0].reason

    precision = PrecisionLossWarning("epoch")
    assert "epoch" in str(precision)
    assert precision.target_format is None

    model = ModelApproximationWarning(
        source_kind="mean elements", target_kind="state", fields=["state"]
    )
    assert model.model is None
    assert model.dropped[0].reason


# --- emission via the sanctioned seam ----------------------------------------------


def test_warn_lossy_is_catchable_as_a_family_with_payload_intact() -> None:
    with pytest.warns(LossyConversionWarning) as record:
        warn_lossy(DroppedFieldWarning("covariance", target_format="ccsds-oem"))
    assert len(record) == 1
    caught = record[0].message
    assert isinstance(caught, DroppedFieldWarning)
    assert caught.field == "covariance"
    assert caught.target_format == "ccsds-oem"
    assert [field.name for field in caught.dropped] == ["covariance"]


@pytest.mark.parametrize("cls", CONCRETE_WARNINGS)
def test_each_warning_is_catchable_by_its_own_type(cls: type[LossyConversionWarning]) -> None:
    with pytest.warns(cls):
        warn_lossy(_sample(cls))


# --- the no-silent-loss meta-test, driven by the real v0.1 surface -----------------
#
# The no-silent-loss contract (assert_no_silent_loss) must hold for every v0.1 operation
# that can drop information: the registered writers, a reader that NaN-fills an absent
# canonical field, and the conversion-graph routing. Each case below pairs a *real*
# operation with whether it loses information; ``writer_format`` marks the cases that
# exercise a registered writer. The coverage guard
# (:func:`test_meta_test_covers_every_registered_writer`) then asserts every registered
# writer has both a lossless and a lossy case, so a writer added in a later version
# cannot quietly join the surface without proving the contract.
#
# The third kickoff semantic — a cross-category model step (mean elements -> a state via
# SGP4) — has no instance in v0.1: such a conversion needs a propagator and is refused
# with UnsupportedConversionError, never silently approximated (test_api and
# test_convert_graph assert that refusal). It returns here once v0.2 lands the
# mean-elements -> ephemeris edge.

GOLDEN_OEM = Path(__file__).parent / "data" / "oem" / "golden_roundtrip.oem"
GOLDEN_OPM = Path(__file__).parent / "data" / "opm" / "golden_opm.opm"
GOLDEN_STK = Path(__file__).parent / "data" / "stk" / "golden_roundtrip.e"

# A single-row GMAT report with a complete state (no NaN-fill) and a position-only one
# (velocity absent -> MissingFieldWarning) — minimal and self-contained.
_GMAT_REPORT_FULL = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5   0.0\n"
)
_GMAT_REPORT_POSITION_ONLY = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   Sat.EarthMJ2000Eq.Z\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0\n"
)


@dataclass(frozen=True)
class _MetaCase:
    """One real-surface operation and whether it drops information.

    ``writer_format`` is the format id when the case exercises a registered writer (so the
    coverage guard can confirm every writer is represented), and ``None`` otherwise.
    """

    label: str
    operation: Callable[[], object]
    loses: bool
    writer_format: str | None = None


def _oem_ephemeris() -> Ephemeris:
    """A canonical ephemeris read from the OEM golden (carries an OemFile source_native)."""
    eph = read(GOLDEN_OEM.read_bytes())
    assert isinstance(eph, Ephemeris)
    return eph


def _incomplete_oem_ephemeris() -> Ephemeris:
    """An ephemeris missing OBJECT_ID and TIME_SYSTEM — an OEM write must warn for each."""
    return Ephemeris(
        metadata=Metadata(object_name="SAT", central_body="EARTH", reference_frame="EME2000"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )


# A complete 3LE — a name plus the two element lines — so the TLE -> OMM enrichment and the
# TLE -> TLE echo are both warning-free (every identifier is present).
_TLE_3LE = (
    b"ISS (ZARYA)\n"
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)


def _tle_mean_set() -> MeanElementSet:
    """A mean-element set read from a 3LE (carries a TleRecord source_native)."""
    mean_set = read(_TLE_3LE)
    assert isinstance(mean_set, MeanElementSet)
    return mean_set


def _opm_state() -> StateVector:
    """A canonical state read from the OPM golden (carries an OpmFile source_native)."""
    state = read(GOLDEN_OPM.read_bytes())
    assert isinstance(state, StateVector)
    return state


def _stk_ephemeris() -> Ephemeris:
    """An ephemeris read from the STK golden (carries an StkEphemerisFile source_native)."""
    eph = read(GOLDEN_STK.read_bytes())
    assert isinstance(eph, Ephemeris)
    return eph


def _incomplete_stk_ephemeris() -> Ephemeris:
    """An ephemeris missing CentralBody and CoordinateSystem — an STK write must warn for each."""
    return Ephemeris(
        metadata=Metadata(time_scale="UTC"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )


def _incomplete_state_vector() -> StateVector:
    """A state missing OBJECT_ID, CENTER_NAME, and TIME_SYSTEM — an OPM write must warn."""
    return StateVector(
        metadata=Metadata(object_name="SAT", reference_frame="EME2000"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 0.0, 0.0]),
        velocity=np.array([0.0, 7.5, 0.0]),
    )


_AEM_KVN = b"""CCSDS_AEM_VERS = 1.0
CREATION_DATE = 2024-01-01T00:00:00
ORIGINATOR = ORBIT-FORMATS

META_START
OBJECT_NAME = SAT
OBJECT_ID = 2024-001A
CENTER_NAME = EARTH
REF_FRAME_A = EME2000
REF_FRAME_B = SC_BODY
TIME_SYSTEM = UTC
START_TIME = 2024-01-01T00:00:00
STOP_TIME = 2024-01-01T00:01:00
ATTITUDE_TYPE = QUATERNION
QUATERNION_TYPE = LAST
META_STOP

DATA_START
2024-01-01T00:00:00 0.1 0.2 0.3 0.927362
2024-01-01T00:01:00 0.11 0.21 0.31 0.92
DATA_STOP
"""


def _aem_attitude() -> Attitude:
    """An attitude read from an AEM (carries an AemFile source_native) — write is lossless."""
    att = read(_AEM_KVN)
    assert isinstance(att, Attitude)
    return att


def _incomplete_attitude() -> Attitude:
    """An attitude missing OBJECT_ID and both frames — an AEM write must warn for each."""
    return Attitude(
        metadata=Metadata(object_name="SAT", time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0]]),
    )


_APM_KVN = b"""CCSDS_APM_VERS = 1.0
CREATION_DATE = 2024-01-01T00:00:00
ORIGINATOR = ORBIT-FORMATS

META_START
OBJECT_NAME = SAT
OBJECT_ID = 2024-001A
CENTER_NAME = EARTH
TIME_SYSTEM = UTC
META_STOP

EPOCH = 2024-01-01T00:00:00
Q_FRAME_A = EME2000
Q_FRAME_B = SC_BODY
Q_DIR = A2B
Q1 = 0.1
Q2 = 0.2
Q3 = 0.3
QC = 0.927362
"""


def _apm_attitude() -> Attitude:
    """An attitude read from an APM (carries an ApmFile source_native) — write is lossless."""
    att = read(_APM_KVN)
    assert isinstance(att, Attitude)
    return att


def _incomplete_apm_attitude() -> Attitude:
    """A single quaternion attitude missing OBJECT_ID and both frames — an APM write warns."""
    return Attitude(
        metadata=Metadata(object_name="SAT", time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0]]),
    )


_CDM_GOLDEN = Path(__file__).parent / "data" / "cdm" / "golden_cdm.cdm"


def _cdm_conjunction() -> Conjunction:
    """A conjunction read from a CDM (carries a CdmFile source_native) — write is lossless."""
    conj = read(_CDM_GOLDEN.read_bytes())
    assert isinstance(conj, Conjunction)
    return conj


def _incomplete_cdm_conjunction() -> Conjunction:
    """A bare conjunction missing the CDM-required per-object metadata — a CDM write warns."""
    objects = (
        ConjunctionObject(
            label="OBJECT1",
            object_designator="1",
            ref_frame="EME2000",
            state=np.zeros(6),
            covariance=np.eye(6),
        ),
        ConjunctionObject(
            label="OBJECT2",
            object_designator="2",
            ref_frame="EME2000",
            state=np.zeros(6),
            covariance=np.eye(6),
        ),
    )
    return Conjunction(
        metadata=Metadata(time_scale="UTC"),
        tca=np.datetime64("2024-01-01T00:00:00", "ns"),
        miss_distance=1.0,
        objects=objects,
    )


def _bare_mean_set(metadata: Metadata) -> MeanElementSet:
    """A bare mean-element set (no source_native) with the given metadata — for the lossy cases."""
    return MeanElementSet(
        metadata=metadata,
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        mean_motion=15.0,
        eccentricity=0.001,
        inclination=51.6,
        raan=247.0,
        arg_periapsis=130.0,
        mean_anomaly=325.0,
    )


_META_CASES = [
    _MetaCase(
        "ccsds-oem write: content-lossless re-serialise",
        lambda: write_oem(_oem_ephemeris()),
        loses=False,
        writer_format="ccsds-oem",
    ),
    _MetaCase(
        "ccsds-oem write: synthesised, missing required META",
        lambda: write_oem(_incomplete_oem_ephemeris()),
        loses=True,
        writer_format="ccsds-oem",
    ),
    _MetaCase(
        "ccsds-omm write: TLE -> OMM, every identifier present",
        lambda: write_omm(_tle_mean_set()),
        loses=False,
        writer_format="ccsds-omm",
    ),
    _MetaCase(
        "ccsds-omm write: synthesised, missing required metadata",
        lambda: write_omm(_bare_mean_set(Metadata())),
        loses=True,
        writer_format="ccsds-omm",
    ),
    _MetaCase(
        "ccsds-opm write: content-lossless re-serialise",
        lambda: write_opm(_opm_state()),
        loses=False,
        writer_format="ccsds-opm",
    ),
    _MetaCase(
        "ccsds-opm write: synthesised, missing required metadata",
        lambda: write_opm(_incomplete_state_vector()),
        loses=True,
        writer_format="ccsds-opm",
    ),
    _MetaCase(
        "stk-ephemeris write: content-lossless re-serialise",
        lambda: write_stk_ephemeris(_stk_ephemeris()),
        loses=False,
        writer_format="stk-ephemeris",
    ),
    _MetaCase(
        "stk-ephemeris write: synthesised, missing required meta",
        lambda: write_stk_ephemeris(_incomplete_stk_ephemeris()),
        loses=True,
        writer_format="stk-ephemeris",
    ),
    _MetaCase(
        "tle write: TLE -> TLE echo",
        lambda: write_tle(_tle_mean_set()),
        loses=False,
        writer_format="tle",
    ),
    _MetaCase(
        "tle write: reconstruction missing the TLE bookkeeping",
        lambda: write_tle(_bare_mean_set(Metadata(object_id="25544"))),
        loses=True,
        writer_format="tle",
    ),
    _MetaCase(
        "gmat-report read: complete state",
        lambda: read(_GMAT_REPORT_FULL, format="gmat-report"),
        loses=False,
    ),
    _MetaCase(
        "gmat-report read: position only (velocity NaN-filled)",
        lambda: read(_GMAT_REPORT_POSITION_ONLY, format="gmat-report"),
        loses=True,
    ),
    _MetaCase(
        "convert: same-form ephemeris -> ccsds-oem",
        lambda: convert(_oem_ephemeris(), to="ccsds-oem"),
        loses=False,
    ),
    _MetaCase(
        "ccsds-aem write: content-lossless re-serialise",
        lambda: write_aem(_aem_attitude()),
        loses=False,
        writer_format="ccsds-aem",
    ),
    _MetaCase(
        "ccsds-aem write: synthesised, missing required META",
        lambda: write_aem(_incomplete_attitude()),
        loses=True,
        writer_format="ccsds-aem",
    ),
    _MetaCase(
        "ccsds-apm write: content-lossless re-serialise",
        lambda: write_apm(_apm_attitude()),
        loses=False,
        writer_format="ccsds-apm",
    ),
    _MetaCase(
        "ccsds-apm write: synthesised, missing required fields",
        lambda: write_apm(_incomplete_apm_attitude()),
        loses=True,
        writer_format="ccsds-apm",
    ),
    _MetaCase(
        "ccsds-cdm write: content-lossless re-serialise",
        lambda: write_cdm(_cdm_conjunction()),
        loses=False,
        writer_format="ccsds-cdm",
    ),
    _MetaCase(
        "ccsds-cdm write: synthesised, missing required fields",
        lambda: write_cdm(_incomplete_cdm_conjunction()),
        loses=True,
        writer_format="ccsds-cdm",
    ),
]


def _registered_writer_formats() -> set[str]:
    """Every catalogued writable format that has a writer registered."""
    return {fid for fid in known_format_ids() if is_writable(fid) and get_writer(fid) is not None}


@pytest.mark.parametrize("case", _META_CASES, ids=lambda case: case.label)
def test_no_surface_operation_loses_information_without_warning(
    case: _MetaCase,
    assert_no_silent_loss: Callable[..., None],
) -> None:
    """Every real v0.1 surface operation warns exactly when it drops information."""
    assert_no_silent_loss(case.operation, loses=case.loses)


def test_meta_test_covers_every_registered_writer() -> None:
    """Each registered writer has both a lossless and a lossy no-silent-loss case.

    This is the future-proofing guard: a writer added later (the v0.2 NDM family) fails
    the suite until it gains both a complete (warn-free) and an information-dropping
    (warns) case in ``_META_CASES`` — so no writer can join the surface without proving
    the no-silent-loss contract end to end.
    """
    registered = _registered_writer_formats()
    assert registered, "expected at least one registered writer on the v0.1 surface"
    for fid in sorted(registered):
        cases = [case for case in _META_CASES if case.writer_format == fid]
        assert any(not case.loses for case in cases), (
            f"registered writer {fid!r} has no lossless no-silent-loss case"
        )
        assert any(case.loses for case in cases), (
            f"registered writer {fid!r} has no information-dropping no-silent-loss case"
        )
