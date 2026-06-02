"""Cross-validate the conversion layer against Orekit — a genuinely independent oracle.

The conversion layer (elements, frames, time) is built on ``astropy`` internally, and the
unit tests in ``test_convert_*.py`` check it against ``astropy`` reference values. That is a
useful self-consistency check but not an *independent* one: the reference and the
implementation share a library. This oracle closes that gap. Orekit is a mature, independently
developed space-dynamics library (Java, Apache-2.0) with its own precession/nutation, frame,
and time-scale machinery, so agreement here means the conversions are right against an outside
authority, not merely internally consistent — the validation discipline the v1.0 charter gates
on.

Like the CCSDS oracles, Orekit is **never** a runtime, extra, or dev dependency of
orbit-formats, never imported by the package, and never distributed. It is installed
transiently in one dedicated CI job (``orekit-jpype[jdk4py]`` — the JVM bridge plus a pip-only
JDK) and pulled in here behind :func:`pytest.importorskip`, so this module simply skips
anywhere Orekit is absent (the main test matrix, a normal local run). The reference Earth-
orientation / leap-second data is a pinned ``orekit-data`` snapshot the CI job downloads once
and points at via the ``OREKIT_DATA_ZIP`` environment variable; the cross-check itself touches
no network. Absent that variable (or the JVM), the module skips rather than fails.

Tolerances are documented per conversion family below and reflect genuine astropy-vs-Orekit
model differences, calibrated against this oracle — not arbitrary slack. Surfacing (not fixing)
any discrepancy is the point: behaviour changes are handled separately under the v0.3 quality
review.

One mapping note: orbit-formats' ``ICRF`` is the *geocentric* ICRF-aligned frame (identical
axes to ``GCRF``; see :mod:`orbit_formats.convert.frames`), whereas Orekit's
``FramesFactory.getICRF()`` is the *barycentric* ICRF. The oracle therefore maps our ``ICRF``
onto Orekit's geocentric ``getGCRF()``, the frame we actually mean.
"""

from __future__ import annotations

import datetime as _dt
import os
from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

pytest.importorskip("orekit_jpype")

from orbit_formats.canonical.state import KeplerianElements
from orbit_formats.convert.elements import cartesian_to_keplerian, keplerian_to_cartesian
from orbit_formats.convert.frames import rotate_state
from orbit_formats.convert.time import convert_time_scale

# Earth gravitational parameter — the same value orbit-formats uses, passed explicitly to
# Orekit so the element cross-check isolates the algebra, not a difference in the constant.
MU_KM = 398600.4418
MU_M = MU_KM * 1e9

# Two non-degenerate, inclined, eccentric sample states (km, km/s). Degenerate orbits
# (circular / equatorial), whose RAAN / argument-of-periapsis / anomaly conventions differ
# between libraries by design, are exercised against the round-trip in test_convert_elements.py
# instead — here we want orbits whose six elements are individually unambiguous.
SAMPLE_STATES = [
    (np.array([7000.0, 1000.0, 200.0]), np.array([1.0, 7.0, 0.5])),
    (np.array([-5500.0, 3200.0, 4100.0]), np.array([-4.2, -2.1, 5.6])),
]

# A single epoch, well inside both libraries' bundled Earth-orientation coverage, so the ITRF
# and UT1 paths (which need EOP) are deterministic.
EPOCHS = np.array(["2020-06-01T00:00:00"], dtype="datetime64[ns]")
FRAME_POS = np.array([[7000.0, 1000.0, 200.0]])
FRAME_VEL = np.array([[1.0, 7.0, 0.5]])

FRAMES = ["TEME", "EME2000", "GCRF", "ICRF", "ITRF"]
FRAME_PAIRS = [(a, b) for a in FRAMES for b in FRAMES if a != b]

SCALES = ["UTC", "TAI", "TT", "TDB", "GPS", "UT1"]
SCALE_PAIRS = [(a, b) for a in SCALES for b in SCALES if a != b]
# UTC/TAI/TT/GPS are related by defined integer or constant offsets (leap seconds, +32.184 s,
# -19 s), so the two libraries agree to the floor of the representation. TDB (a periodic
# relativistic series) and UT1 (an EOP-interpolated scale) are modelled, so a pair involving
# either differs at the model level between astropy and Orekit.
MODEL_SCALES = {"TDB", "UT1"}

# --- documented tolerances (calibrated against this oracle) -------------------------------
# Elements: identical two-body algebra given the same mu — agreement is at machine precision;
# the bounds below are generous round-offs of that.
ELEM_SMA_RTOL = 1e-9
ELEM_ECC_ATOL = 1e-9
ELEM_ANGLE_ATOL_DEG = 1e-6
ELEM_POS_ATOL_KM = 1e-6
ELEM_VEL_ATOL_KM_S = 1e-9
# Frames: the IERS-standard frames (EME2000 / GCRF / ICRF / ITRF) agree to a few millimetres;
# 1 m / 1 cm/s bounds that with margin for state and epoch spread. TEME has no single
# rigorous definition (astropy and Orekit realise it slightly differently), so its pairs get a
# looser metre-level bound — still ~1000x tighter than any real frame-mapping error.
FRAME_POS_ATOL_KM = 1e-3
FRAME_VEL_ATOL_KM_S = 1e-5
TEME_POS_ATOL_KM = 1e-2
TEME_VEL_ATOL_KM_S = 1e-4
# Time: the defined scales agree to well under a microsecond; the modelled scales (TDB / UT1)
# differ at the sub-millisecond level between the two libraries' models and EOP tables.
TIME_EXACT_ATOL_S = 1e-6
TIME_MODEL_ATOL_S = 2e-3


def _components(epoch: np.datetime64) -> tuple[int, int, int, int, int, float]:
    """Decompose a ``datetime64`` into (year, month, day, hour, minute, fractional-second)."""
    moment = epoch.astype("datetime64[ns]")
    day = moment.astype("datetime64[D]")
    midnight_ns = (moment - day) / np.timedelta64(1, "ns")
    py_day = day.astype(_dt.date)
    hour, rem = divmod(int(midnight_ns), 3_600_000_000_000)
    minute, rem = divmod(rem, 60_000_000_000)
    return py_day.year, py_day.month, py_day.day, hour, minute, rem / 1e9


class _Orekit:
    """A thin façade over the Orekit references the oracle compares against.

    Built only after the JVM is up (the ``orekit`` fixture), so the ``org.orekit`` / ``java``
    imports — which need a running VM — live here rather than at module load. Every method
    returns plain Python / numpy so the test bodies stay free of JPype objects.
    """

    def __init__(self) -> None:
        from org.orekit.frames import FramesFactory
        from org.orekit.time import AbsoluteDate, TimeScalesFactory
        from org.orekit.utils import IERSConventions

        self._AbsoluteDate = AbsoluteDate
        self._frames = {
            "TEME": FramesFactory.getTEME(),
            "EME2000": FramesFactory.getEME2000(),
            "GCRF": FramesFactory.getGCRF(),
            # orbit-formats' ICRF is geocentric (== GCRF), not Orekit's barycentric getICRF().
            "ICRF": FramesFactory.getGCRF(),
            "ITRF": FramesFactory.getITRF(IERSConventions.IERS_2010, True),
        }
        self._scales = {
            "UTC": TimeScalesFactory.getUTC(),
            "TAI": TimeScalesFactory.getTAI(),
            "TT": TimeScalesFactory.getTT(),
            "TDB": TimeScalesFactory.getTDB(),
            "GPS": TimeScalesFactory.getGPS(),
            "UT1": TimeScalesFactory.getUT1(IERSConventions.IERS_2010, True),
        }

    def _date(self, epoch: np.datetime64, scale: str) -> Any:
        year, month, day, hour, minute, second = _components(epoch)
        return self._AbsoluteDate(year, month, day, hour, minute, second, self._scales[scale])

    def keplerian(
        self, position: NDArray[np.float64], velocity: NDArray[np.float64]
    ) -> tuple[float, float, float, float, float, float]:
        """Classical elements (a in km; e; i, RAAN, argp, true anomaly in deg), via Orekit."""
        import math

        from org.hipparchus.geometry.euclidean.threed import Vector3D
        from org.orekit.frames import FramesFactory
        from org.orekit.orbits import CartesianOrbit, KeplerianOrbit
        from org.orekit.time import AbsoluteDate
        from org.orekit.utils import PVCoordinates

        pv = PVCoordinates(Vector3D(*(position * 1000.0)), Vector3D(*(velocity * 1000.0)))
        orbit = KeplerianOrbit(
            CartesianOrbit(pv, FramesFactory.getEME2000(), AbsoluteDate.J2000_EPOCH, MU_M)
        )
        return (
            orbit.getA() / 1000.0,
            orbit.getE(),
            math.degrees(orbit.getI()) % 360.0,
            math.degrees(orbit.getRightAscensionOfAscendingNode()) % 360.0,
            math.degrees(orbit.getPerigeeArgument()) % 360.0,
            math.degrees(orbit.getTrueAnomaly()) % 360.0,
        )

    def cartesian(
        self, elements: KeplerianElements
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Cartesian position (km) and velocity (km/s) of Keplerian elements, via Orekit."""
        import math

        from org.orekit.frames import FramesFactory
        from org.orekit.orbits import KeplerianOrbit, PositionAngleType
        from org.orekit.time import AbsoluteDate

        orbit = KeplerianOrbit(
            elements.semi_major_axis * 1000.0,
            elements.eccentricity,
            math.radians(elements.inclination),
            math.radians(elements.arg_periapsis),  # Orekit's constructor takes argp before RAAN
            math.radians(elements.raan),
            math.radians(elements.true_anomaly),
            PositionAngleType.TRUE,
            FramesFactory.getEME2000(),
            AbsoluteDate.J2000_EPOCH,
            MU_M,
        )
        pv = orbit.getPVCoordinates()
        position = pv.getPosition()
        velocity = pv.getVelocity()
        return (
            np.array([position.getX(), position.getY(), position.getZ()]) / 1000.0,
            np.array([velocity.getX(), velocity.getY(), velocity.getZ()]) / 1000.0,
        )

    def rotate(
        self,
        position: NDArray[np.float64],
        velocity: NDArray[np.float64],
        from_frame: str,
        to_frame: str,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Rotate a single Cartesian state at ``EPOCHS[0]`` (UTC) between frames, via Orekit."""
        from org.hipparchus.geometry.euclidean.threed import Vector3D
        from org.orekit.utils import PVCoordinates

        pv = PVCoordinates(Vector3D(*(position * 1000.0)), Vector3D(*(velocity * 1000.0)))
        transform = self._frames[from_frame].getTransformTo(
            self._frames[to_frame], self._date(EPOCHS[0], "UTC")
        )
        out = transform.transformPVCoordinates(pv)
        position_out = out.getPosition()
        velocity_out = out.getVelocity()
        return (
            np.array([position_out.getX(), position_out.getY(), position_out.getZ()]) / 1000.0,
            np.array([velocity_out.getX(), velocity_out.getY(), velocity_out.getZ()]) / 1000.0,
        )

    def scale_delta_seconds(self, from_scale: str, to_scale: str, epoch: np.datetime64) -> float:
        """The clock-reading shift (seconds) of reinterpreting ``epoch`` from one scale to another.

        Matches ``convert_time_scale``'s semantics: the same wall-clock reading on the source
        scale, expressed on the target scale, shifts by ``offset(to) - offset(from)`` from TAI.
        """
        date = self._date(epoch, from_scale)
        offset_from = self._scales[from_scale].offsetFromTAI(date).toDouble()
        offset_to = self._scales[to_scale].offsetFromTAI(date).toDouble()
        return float(offset_to - offset_from)


@pytest.fixture(scope="module")
def orekit() -> Iterator[_Orekit]:
    """Start the JVM, point Orekit at the pinned data archive, and yield the reference façade.

    Skips (never fails) when the oracle cannot run: no ``OREKIT_DATA_ZIP`` archive, or no JVM
    available. The dedicated CI ``orekit`` job sets both up; everywhere else this skips.
    """
    data_archive = os.environ.get("OREKIT_DATA_ZIP")
    if not data_archive or not os.path.isfile(data_archive):
        pytest.skip("set OREKIT_DATA_ZIP to a pinned orekit-data archive to run the Orekit oracle")

    import jpype
    import orekit_jpype

    if not jpype.isJVMStarted():
        jvmpath = None
        try:
            import jdk4py  # the pip-only JDK that backs orekit-jpype[jdk4py]

            os.environ.setdefault("JAVA_HOME", str(jdk4py.JAVA_HOME))
            jvmpath = str(jdk4py.JAVA_HOME / "lib" / "server" / "libjvm.so")
        except ImportError:
            jvmpath = None  # fall back to a system JVM discovered via JAVA_HOME
        if jvmpath:
            orekit_jpype.initVM(jvmpath=jvmpath)
        else:
            orekit_jpype.initVM()

    from orekit_jpype.pyhelpers import setup_orekit_curdir

    setup_orekit_curdir(data_archive)
    yield _Orekit()


def _assert_angle_close(actual: float, reference: float, atol: float) -> None:
    """Assert two angles (degrees) agree, treating 0° and 360° as equal."""
    diff = abs((actual - reference + 180.0) % 360.0 - 180.0)
    assert diff <= atol, f"angle {actual} vs {reference} differ by {diff} deg (> {atol})"


# --- elements: Cartesian <-> Keplerian against Orekit -------------------------------------


@pytest.mark.parametrize(("position", "velocity"), SAMPLE_STATES)
def test_cartesian_to_keplerian_matches_orekit(
    orekit: _Orekit, position: NDArray[np.float64], velocity: NDArray[np.float64]
) -> None:
    ours = cartesian_to_keplerian(position, velocity, MU_KM)
    ref_a, ref_e, ref_i, ref_raan, ref_argp, ref_nu = orekit.keplerian(position, velocity)
    np.testing.assert_allclose(ours.semi_major_axis, ref_a, rtol=ELEM_SMA_RTOL)
    np.testing.assert_allclose(ours.eccentricity, ref_e, atol=ELEM_ECC_ATOL)
    _assert_angle_close(ours.inclination, ref_i, ELEM_ANGLE_ATOL_DEG)
    _assert_angle_close(ours.raan, ref_raan, ELEM_ANGLE_ATOL_DEG)
    _assert_angle_close(ours.arg_periapsis, ref_argp, ELEM_ANGLE_ATOL_DEG)
    _assert_angle_close(ours.true_anomaly, ref_nu, ELEM_ANGLE_ATOL_DEG)


@pytest.mark.parametrize(("position", "velocity"), SAMPLE_STATES)
def test_keplerian_to_cartesian_matches_orekit(
    orekit: _Orekit, position: NDArray[np.float64], velocity: NDArray[np.float64]
) -> None:
    # Go to elements with our own forward map, then compare both libraries' inverse on them.
    elements = cartesian_to_keplerian(position, velocity, MU_KM)
    our_pos, our_vel = keplerian_to_cartesian(elements, MU_KM)
    ref_pos, ref_vel = orekit.cartesian(elements)
    np.testing.assert_allclose(our_pos, ref_pos, atol=ELEM_POS_ATOL_KM)
    np.testing.assert_allclose(our_vel, ref_vel, atol=ELEM_VEL_ATOL_KM_S)


# --- frames: rotations against Orekit -----------------------------------------------------


@pytest.mark.parametrize(("from_frame", "to_frame"), FRAME_PAIRS)
def test_frame_rotation_matches_orekit(orekit: _Orekit, from_frame: str, to_frame: str) -> None:
    ours_pos, ours_vel = rotate_state(
        FRAME_POS, FRAME_VEL, EPOCHS, time_scale="UTC", from_frame=from_frame, to_frame=to_frame
    )
    ref_pos, ref_vel = orekit.rotate(FRAME_POS[0], FRAME_VEL[0], from_frame, to_frame)
    teme_involved = "TEME" in (from_frame, to_frame)
    pos_atol = TEME_POS_ATOL_KM if teme_involved else FRAME_POS_ATOL_KM
    vel_atol = TEME_VEL_ATOL_KM_S if teme_involved else FRAME_VEL_ATOL_KM_S
    np.testing.assert_allclose(ours_pos[0], ref_pos, atol=pos_atol)
    np.testing.assert_allclose(ours_vel[0], ref_vel, atol=vel_atol)


# --- time scales: reinterpretation shifts against Orekit ----------------------------------


@pytest.mark.parametrize(("from_scale", "to_scale"), SCALE_PAIRS)
def test_time_scale_conversion_matches_orekit(
    orekit: _Orekit, from_scale: str, to_scale: str
) -> None:
    epoch = EPOCHS[0]
    converted = convert_time_scale(epoch, from_scale, to_scale)
    ours_delta = float((converted - epoch) / np.timedelta64(1, "ns")) / 1e9
    ref_delta = orekit.scale_delta_seconds(from_scale, to_scale, epoch)
    modelled = bool(MODEL_SCALES & {from_scale, to_scale})
    atol = TIME_MODEL_ATOL_S if modelled else TIME_EXACT_ATOL_S
    assert abs(ours_delta - ref_delta) <= atol, (
        f"{from_scale}->{to_scale}: ours {ours_delta}s vs orekit {ref_delta}s "
        f"differ by {abs(ours_delta - ref_delta)}s (> {atol})"
    )
