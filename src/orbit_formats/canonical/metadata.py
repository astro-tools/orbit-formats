"""The shared metadata spine — frame, time scale, central body, object id, units, provenance.

Every canonical object carries this typed, validated metadata on the object itself,
never parked in a pandas ``attrs`` dict (pandas drops ``attrs`` on most operations,
which a lossless-round-trip library cannot depend on). ``to_dataframe()`` materialises
the metadata into ``DataFrame.attrs`` only at the edge.
"""

from __future__ import annotations

from dataclasses import dataclass

from orbit_formats.units import DEFAULT_UNITS, UnitSpec

__all__ = ["TIME_SCALES", "Metadata", "Provenance"]

# The time scales orbit-formats recognises: UTC, TAI, TT, TDB, GPS, and UT1. The
# conversion graph reads the tag to decide when a time-scale conversion is needed.
TIME_SCALES = frozenset({"UTC", "TAI", "TT", "TDB", "GPS", "UT1"})


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a canonical object came from — recorded, never reconstructed.

    ``orbit_formats`` records what a source *states*; it does not infer the dynamics,
    perturbations, or maneuvers that produced a trajectory (force-model attribution is
    explicitly out of scope).
    """

    source_format: str | None = None
    creation_date: str | None = None
    header: str | None = None


@dataclass(frozen=True, slots=True)
class Metadata:
    """The typed, validated tags every canonical object carries on the object itself.

    A shared spine across the federated category types: object identity (``object_name``
    / ``object_id`` / ``originator``), reference frame, central body, time scale, the
    units the numeric fields use, and provenance. ``reference_frame`` is always tagged
    and preserved; a rotation to an unsupported frame, or one requested from a canonical
    form with no Cartesian state, errors rather than guessing.
    """

    object_name: str | None = None
    object_id: str | None = None
    originator: str | None = None
    reference_frame: str | None = None
    central_body: str | None = None
    time_scale: str | None = None
    units: UnitSpec = DEFAULT_UNITS
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if self.time_scale is not None and self.time_scale not in TIME_SCALES:
            raise ValueError(
                f"unknown time_scale {self.time_scale!r}; "
                f"expected one of {sorted(TIME_SCALES)} or None"
            )
