"""orbit-formats: lossless round-trip across orbital state-vector and ephemeris formats.

The public surface lives here. This release exposes the canonical metamodel — the typed
dataclass family downstream consumers adopt as the single format-agnostic representation.
The ``read`` / ``write`` / ``convert`` / ``detect`` entry points join it as the format
readers, writers, and conversion graph land.
"""

from orbit_formats.canonical import (
    Attitude,
    Canonical,
    Conjunction,
    Ephemeris,
    FidelityModel,
    KeplerianElements,
    MeanElementSet,
    Metadata,
    Provenance,
    StateVector,
    Tracking,
)
from orbit_formats.units import DEFAULT_UNITS, UnitSpec

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_UNITS",
    "Attitude",
    "Canonical",
    "Conjunction",
    "Ephemeris",
    "FidelityModel",
    "KeplerianElements",
    "MeanElementSet",
    "Metadata",
    "Provenance",
    "StateVector",
    "Tracking",
    "UnitSpec",
    "__version__",
]
