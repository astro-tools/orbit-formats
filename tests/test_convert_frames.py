"""Frame rotation: rotations checked against astropy reference values, magnitude and
round-trip invariants, the GCRF/ICRF identity, the lazy astropy import, and rejection of
an unsupported frame or time scale."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

from orbit_formats import Ephemeris, MeanElementSet, Metadata, StateVector, convert
from orbit_formats.convert.frames import normalize_frame, rotate_state, transform_available
from orbit_formats.convert.graph import apply_frame
from orbit_formats.errors import FrameRotationUnsupportedError

# Two epochs in 2020 — well inside astropy's bundled IERS-B coverage, so the ITRF rotation
# (which needs Earth-orientation data) is deterministic without any network access.
EPOCHS = np.array(["2020-06-01T00:00:00", "2020-06-01T00:10:00"], dtype="datetime64[ns]")
POS = np.array([[7000.0, 1000.0, 200.0], [6800.0, 1500.0, 400.0]])  # km
VEL = np.array([[1.0, 7.0, 0.5], [1.2, 6.9, 0.4]])  # km/s

KNOWN_FRAMES = ["TEME", "EME2000", "GCRF", "ICRF", "ITRF"]
ORDERED_PAIRS = [(a, b) for a in KNOWN_FRAMES for b in KNOWN_FRAMES if a != b]
# EME2000 / GCRF / ICRF are mutually fixed (constant bias rotations), so a rotation among
# them preserves the speed exactly. TEME drifts against them slowly (precession / nutation),
# and the terrestrial ITRF rotates with the Earth — both add a velocity term, so speed is
# not an invariant across them.
FIXED_INERTIAL = ["EME2000", "GCRF", "ICRF"]


def _astropy_reference(from_frame: str, to_frame: str) -> tuple[np.ndarray, np.ndarray]:
    """Rotate the sample state with astropy directly — the independent reference the DoD names.

    Built without touching the production module, so a wrong frame mapping, unit, or
    differential in :func:`rotate_state` shows up as a mismatch.
    """
    import astropy.units as u
    from astropy.coordinates import (
        GCRS,
        ITRS,
        TEME,
        CartesianDifferential,
        CartesianRepresentation,
        PrecessedGeocentric,
    )
    from astropy.time import Time
    from astropy.utils import iers

    def frame(name: str, obstime: Any) -> Any:
        if name == "TEME":
            return TEME(obstime=obstime)
        if name == "ITRF":
            return ITRS(obstime=obstime)
        if name in ("GCRF", "ICRF"):
            return GCRS(obstime=obstime)
        return PrecessedGeocentric(equinox=Time("J2000"), obstime=obstime)

    with iers.conf.set_temp("auto_download", False):
        obstime = Time(EPOCHS, format="datetime64", scale="utc")
        rep = CartesianRepresentation(
            POS[:, 0] * u.km,
            POS[:, 1] * u.km,
            POS[:, 2] * u.km,
            differentials=CartesianDifferential(
                VEL[:, 0] * (u.km / u.s), VEL[:, 1] * (u.km / u.s), VEL[:, 2] * (u.km / u.s)
            ),
        )
        out = (
            frame(from_frame, obstime)
            .realize_frame(rep)
            .transform_to(frame(to_frame, obstime))
            .represent_as(CartesianRepresentation, CartesianDifferential)
        )
        diff = out.differentials["s"]
        pos = np.stack([out.x.to_value(u.km), out.y.to_value(u.km), out.z.to_value(u.km)], axis=-1)
        vel = np.stack(
            [
                diff.d_x.to_value(u.km / u.s),
                diff.d_y.to_value(u.km / u.s),
                diff.d_z.to_value(u.km / u.s),
            ],
            axis=-1,
        )
    return pos, vel


# --- normalisation and capability ---------------------------------------------------------


def test_normalize_frame_aliases_and_casing() -> None:
    assert normalize_frame("teme") == "TEME"
    assert normalize_frame("  J2000 ") == "EME2000"  # J2000 is an alias of EME2000
    assert normalize_frame("EME2000") == "EME2000"
    assert normalize_frame("gcrf") == "GCRF"
    assert normalize_frame("ICRF") == "ICRF"
    assert normalize_frame("itrf") == "ITRF"


def test_normalize_frame_returns_none_for_an_unknown_frame() -> None:
    assert normalize_frame("NONSENSE") is None
    assert normalize_frame("") is None


def test_transform_available_only_between_known_frames() -> None:
    assert transform_available("TEME", "J2000") is True
    assert transform_available("ITRF", "GCRF") is True
    assert transform_available("TEME", "NONSENSE") is False
    assert transform_available("WAT", "ITRF") is False


# --- rotation against astropy reference values --------------------------------------------


@pytest.mark.parametrize(("from_frame", "to_frame"), ORDERED_PAIRS)
def test_rotation_matches_the_astropy_reference(from_frame: str, to_frame: str) -> None:
    pos, vel = rotate_state(
        POS, VEL, EPOCHS, time_scale="UTC", from_frame=from_frame, to_frame=to_frame
    )
    ref_pos, ref_vel = _astropy_reference(from_frame, to_frame)
    np.testing.assert_allclose(pos, ref_pos, atol=1e-9)
    np.testing.assert_allclose(vel, ref_vel, atol=1e-12)


@pytest.mark.parametrize(("from_frame", "to_frame"), ORDERED_PAIRS)
def test_rotation_preserves_the_position_magnitude(from_frame: str, to_frame: str) -> None:
    pos, _ = rotate_state(
        POS, VEL, EPOCHS, time_scale="UTC", from_frame=from_frame, to_frame=to_frame
    )
    np.testing.assert_allclose(np.linalg.norm(pos, axis=1), np.linalg.norm(POS, axis=1), rtol=1e-9)


@pytest.mark.parametrize(
    ("from_frame", "to_frame"),
    [(a, b) for a in FIXED_INERTIAL for b in FIXED_INERTIAL if a != b],
)
def test_speed_is_preserved_within_the_fixed_inertial_triad(from_frame: str, to_frame: str) -> None:
    _, vel = rotate_state(
        POS, VEL, EPOCHS, time_scale="UTC", from_frame=from_frame, to_frame=to_frame
    )
    np.testing.assert_allclose(np.linalg.norm(vel, axis=1), np.linalg.norm(VEL, axis=1), rtol=1e-9)


@pytest.mark.parametrize("inertial", ["TEME", "EME2000", "GCRF", "ICRF"])
def test_itrf_rotation_changes_the_speed(inertial: str) -> None:
    # The Earth-rotation term across the terrestrial ITRF visibly changes the speed (the
    # ground-track velocity is metres-per-second different from the inertial velocity).
    _, vel = rotate_state(POS, VEL, EPOCHS, time_scale="UTC", from_frame=inertial, to_frame="ITRF")
    assert not np.allclose(np.linalg.norm(vel, axis=1), np.linalg.norm(VEL, axis=1), rtol=1e-3)


def test_gcrf_and_icrf_are_the_same_axes() -> None:
    # GCRF is by definition the geocentric frame whose axes coincide with ICRF, so the
    # rotation between them is an identity.
    pos, vel = rotate_state(POS, VEL, EPOCHS, time_scale="UTC", from_frame="GCRF", to_frame="ICRF")
    np.testing.assert_allclose(pos, POS, atol=1e-9)
    np.testing.assert_allclose(vel, VEL, atol=1e-12)


@pytest.mark.parametrize(("from_frame", "to_frame"), ORDERED_PAIRS)
def test_round_trip_returns_to_the_source(from_frame: str, to_frame: str) -> None:
    pos, vel = rotate_state(
        POS, VEL, EPOCHS, time_scale="UTC", from_frame=from_frame, to_frame=to_frame
    )
    back_pos, back_vel = rotate_state(
        pos, vel, EPOCHS, time_scale="UTC", from_frame=to_frame, to_frame=from_frame
    )
    np.testing.assert_allclose(back_pos, POS, atol=1e-6)
    np.testing.assert_allclose(back_vel, VEL, atol=1e-9)


def test_identity_rotation_returns_the_state_unchanged() -> None:
    # J2000 and EME2000 name the same frame, so this is an identity (no astropy needed).
    pos, vel = rotate_state(
        POS, VEL, EPOCHS, time_scale="UTC", from_frame="J2000", to_frame="EME2000"
    )
    np.testing.assert_array_equal(pos, POS)
    np.testing.assert_array_equal(vel, VEL)


def test_a_single_epoch_state_rotates() -> None:
    pos, vel = rotate_state(
        POS[:1], VEL[:1], EPOCHS[:1], time_scale="UTC", from_frame="TEME", to_frame="J2000"
    )
    assert pos.shape == (1, 3)
    assert vel.shape == (1, 3)
    ref_pos, _ = _astropy_reference("TEME", "EME2000")
    np.testing.assert_allclose(pos[0], ref_pos[0], atol=1e-9)


def test_gps_time_scale_is_accepted() -> None:
    # GPS epochs build an obstime via the constant TAI offset; the rotation must just run.
    pos, _ = rotate_state(POS, VEL, EPOCHS, time_scale="GPS", from_frame="TEME", to_frame="ITRF")
    np.testing.assert_allclose(np.linalg.norm(pos, axis=1), np.linalg.norm(POS, axis=1), rtol=1e-9)


# --- rejection ----------------------------------------------------------------------------


def test_rotate_state_rejects_an_unknown_frame() -> None:
    with pytest.raises(ValueError, match="cannot rotate between frames"):
        rotate_state(POS, VEL, EPOCHS, time_scale="UTC", from_frame="TEME", to_frame="NONSENSE")


def test_rotate_state_rejects_an_unknown_time_scale() -> None:
    with pytest.raises(ValueError, match="time scale"):
        rotate_state(POS, VEL, EPOCHS, time_scale="BOGUS", from_frame="TEME", to_frame="J2000")


# --- the lazy astropy import (as in the time-scale layer) ---------------------------------


def test_astropy_is_not_imported_until_a_rotation_runs() -> None:
    # In a fresh interpreter: importing orbit_formats and running a same-frame convert must
    # not pull astropy in; only a real rotation does. Run out-of-process so the assertion is
    # not fooled by another test having already imported astropy into this process.
    program = textwrap.dedent(
        """
        import sys
        import numpy as np
        import orbit_formats
        from orbit_formats import convert, Ephemeris, Metadata

        eph = Ephemeris(
            metadata=Metadata(reference_frame="TEME", time_scale="UTC", central_body="EARTH"),
            epochs=np.array(["2020-06-01T00:00:00"], dtype="datetime64[ns]"),
            positions=np.array([[7000.0, 0.0, 0.0]]),
            velocities=np.array([[0.0, 7.5, 0.0]]),
        )
        convert(eph, to="ccsds-oem")                  # same form, no frame -> no rotation
        convert(eph, to="ccsds-oem", frame="TEME")    # already TEME -> no rotation
        assert "astropy" not in sys.modules, "astropy imported before any rotation"
        convert(eph, to="ccsds-oem", frame="J2000")   # a real rotation
        assert "astropy" in sys.modules, "astropy not imported by a rotation"
        print("OK")
        """
    )
    result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("OK")


# --- the no-silent-loss contract: a rotation is lossless ----------------------------------


def test_frame_rotation_is_lossless(assert_no_silent_loss: Callable[..., None]) -> None:
    eph = Ephemeris(
        metadata=Metadata(reference_frame="TEME", time_scale="UTC", central_body="EARTH"),
        epochs=EPOCHS,
        positions=POS,
        velocities=VEL,
    )
    # Rotating to a different frame is a rigid transform — it drops no canonical information,
    # so it must stay warn-free.
    assert_no_silent_loss(lambda: convert(eph, to="ccsds-oem", frame="J2000"), loses=False)


# --- the graph's apply_frame policy on the other canonical forms --------------------------


def test_apply_frame_rotates_a_state_vector_between_known_frames() -> None:
    state = StateVector(
        metadata=Metadata(reference_frame="TEME", time_scale="UTC", central_body="EARTH"),
        epoch=EPOCHS[0],
        position=POS[0],
        velocity=VEL[0],
    )
    rotated = apply_frame(state, "ITRF")
    assert isinstance(rotated, StateVector)
    assert rotated.metadata.reference_frame == "ITRF"
    # A rigid rotation preserves the position magnitude.
    np.testing.assert_allclose(
        np.linalg.norm(rotated.position), np.linalg.norm(state.position), rtol=1e-9
    )
    # The rotated state no longer matches the original bytes, so source_native is dropped.
    assert rotated.source_native is None


def test_apply_frame_on_mean_elements_has_no_cartesian_state_to_rotate() -> None:
    mean_set = MeanElementSet(
        metadata=Metadata(reference_frame="TEME", time_scale="UTC", central_body="EARTH"),
        epoch=EPOCHS[0],
        mean_motion=15.5,
        eccentricity=0.001,
        inclination=51.6,
        raan=247.0,
        arg_periapsis=130.0,
        mean_anomaly=325.0,
    )
    with pytest.raises(FrameRotationUnsupportedError):
        apply_frame(mean_set, "J2000")
