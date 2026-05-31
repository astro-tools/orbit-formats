"""Element transforms — Cartesian to and from Keplerian, given a gravitational parameter.

The two-way map between a Cartesian state (position / velocity) and the classical
orbital elements — the conversion graph's element edge. Both directions take the
gravitational parameter ``mu`` (km^3/s^2) explicitly; the graph supplies it from the
metadata's central body via :func:`gravitational_parameter`. Angles are in **degrees**,
matching the canonical angle-unit convention; lengths and speeds are km and km/s.

The transform is the standard RV-to-COE / COE-to-RV pair (e.g. Vallado, Curtis). The
circular and equatorial degeneracies — where the argument of periapsis, RAAN, or true
anomaly is individually undefined — are folded into the next well-defined angle with a
round-trip-stable convention, so ``cartesian -> keplerian -> cartesian`` recovers the
state for those orbits too.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.state import KeplerianElements

__all__ = [
    "cartesian_to_keplerian",
    "gravitational_parameter",
    "keplerian_to_cartesian",
]

# Standard gravitational parameters (km^3/s^2) for the central bodies a state is
# likely tagged with. Keyed by the upper-cased body name; the table is deliberately small
# and easily extended as more central bodies appear in real data.
_GM_KM3_S2: dict[str, float] = {
    "EARTH": 398600.4418,
    "SUN": 132712440018.0,
    "MOON": 4902.800066,
}

# Below this, the eccentricity (circular) or node-vector magnitude (equatorial) is treated
# as zero and the corresponding angle is folded into the next defined one.
_DEGENERACY_EPS = 1e-11

_TWO_PI = 2.0 * np.pi


def gravitational_parameter(central_body: str) -> float:
    """The gravitational parameter ``mu`` (km^3/s^2) for ``central_body``.

    Lookup is case- and whitespace-insensitive. Raises :class:`ValueError` for a body the
    table does not know — the element transforms need an explicit ``mu``, so guessing one
    would be worse than a clear failure.
    """
    key = central_body.strip().upper()
    try:
        return _GM_KM3_S2[key]
    except KeyError:
        known = ", ".join(sorted(_GM_KM3_S2))
        raise ValueError(
            f"no gravitational parameter known for central body {central_body!r}; "
            f"known bodies: {known}"
        ) from None


def cartesian_to_keplerian(
    position: NDArray[np.float64], velocity: NDArray[np.float64], mu: float
) -> KeplerianElements:
    """Classical orbital elements from a Cartesian state, given ``mu`` (km^3/s^2).

    ``position`` (km) and ``velocity`` (km/s) are length-3 arrays in the same frame. The
    returned :class:`KeplerianElements` has its angles in degrees. A circular and/or
    equatorial orbit, whose RAAN / argument of periapsis / true anomaly are individually
    undefined, is given the conventional folded angles so the inverse transform recovers
    the state.
    """
    r_vec = np.asarray(position, dtype=np.float64)
    v_vec = np.asarray(velocity, dtype=np.float64)
    r = float(np.linalg.norm(r_vec))
    v = float(np.linalg.norm(v_vec))

    h_vec = np.cross(r_vec, v_vec)
    h = float(np.linalg.norm(h_vec))
    node_vec = np.cross([0.0, 0.0, 1.0], h_vec)
    node = float(np.linalg.norm(node_vec))

    ecc_vec = ((v * v - mu / r) * r_vec - float(np.dot(r_vec, v_vec)) * v_vec) / mu
    ecc = float(np.linalg.norm(ecc_vec))

    energy = v * v / 2.0 - mu / r
    semi_major_axis = float("inf") if abs(ecc - 1.0) <= _DEGENERACY_EPS else -mu / (2.0 * energy)

    inclination = float(np.arccos(np.clip(h_vec[2] / h, -1.0, 1.0)))

    circular = ecc < _DEGENERACY_EPS
    equatorial = node < _DEGENERACY_EPS
    radial_outward = float(np.dot(r_vec, v_vec)) >= 0.0

    if not circular and not equatorial:
        raan = _angle(node_vec[0] / node, node_vec[1] >= 0.0)
        arg_periapsis = _angle(float(np.dot(node_vec, ecc_vec)) / (node * ecc), ecc_vec[2] >= 0.0)
        true_anomaly = _angle(float(np.dot(ecc_vec, r_vec)) / (ecc * r), radial_outward)
    elif not circular and equatorial:
        # Equatorial, elliptical: RAAN is undefined; fold it into the true longitude of
        # periapsis measured from the +X axis.
        raan = 0.0
        arg_periapsis = _angle(ecc_vec[0] / ecc, ecc_vec[1] >= 0.0)
        true_anomaly = _angle(float(np.dot(ecc_vec, r_vec)) / (ecc * r), radial_outward)
    elif circular and not equatorial:
        # Circular, inclined: argument of periapsis and true anomaly are undefined
        # separately; carry the argument of latitude as the true anomaly.
        raan = _angle(node_vec[0] / node, node_vec[1] >= 0.0)
        arg_periapsis = 0.0
        true_anomaly = _angle(float(np.dot(node_vec, r_vec)) / (node * r), r_vec[2] >= 0.0)
    else:
        # Circular, equatorial: only the true longitude from the +X axis is defined.
        raan = 0.0
        arg_periapsis = 0.0
        true_anomaly = _angle(r_vec[0] / r, r_vec[1] >= 0.0)

    return KeplerianElements(
        semi_major_axis=semi_major_axis,
        eccentricity=ecc,
        inclination=float(np.degrees(inclination)),
        raan=float(np.degrees(raan)),
        arg_periapsis=float(np.degrees(arg_periapsis)),
        true_anomaly=float(np.degrees(true_anomaly)),
    )


def keplerian_to_cartesian(
    elements: KeplerianElements, mu: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Cartesian position (km) and velocity (km/s) from Keplerian ``elements`` and ``mu``.

    The inverse of :func:`cartesian_to_keplerian`: it builds the state in the perifocal
    frame from the true anomaly, then rotates into the inertial frame by the 3-1-3
    (RAAN, inclination, argument of periapsis) sequence. Angles are read in degrees.
    """
    ecc = elements.eccentricity
    inclination = np.radians(elements.inclination)
    raan = np.radians(elements.raan)
    arg_periapsis = np.radians(elements.arg_periapsis)
    true_anomaly = np.radians(elements.true_anomaly)

    semi_latus_rectum = elements.semi_major_axis * (1.0 - ecc * ecc)
    radius = semi_latus_rectum / (1.0 + ecc * np.cos(true_anomaly))

    r_pqw = np.array(
        [radius * np.cos(true_anomaly), radius * np.sin(true_anomaly), 0.0], dtype=np.float64
    )
    sqrt_mu_over_p = np.sqrt(mu / semi_latus_rectum)
    v_pqw = np.array(
        [
            -sqrt_mu_over_p * np.sin(true_anomaly),
            sqrt_mu_over_p * (ecc + np.cos(true_anomaly)),
            0.0,
        ],
        dtype=np.float64,
    )

    rotation = _perifocal_to_inertial(raan, inclination, arg_periapsis)
    position = np.asarray(rotation @ r_pqw, dtype=np.float64)
    velocity = np.asarray(rotation @ v_pqw, dtype=np.float64)
    return position, velocity


def _angle(cosine: float, in_upper_half: bool) -> float:
    """Recover an angle in [0, 2pi) from its cosine and the sign of its sine.

    ``in_upper_half`` is the quadrant resolver: the angle is taken in ``[0, pi]`` when the
    governing component is non-negative, and reflected into ``(pi, 2pi)`` otherwise.
    """
    angle = float(np.arccos(np.clip(cosine, -1.0, 1.0)))
    return angle if in_upper_half else _TWO_PI - angle


def _perifocal_to_inertial(
    raan: float, inclination: float, arg_periapsis: float
) -> NDArray[np.float64]:
    """The 3-1-3 (RAAN, inclination, argument of periapsis) perifocal-to-inertial DCM."""
    cos_o, sin_o = np.cos(raan), np.sin(raan)
    cos_i, sin_i = np.cos(inclination), np.sin(inclination)
    cos_w, sin_w = np.cos(arg_periapsis), np.sin(arg_periapsis)
    return np.array(
        [
            [
                cos_o * cos_w - sin_o * sin_w * cos_i,
                -cos_o * sin_w - sin_o * cos_w * cos_i,
                sin_o * sin_i,
            ],
            [
                sin_o * cos_w + cos_o * sin_w * cos_i,
                -sin_o * sin_w + cos_o * cos_w * cos_i,
                -cos_o * sin_i,
            ],
            [sin_w * sin_i, cos_w * sin_i, cos_i],
        ],
        dtype=np.float64,
    )
