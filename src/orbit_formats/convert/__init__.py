"""The conversion layer — route a canonical object to the form a target format prefers.

Conversions route through the canonical metamodel rather than as N-by-N bespoke format
pairs: a small explicit graph (``graph``) chains element transforms (``elements``:
Cartesian and Keplerian, given a gravitational parameter) and time-scale transforms
(``time``: UTC / TAI / TT / TDB / GPS / UT1). Frame rotation between distinct frames is
not performed here; a conversion that would require one errors clearly rather than
guessing.

The element and graph helpers are re-exported eagerly (they pull in numpy only).
``convert_time_scale`` is resolved lazily, so importing this package — and the
read / write / detect paths that route through it — does not import astropy until a
time-scale conversion is actually requested.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orbit_formats.convert.elements import (
    cartesian_to_keplerian,
    gravitational_parameter,
    keplerian_to_cartesian,
)
from orbit_formats.convert.graph import require_same_frame, route

if TYPE_CHECKING:
    from orbit_formats.convert.time import convert_time_scale

__all__ = [
    "cartesian_to_keplerian",
    "convert_time_scale",
    "gravitational_parameter",
    "keplerian_to_cartesian",
    "require_same_frame",
    "route",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the astropy-backed time helper on first access (PEP 562)."""
    if name == "convert_time_scale":
        from orbit_formats.convert.time import convert_time_scale

        return convert_time_scale
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
