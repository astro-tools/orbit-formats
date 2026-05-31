"""Reference-frame rotation — TEME / EME2000 (J2000) / GCRF / ICRF / ITRF, via ``astropy``.

Rotating a Cartesian state from one reference frame to another is a rigid, lossless
operation: the same physical state expressed on a different set of axes. The position
magnitude is preserved by every rotation; the speed is preserved too, except across the
terrestrial ITRF, where the Earth-rotation term genuinely changes the velocity.

``astropy.coordinates`` does the heavy lifting — precession / nutation for the inertial
frames, and the IERS Earth-orientation tables plus the Earth-rotation rate for the
terrestrial ITRF — but it stays an internal detail: it is imported lazily *inside* the
rotation, so ``import orbit_formats`` and the read / write / detect / same-frame paths
stay astropy-free, and the input and output are plain ``numpy`` arrays. Earth-orientation
data is read hermetically (IERS auto-download disabled), matching the time-scale module.

The supported frames and how each maps onto an astropy frame:

- ``TEME`` — the SGP4 / TLE true-equator mean-equinox frame (``astropy`` ``TEME``).
- ``EME2000`` (``J2000``) — the geocentric mean equator and equinox of J2000
  (``PrecessedGeocentric`` at the J2000 equinox).
- ``GCRF`` / ``ICRF`` — both the geocentric celestial reference frame (``astropy`` ``GCRS``):
  GCRF is by definition the geocentric frame whose axes coincide with ICRF, so a rotation
  between the two is an identity, while each rotates non-trivially against TEME / EME2000 / ITRF.
- ``ITRF`` — the terrestrial (Earth-fixed) frame (``astropy`` ``ITRS``).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

__all__ = ["normalize_frame", "rotate_state", "transform_available"]

# The frames orbit-formats rotates among, each keyed to its canonical id. ``J2000`` and
# ``EME2000`` name the same frame and both normalise to ``EME2000`` (the CCSDS REF_FRAME
# spelling). The lookup is case- and whitespace-insensitive via :func:`normalize_frame`.
_FRAME_ALIASES: dict[str, str] = {
    "TEME": "TEME",
    "J2000": "EME2000",
    "EME2000": "EME2000",
    "GCRF": "GCRF",
    "ICRF": "ICRF",
    "ITRF": "ITRF",
}

# astropy's obstime scales, keyed by our upper-cased time-scale ids. GPS is handled as a
# constant TAI offset below — astropy models it as a clock format, not an obstime scale.
_ASTROPY_SCALE: dict[str, str] = {
    "UTC": "utc",
    "TAI": "tai",
    "TT": "tt",
    "TDB": "tdb",
    "UT1": "ut1",
}

# GPS time = TAI - 19 s, fixed since the GPS epoch (1980-01-06), mirroring the time module.
_GPS_TAI_OFFSET_SECONDS = 19.0


def normalize_frame(name: str) -> str | None:
    """The canonical frame id for ``name`` (case- and whitespace-insensitive), or ``None``.

    Returns ``None`` for any frame outside the supported set, so a caller can tell a known
    frame from one outside the supported set.
    """
    return _FRAME_ALIASES.get(name.strip().upper())


def transform_available(source_frame: str, target_frame: str) -> bool:
    """Whether a rotation between ``source_frame`` and ``target_frame`` is supported.

    True when both names normalise to a known frame — astropy composes a transform between
    any pair of the supported frames. Every other case (an unknown frame on either side) is
    left for the graph layer to report as an unsupported rotation.
    """
    return normalize_frame(source_frame) is not None and normalize_frame(target_frame) is not None


def rotate_state(
    positions: NDArray[np.float64],
    velocities: NDArray[np.float64],
    epochs: NDArray[np.datetime64],
    *,
    time_scale: str,
    from_frame: str,
    to_frame: str,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Rotate a Cartesian state series from ``from_frame`` to ``to_frame``.

    ``positions`` (km) and ``velocities`` (km/s) are ``(N, 3)`` arrays; ``epochs`` is the
    matching length-N ``datetime64`` array, interpreted in ``time_scale`` (one of
    :data:`~orbit_formats.canonical.metadata.TIME_SCALES`) to build the astropy obstime the
    epoch-dependent frames need. The velocity transform carries the rotating-frame term —
    e.g. the Earth-rotation contribution across ITRF — because the astropy state is built
    with velocity differentials. Returns the rotated ``(positions, velocities)`` with the
    same shape and ``float64`` dtype; an identity rotation (same frame, including the
    J2000 / EME2000 alias) returns copies unchanged.

    Raises :class:`ValueError` for a frame outside the supported set or a ``time_scale``
    astropy cannot build an obstime from. The no-op-vs-typed-error *policy* lives in the
    graph layer (:func:`orbit_formats.convert.graph.apply_frame`); this is the raw transform.
    """
    source_id = normalize_frame(from_frame)
    target_id = normalize_frame(to_frame)
    if source_id is None or target_id is None:
        raise ValueError(f"cannot rotate between frames {from_frame!r} and {to_frame!r}")

    pos = np.asarray(positions, dtype=np.float64).reshape(-1, 3)
    vel = np.asarray(velocities, dtype=np.float64).reshape(-1, 3)
    if source_id == target_id:
        return pos.copy(), vel.copy()

    import astropy.units as u
    from astropy.coordinates import CartesianDifferential, CartesianRepresentation
    from astropy.utils import iers

    representation = CartesianRepresentation(
        pos[:, 0] * u.km,
        pos[:, 1] * u.km,
        pos[:, 2] * u.km,
        differentials=CartesianDifferential(
            vel[:, 0] * (u.km / u.s),
            vel[:, 1] * (u.km / u.s),
            vel[:, 2] * (u.km / u.s),
        ),
    )
    # Disable IERS auto-download so the rotation is hermetic (no network) and deterministic,
    # falling back to astropy's bundled Earth-orientation tables — as the time module does.
    with iers.conf.set_temp("auto_download", False):
        obstime = _obstime(epochs, time_scale)
        source_state = _astropy_frame(source_id, obstime).realize_frame(representation)
        rotated = source_state.transform_to(_astropy_frame(target_id, obstime)).represent_as(
            CartesianRepresentation, CartesianDifferential
        )
        differential = rotated.differentials["s"]
        out_pos = np.stack(
            [rotated.x.to_value(u.km), rotated.y.to_value(u.km), rotated.z.to_value(u.km)],
            axis=-1,
        )
        out_vel = np.stack(
            [
                differential.d_x.to_value(u.km / u.s),
                differential.d_y.to_value(u.km / u.s),
                differential.d_z.to_value(u.km / u.s),
            ],
            axis=-1,
        )
    return out_pos.astype(np.float64), out_vel.astype(np.float64)


def _astropy_frame(frame_id: str, obstime: Any) -> Any:
    """Build the astropy frame instance for a canonical frame id at ``obstime``."""
    from astropy.coordinates import GCRS, ITRS, TEME, PrecessedGeocentric
    from astropy.time import Time

    if frame_id == "TEME":
        return TEME(obstime=obstime)
    if frame_id == "ITRF":
        return ITRS(obstime=obstime)
    if frame_id in ("GCRF", "ICRF"):
        return GCRS(obstime=obstime)
    # EME2000 / J2000: the geocentric mean equator and equinox of the J2000 epoch.
    return PrecessedGeocentric(equinox=Time("J2000"), obstime=obstime)


def _obstime(epochs: NDArray[np.datetime64], time_scale: str) -> Any:
    """Build the astropy obstime from ``epochs`` interpreted in ``time_scale``."""
    from astropy.time import Time, TimeDelta

    flat = np.atleast_1d(np.asarray(epochs, dtype="datetime64[ns]"))
    if time_scale == "GPS":
        offset = TimeDelta(_GPS_TAI_OFFSET_SECONDS, format="sec")
        return Time(flat, format="datetime64", scale="tai") + offset
    scale = _ASTROPY_SCALE.get(time_scale)
    if scale is None:
        raise ValueError(f"cannot interpret epochs in time scale {time_scale!r} for a rotation")
    return Time(flat, format="datetime64", scale=scale)
