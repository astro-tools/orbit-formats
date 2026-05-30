"""Unit handling — ``astropy.units`` internally, plain numpy floats with unit metadata out.

The library uses ``astropy.units`` for unit safety inside the conversion layer (see
:mod:`orbit_formats.convert`). The canonical schema itself never exposes astropy
objects: state values are plain :class:`numpy.float64` and the units they are expressed
in travel beside them as the small, declarative :class:`UnitSpec` recorded on every
canonical object's metadata and materialised onto ``DataFrame.attrs["units"]`` at the
edge. A consumer reading a result therefore never needs astropy installed.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DEFAULT_UNITS", "UnitSpec"]


@dataclass(frozen=True, slots=True)
class UnitSpec:
    """The physical units a canonical object's numeric fields are expressed in.

    Plain unit *strings* — not astropy objects — so the canonical schema stays
    astropy-free on the way out. ``length`` applies to position components, ``speed`` to
    velocity components, ``angle`` to orbital angles, and ``time`` to the time base of
    rates and durations.
    """

    length: str = "km"
    speed: str = "km/s"
    angle: str = "deg"
    time: str = "s"


DEFAULT_UNITS = UnitSpec()
"""The astro-tools canonical default units: kilometres, km/s, degrees, seconds."""
