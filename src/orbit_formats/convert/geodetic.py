"""Geodetic projection — ECEF Cartesian to and from ellipsoidal longitude / latitude / height.

The last, purely geometric step of a ground track: projecting an Earth-fixed (ITRF / ECEF)
Cartesian position onto a reference ellipsoid. It composes on top of the inertial -> ``ITRF``
rotation the conversion layer already does (:mod:`orbit_formats.convert.frames`), giving a full
inertial -> geodetic path without each consumer re-deriving the WGS84 math.

Like the element transforms (:mod:`orbit_formats.convert.elements`) this is closed-form geometry,
not a frame transform: it needs no precession / nutation / Earth-orientation data, so it stays
**pure numpy** with no astropy dependency (the frame rotation, which genuinely needs astropy, is the
half this builds on). Longitudes and latitudes are in **degrees** and lengths in **km**, matching
the canonical unit convention; the geodetic latitude is the angle of the local ellipsoid normal,
not the geocentric one.

The reference ellipsoid is table-driven: pass a known name (``"WGS84"``, the default) or a custom
:class:`Ellipsoid`, so other bodies can be projected without new code paths.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "Ellipsoid",
    "GeodeticLocation",
    "cartesian_to_geodetic",
    "geodetic_to_cartesian",
]


@dataclass(frozen=True, slots=True)
class Ellipsoid:
    """A reference ellipsoid of revolution, defined by its size and flattening.

    ``semi_major_axis`` is the equatorial radius in km; ``inverse_flattening`` is ``1 / f``
    (use ``float("inf")`` for a sphere). The eccentricity follows from the flattening. Pass an
    instance to the projection helpers to use a body the built-in table does not list.
    """

    semi_major_axis: float
    inverse_flattening: float

    @property
    def flattening(self) -> float:
        """The flattening ``f = (a - b) / a`` (0 for a sphere)."""
        return 1.0 / self.inverse_flattening

    @property
    def eccentricity_squared(self) -> float:
        """The first eccentricity squared ``e^2 = f (2 - f)``."""
        f = self.flattening
        return f * (2.0 - f)


# The reference ellipsoids known by name. Keyed by the upper-cased name; deliberately small and
# extended either by adding an entry here or by passing a custom :class:`Ellipsoid` instance, so a
# new body needs no new code path. WGS84 is the default (a in km, the standard 1/f).
_ELLIPSOIDS: dict[str, Ellipsoid] = {
    "WGS84": Ellipsoid(semi_major_axis=6378.137, inverse_flattening=298.257223563),
}

# The latitude fixed-point iteration converges quadratically; this many steps reach float64
# precision for any terrestrial-to-deep-space height, and convergence is checked each step.
_MAX_LATITUDE_ITERATIONS = 10
# Stop once the latitude estimate moves less than this (radians) — ~1e-13 deg, below float64 noise.
_LATITUDE_TOLERANCE_RAD = 1e-15


def _resolve_ellipsoid(ellipsoid: str | Ellipsoid) -> Ellipsoid:
    """The :class:`Ellipsoid` for ``ellipsoid``: an instance is returned as-is, a name looked up.

    Name lookup is case- and whitespace-insensitive. Raises :class:`ValueError` for an unknown
    name, listing the known ones — guessing an ellipsoid would be worse than a clear failure.
    """
    if isinstance(ellipsoid, Ellipsoid):
        return ellipsoid
    key = ellipsoid.strip().upper()
    try:
        return _ELLIPSOIDS[key]
    except KeyError:
        known = ", ".join(sorted(_ELLIPSOIDS))
        raise ValueError(
            f"no ellipsoid known by name {ellipsoid!r}; known ellipsoids: {known} "
            f"(or pass a custom Ellipsoid)"
        ) from None


def geodetic_to_cartesian(
    longitude: ArrayLike,
    latitude: ArrayLike,
    height: ArrayLike,
    *,
    ellipsoid: str | Ellipsoid = "WGS84",
) -> NDArray[np.float64]:
    """ECEF Cartesian position (km) from geodetic ``longitude`` / ``latitude`` / ``height``.

    ``longitude`` and ``latitude`` are geodetic degrees (east-positive longitude); ``height`` is
    the ellipsoidal height in km. The three are broadcast together, so scalars give a single
    ``(3,)`` position and matching length-N arrays give an ``(N, 3)`` series. This is the exact
    closed form (no iteration); it inverts :func:`cartesian_to_geodetic`.
    """
    ell = _resolve_ellipsoid(ellipsoid)
    a = ell.semi_major_axis
    e2 = ell.eccentricity_squared

    lon = np.radians(np.asarray(longitude, dtype=np.float64))
    lat = np.radians(np.asarray(latitude, dtype=np.float64))
    h = np.asarray(height, dtype=np.float64)

    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    # Prime-vertical radius of curvature: the ellipsoid normal's length to the equatorial plane.
    prime_vertical = a / np.sqrt(1.0 - e2 * sin_lat * sin_lat)

    ring = (prime_vertical + h) * cos_lat
    x = ring * np.cos(lon)
    y = ring * np.sin(lon)
    z = (prime_vertical * (1.0 - e2) + h) * sin_lat
    return np.asarray(np.stack(np.broadcast_arrays(x, y, z), axis=-1), dtype=np.float64)


def cartesian_to_geodetic(
    xyz: ArrayLike, *, ellipsoid: str | Ellipsoid = "WGS84"
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Geodetic ``(longitude, latitude, height)`` from an ECEF Cartesian position ``xyz`` (km).

    ``xyz`` is a ``(3,)`` position or an ``(N, 3)`` series; the trailing axis is x / y / z in km.
    Returns longitude and latitude in degrees and height in km — a single ``(3,)`` input yields
    three 0-d arrays (read with ``float(...)``), an ``(N, 3)`` input three length-N arrays.

    Longitude is exact (``atan2``); latitude and height are solved by the standard fixed-point
    iteration on latitude, which converges to float64 precision and is well-behaved at the poles
    and at high altitude. Inverts :func:`geodetic_to_cartesian`.
    """
    ell = _resolve_ellipsoid(ellipsoid)
    a = ell.semi_major_axis
    e2 = ell.eccentricity_squared

    arr = np.asarray(xyz, dtype=np.float64)
    if arr.shape[-1] != 3:
        raise ValueError(
            f"expected a Cartesian position with a trailing axis of length 3, got shape {arr.shape}"
        )
    x = arr[..., 0]
    y = arr[..., 1]
    z = arr[..., 2]

    distance_from_axis = np.hypot(x, y)
    longitude = np.arctan2(y, x)

    # Seed with the latitude the point would have on a sphere, then iterate
    # tan(lat) = (z + e^2 N sin(lat)) / p until it stops moving. At the poles p -> 0 and the
    # iterate lands on +/-90 deg immediately, so no pole special-case is needed here.
    latitude = np.arctan2(z, distance_from_axis * (1.0 - e2))
    for _ in range(_MAX_LATITUDE_ITERATIONS):
        sin_lat = np.sin(latitude)
        prime_vertical = a / np.sqrt(1.0 - e2 * sin_lat * sin_lat)
        next_latitude = np.arctan2(z + e2 * prime_vertical * sin_lat, distance_from_axis)
        if np.all(np.abs(next_latitude - latitude) <= _LATITUDE_TOLERANCE_RAD):
            latitude = next_latitude
            break
        latitude = next_latitude

    sin_lat = np.sin(latitude)
    cos_lat = np.cos(latitude)
    # Height projected along the local normal — division-free, so it is exact at the poles
    # (cos(lat) -> 0) and at high altitude: h = p cos(lat) + z sin(lat) - a sqrt(1 - e^2 sin^2).
    height = distance_from_axis * cos_lat + z * sin_lat - a * np.sqrt(1.0 - e2 * sin_lat * sin_lat)

    return (
        np.asarray(np.degrees(longitude), dtype=np.float64),
        np.asarray(np.degrees(latitude), dtype=np.float64),
        np.asarray(height, dtype=np.float64),
    )


@dataclass(frozen=True, slots=True)
class GeodeticLocation:
    """A fixed geodetic site / observer coordinate on a reference ellipsoid.

    ``longitude`` and ``latitude`` are geodetic degrees (east-positive longitude); ``height`` is
    the ellipsoidal height in km above ``ellipsoid`` (``"WGS84"`` by default, or a custom
    :class:`Ellipsoid`). A pure value type for expressing where a ground site sits consistently —
    :meth:`from_cartesian` / :meth:`to_cartesian` compose the module's projection helpers, and it
    holds no astropy objects.
    """

    longitude: float
    latitude: float
    height: float
    ellipsoid: str | Ellipsoid = "WGS84"

    @classmethod
    def from_cartesian(
        cls, xyz: ArrayLike, *, ellipsoid: str | Ellipsoid = "WGS84"
    ) -> GeodeticLocation:
        """The geodetic location of a single ECEF Cartesian position ``xyz`` (km)."""
        arr = np.asarray(xyz, dtype=np.float64)
        if arr.shape != (3,):
            raise ValueError(
                f"GeodeticLocation.from_cartesian expects a single (3,) position, "
                f"got shape {arr.shape}"
            )
        longitude, latitude, height = cartesian_to_geodetic(arr, ellipsoid=ellipsoid)
        return cls(
            longitude=float(longitude),
            latitude=float(latitude),
            height=float(height),
            ellipsoid=ellipsoid,
        )

    def to_cartesian(self) -> NDArray[np.float64]:
        """The ECEF Cartesian position (km) of this location, as a ``(3,)`` array."""
        return geodetic_to_cartesian(
            self.longitude, self.latitude, self.height, ellipsoid=self.ellipsoid
        )
