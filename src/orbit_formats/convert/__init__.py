"""The conversion layer — route a canonical object to the form and frame a target format wants.

Conversions route through the canonical metamodel rather than as N-by-N bespoke format
pairs: a small explicit graph (``graph``) chains element transforms (``elements``:
Cartesian and Keplerian, given a gravitational parameter), reference-frame rotations
(``frames``: TEME / EME2000 / GCRF / ICRF / ITRF), and time-scale transforms (``time``:
UTC / TAI / TT / TDB / GPS / UT1). A rotation between two genuinely unsupported frames
errors clearly rather than guessing.

The element, frame, and graph helpers are re-exported eagerly (they pull in numpy only at
import; the frame and time helpers import astropy lazily, on the first rotation or
time-scale conversion). ``convert_time_scale`` is resolved lazily, so importing this
package — and the read / write / detect paths that route through it — does not import
astropy until a transform that needs it actually runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orbit_formats.convert.capabilities import (
    ConversionCapability,
    ConversionKind,
    capability_matrix,
    conversion_capability,
)
from orbit_formats.convert.elements import (
    cartesian_to_keplerian,
    gravitational_parameter,
    keplerian_to_cartesian,
)
from orbit_formats.convert.frames import normalize_frame, rotate_state, transform_available
from orbit_formats.convert.geodetic import (
    Ellipsoid,
    GeodeticLocation,
    cartesian_to_geodetic,
    geodetic_to_cartesian,
)
from orbit_formats.convert.graph import apply_frame, conversion_edges, route

if TYPE_CHECKING:
    from orbit_formats.convert.time import convert_time_scale

__all__ = [
    "ConversionCapability",
    "ConversionKind",
    "Ellipsoid",
    "GeodeticLocation",
    "apply_frame",
    "capability_matrix",
    "cartesian_to_geodetic",
    "cartesian_to_keplerian",
    "conversion_capability",
    "conversion_edges",
    "convert_time_scale",
    "geodetic_to_cartesian",
    "gravitational_parameter",
    "keplerian_to_cartesian",
    "normalize_frame",
    "rotate_state",
    "route",
    "transform_available",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the astropy-backed time helper on first access (PEP 562)."""
    if name == "convert_time_scale":
        from orbit_formats.convert.time import convert_time_scale

        return convert_time_scale
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
