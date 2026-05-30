"""The Cartesian <-> Keplerian element transform: a textbook case, round-trips to
tolerance, the circular / equatorial degeneracies, and the gravitational-parameter table."""

from __future__ import annotations

import math

import numpy as np
import pytest

from orbit_formats import KeplerianElements
from orbit_formats.convert.elements import (
    cartesian_to_keplerian,
    gravitational_parameter,
    keplerian_to_cartesian,
)

# Earth GM rounded as the textbooks use it, so the published example values line up.
MU_EARTH = 398600.0


def _circular_state(radius: float, inclination_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """A circular state at ``radius`` km and the given inclination, in the X-Z plane of motion."""
    speed = math.sqrt(MU_EARTH / radius)
    position = np.array([radius, 0.0, 0.0])
    velocity = np.array(
        [
            0.0,
            speed * math.cos(math.radians(inclination_deg)),
            speed * math.sin(math.radians(inclination_deg)),
        ]
    )
    return position, velocity


# --- the gravitational-parameter table ---------------------------------------------


def test_gravitational_parameter_is_case_insensitive() -> None:
    assert gravitational_parameter("Earth") == gravitational_parameter("  earth ")
    assert gravitational_parameter("EARTH") == pytest.approx(398600.4418)
    assert gravitational_parameter("Sun") == pytest.approx(132712440018.0)
    assert gravitational_parameter("Moon") == pytest.approx(4902.800066)


def test_gravitational_parameter_rejects_an_unknown_body() -> None:
    with pytest.raises(ValueError, match="no gravitational parameter known"):
        gravitational_parameter("Krypton")


# --- the textbook case (Curtis, Orbital Mechanics, Example 4.3) ---------------------


def test_cartesian_to_keplerian_matches_a_textbook_case() -> None:
    position = np.array([-6045.0, -3490.0, 2500.0])  # km
    velocity = np.array([-3.457, 6.618, 2.533])  # km/s

    elements = cartesian_to_keplerian(position, velocity, MU_EARTH)

    # Curtis Example 4.3 reference values (rounded as published).
    assert elements.semi_major_axis == pytest.approx(8788.0, abs=1.0)
    assert elements.eccentricity == pytest.approx(0.1712, abs=1e-3)
    assert elements.inclination == pytest.approx(153.2, abs=0.1)
    assert elements.raan == pytest.approx(255.3, abs=0.1)
    assert elements.arg_periapsis == pytest.approx(20.07, abs=0.1)
    assert elements.true_anomaly == pytest.approx(28.45, abs=0.1)


def test_general_orbit_round_trips_to_tolerance() -> None:
    position = np.array([-6045.0, -3490.0, 2500.0])
    velocity = np.array([-3.457, 6.618, 2.533])

    elements = cartesian_to_keplerian(position, velocity, MU_EARTH)
    recovered_position, recovered_velocity = keplerian_to_cartesian(elements, MU_EARTH)

    np.testing.assert_allclose(recovered_position, position, atol=1e-6)
    np.testing.assert_allclose(recovered_velocity, velocity, atol=1e-9)


def test_keplerian_to_cartesian_matches_a_known_state() -> None:
    # A 7000 km, e=0.01, 30 deg orbit at periapsis (true anomaly 0): the periapsis radius
    # a(1-e) lies in the orbit plane and rotates by the 3-1-3 sequence.
    elements = KeplerianElements(
        semi_major_axis=7000.0,
        eccentricity=0.01,
        inclination=30.0,
        raan=40.0,
        arg_periapsis=60.0,
        true_anomaly=0.0,
    )
    position, velocity = keplerian_to_cartesian(elements, MU_EARTH)
    # Periapsis radius and circular-ish speed are the magnitude checks.
    assert float(np.linalg.norm(position)) == pytest.approx(7000.0 * (1 - 0.01), rel=1e-9)
    # Re-deriving the elements returns the inputs.
    back = cartesian_to_keplerian(position, velocity, MU_EARTH)
    assert back.semi_major_axis == pytest.approx(7000.0, rel=1e-9)
    assert back.eccentricity == pytest.approx(0.01, abs=1e-9)
    assert back.inclination == pytest.approx(30.0, abs=1e-9)
    assert back.raan == pytest.approx(40.0, abs=1e-9)


# --- the degeneracies (each branch of the angle-folding logic) ----------------------


def test_circular_inclined_orbit_round_trips() -> None:
    position, velocity = _circular_state(7000.0, 45.0)
    elements = cartesian_to_keplerian(position, velocity, MU_EARTH)

    assert elements.eccentricity == pytest.approx(0.0, abs=1e-9)
    assert elements.inclination == pytest.approx(45.0, abs=1e-9)
    assert elements.arg_periapsis == pytest.approx(0.0, abs=1e-9)  # folded away

    recovered_position, recovered_velocity = keplerian_to_cartesian(elements, MU_EARTH)
    np.testing.assert_allclose(recovered_position, position, atol=1e-6)
    np.testing.assert_allclose(recovered_velocity, velocity, atol=1e-9)


def test_equatorial_elliptical_orbit_round_trips() -> None:
    # Elliptical, in the equatorial plane: RAAN is undefined and folds into the longitude
    # of periapsis. Start just past periapsis so velocity has an in-plane radial component.
    elements = KeplerianElements(
        semi_major_axis=10000.0,
        eccentricity=0.2,
        inclination=0.0,
        raan=0.0,
        arg_periapsis=70.0,
        true_anomaly=35.0,
    )
    position, velocity = keplerian_to_cartesian(elements, MU_EARTH)
    recovered = cartesian_to_keplerian(position, velocity, MU_EARTH)

    assert recovered.inclination == pytest.approx(0.0, abs=1e-9)
    assert recovered.raan == pytest.approx(0.0, abs=1e-9)  # folded away
    re_position, re_velocity = keplerian_to_cartesian(recovered, MU_EARTH)
    np.testing.assert_allclose(re_position, position, atol=1e-6)
    np.testing.assert_allclose(re_velocity, velocity, atol=1e-9)


def test_circular_equatorial_orbit_round_trips() -> None:
    position, velocity = _circular_state(7000.0, 0.0)
    elements = cartesian_to_keplerian(position, velocity, MU_EARTH)

    assert elements.eccentricity == pytest.approx(0.0, abs=1e-9)
    assert elements.inclination == pytest.approx(0.0, abs=1e-9)
    assert elements.raan == pytest.approx(0.0, abs=1e-9)
    assert elements.arg_periapsis == pytest.approx(0.0, abs=1e-9)

    recovered_position, recovered_velocity = keplerian_to_cartesian(elements, MU_EARTH)
    np.testing.assert_allclose(recovered_position, position, atol=1e-6)
    np.testing.assert_allclose(recovered_velocity, velocity, atol=1e-9)


def test_hyperbolic_orbit_round_trips() -> None:
    # e > 1: the semi-major axis is negative and the semi-latus rectum stays positive.
    position = np.array([7000.0, 1000.0, 500.0])
    velocity = np.array([2.0, 11.0, 3.0])  # fast enough to be hyperbolic at this radius

    elements = cartesian_to_keplerian(position, velocity, MU_EARTH)
    assert elements.eccentricity > 1.0
    assert elements.semi_major_axis < 0.0

    recovered_position, recovered_velocity = keplerian_to_cartesian(elements, MU_EARTH)
    np.testing.assert_allclose(recovered_position, position, atol=1e-6)
    np.testing.assert_allclose(recovered_velocity, velocity, atol=1e-9)
