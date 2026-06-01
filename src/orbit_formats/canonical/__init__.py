"""The canonical metamodel — the typed dataclass family consumers speak.

A shared metadata spine (``metadata``) tags every object with frame, time scale,
central body, object identity, units, and provenance. Category types build on it:
``StateVector`` (single state), ``Ephemeris`` (state time series), and
``MeanElementSet`` (TLE/SGP4, CCSDS OMM). Each canonical object keeps an optional
handle to its format-fidelity model (``fidelity``) so a same-format write recovers
full fidelity without polluting the canonical schema.
"""

from orbit_formats.canonical.attitude import Attitude
from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.conjunction import Conjunction, ConjunctionObject
from orbit_formats.canonical.elements import MeanElementSet
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.canonical.state import KeplerianElements, StateVector
from orbit_formats.canonical.tracking import Tracking

__all__ = [
    "Attitude",
    "Canonical",
    "Conjunction",
    "ConjunctionObject",
    "Ephemeris",
    "FidelityModel",
    "KeplerianElements",
    "MeanElementSet",
    "Metadata",
    "Provenance",
    "StateVector",
    "Tracking",
]
