"""orbit-formats: lossless round-trip across orbital state-vector and ephemeris formats.

The public surface lives here. It exposes the canonical metamodel — the typed dataclass
family downstream consumers adopt as the single format-agnostic representation — and the
``read`` / ``write`` / ``convert`` / ``detect`` entry points, with format detection and a
registry the format readers and writers plug into as they land.
"""

from orbit_formats.api import convert, read, write
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
from orbit_formats.detect import detect
from orbit_formats.errors import (
    AmbiguousFormatError,
    FormatDetectionError,
    OrbitFormatsError,
    UnknownFormatError,
    UnsupportedConversionError,
    UnsupportedFormatError,
)
from orbit_formats.registry import register_reader, register_writer
from orbit_formats.source import Source
from orbit_formats.units import DEFAULT_UNITS, UnitSpec

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_UNITS",
    "AmbiguousFormatError",
    "Attitude",
    "Canonical",
    "Conjunction",
    "Ephemeris",
    "FidelityModel",
    "FormatDetectionError",
    "KeplerianElements",
    "MeanElementSet",
    "Metadata",
    "OrbitFormatsError",
    "Provenance",
    "Source",
    "StateVector",
    "Tracking",
    "UnitSpec",
    "UnknownFormatError",
    "UnsupportedConversionError",
    "UnsupportedFormatError",
    "__version__",
    "convert",
    "detect",
    "read",
    "register_reader",
    "register_writer",
    "write",
]
