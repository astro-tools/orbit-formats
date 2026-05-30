"""Time-scale transforms — UTC / TAI / TT / TDB / GPS / UT1, via ``astropy.time`` internally.

Reinterpreting an instant from one time scale to another (e.g. a UTC epoch as TAI) is a
lossless, bijective operation: the same physical instant, a different clock. The full set
of scales decided at kickoff is supported. ``astropy.time`` does the heavy lifting — leap
seconds for UTC<->TAI, the IERS Earth-orientation tables for UT1 — but it stays an
internal detail: the input and output are plain ``numpy.datetime64`` arrays, so the
canonical schema never exposes an astropy object.

GPS time is carried as a constant 19-second offset from TAI (its definition since 1980),
since astropy models GPS as a clock format rather than a transformable scale. UT1 needs
the IERS tables; the conversion runs with IERS auto-download disabled so it never reaches
out to the network — astropy falls back to its bundled Earth-orientation data.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.metadata import TIME_SCALES

__all__ = ["convert_time_scale"]

# astropy's transformable scales, keyed by our upper-cased scale ids. GPS is absent on
# purpose — it is handled via the constant TAI offset below.
_ASTROPY_SCALE = {"UTC": "utc", "TAI": "tai", "TT": "tt", "TDB": "tdb", "UT1": "ut1"}

# GPS time = TAI - 19 s, fixed since the GPS epoch (1980-01-06).
_GPS_TAI_OFFSET_SECONDS = 19.0


def convert_time_scale(
    epochs: NDArray[np.datetime64] | np.datetime64,
    from_scale: str,
    to_scale: str,
) -> NDArray[np.datetime64]:
    """Reinterpret ``epochs`` from ``from_scale`` to ``to_scale`` (both in :data:`TIME_SCALES`).

    ``epochs`` is a ``datetime64`` array (or a single ``datetime64``); the result has the
    same shape and ``datetime64[ns]`` resolution. Identity conversions return the epochs
    unchanged. Raises :class:`ValueError` for a scale outside the supported set.
    """
    _validate_scale(from_scale)
    _validate_scale(to_scale)

    work = np.asarray(epochs, dtype="datetime64[ns]")
    if from_scale == to_scale:
        return work

    # astropy needs IERS data only for UT1; disable auto-download so the conversion is
    # hermetic (no network) and deterministic, falling back to bundled Earth-orientation.
    from astropy.time import Time, TimeDelta
    from astropy.utils import iers

    flat = np.atleast_1d(work)
    offset = TimeDelta(_GPS_TAI_OFFSET_SECONDS, format="sec")

    with iers.conf.set_temp("auto_download", False):
        # Bring the source epochs onto the TAI scale first.
        if from_scale == "GPS":
            tai = Time(flat, format="datetime64", scale="tai") + offset
        else:
            tai = Time(flat, format="datetime64", scale=_ASTROPY_SCALE[from_scale]).tai

        # Then express TAI in the target scale.
        if to_scale == "GPS":
            converted = (tai - offset).to_value("datetime64")
        else:
            converted = getattr(tai, _ASTROPY_SCALE[to_scale]).to_value("datetime64")

    result = np.asarray(converted, dtype="datetime64[ns]").reshape(work.shape)
    return result


def _validate_scale(scale: str) -> None:
    if scale not in TIME_SCALES:
        raise ValueError(f"unknown time scale {scale!r}; expected one of {sorted(TIME_SCALES)}")
