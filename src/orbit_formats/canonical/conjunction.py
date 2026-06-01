"""``Conjunction`` — a close-approach record between two objects (CCSDS CDM).

A federated category type alongside the implemented
:class:`~orbit_formats.canonical.ephemeris.Ephemeris`,
:class:`~orbit_formats.canonical.state.StateVector`,
:class:`~orbit_formats.canonical.elements.MeanElementSet`, and
:class:`~orbit_formats.canonical.attitude.Attitude`. Where those describe a *single* body,
a ``Conjunction`` relates *two*: the time of closest approach, the miss distance, the
relative position/velocity in the RTN frame, and — per object — its identity, its Cartesian
state at TCA, and its position/velocity covariance in RTN.

The metadata spine cannot carry a two-body record: its single ``object_name`` / ``object_id``
and ``reference_frame`` describe one body, so the per-object identity and frame live on the
two :class:`ConjunctionObject` entries and the spine carries only the primary object (the CDM
``OBJECT1``) and the message originator, with ``reference_frame`` left unset (the relative
state is RTN; each object names its own frame). The CDM has no ``TIME_SYSTEM`` keyword — its
epochs are UTC by convention — so the spine's ``time_scale`` is ``UTC``. Format-specific
fields (the screen-volume block, OD / additional parameters, the extended drag / SRP / thrust
covariance terms) ride on the ``source_native`` fidelity model, keeping this schema lean.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.base import Canonical

__all__ = ["Conjunction", "ConjunctionObject"]


@dataclass(frozen=True, eq=False)
class ConjunctionObject:
    """One of the two objects in a conjunction: its identity, state, and RTN covariance.

    ``label`` is the CDM slot (``"OBJECT1"`` / ``"OBJECT2"``); ``object_designator`` the
    catalogue designator. ``state`` is the ``(6,)`` Cartesian state at TCA — ``X, Y, Z`` (km)
    and ``X_DOT, Y_DOT, Z_DOT`` (km/s) — expressed in ``ref_frame``; ``covariance`` is the
    ``(6, 6)`` symmetric position/velocity covariance in the RTN frame (metre-based, axis
    order ``R, T, N, Ṙ, Ṫ, Ṅ``). The optional identity fields (``object_name`` /
    ``catalog_name`` / ``international_designator``) are present when the CDM states them.
    """

    label: str
    object_designator: str
    ref_frame: str
    state: NDArray[np.float64]
    covariance: NDArray[np.float64]
    object_name: str | None = None
    catalog_name: str | None = None
    international_designator: str | None = None

    def __post_init__(self) -> None:
        state = np.asarray(self.state, dtype=np.float64)
        covariance = np.asarray(self.covariance, dtype=np.float64)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "covariance", covariance)
        if state.shape != (6,):
            raise ValueError(f"a conjunction object state must have shape (6,), got {state.shape}")
        if covariance.shape != (6, 6):
            raise ValueError(
                f"a conjunction object covariance must have shape (6, 6), got {covariance.shape}"
            )


@dataclass(kw_only=True, eq=False)
class Conjunction(Canonical):
    """A two-object conjunction (CCSDS CDM): TCA, miss distance, relative state, two objects.

    ``tca`` is the time of closest approach; ``miss_distance`` the separation at TCA in metres.
    ``relative_speed`` (m/s), ``relative_position`` and ``relative_velocity`` (each a ``(3,)``
    RTN vector, metres and m/s) are present when the CDM carries the relative-state block, else
    ``None``. ``objects`` is the ``(OBJECT1, OBJECT2)`` pair. The metadata spine tags the
    primary object and the originator; its ``time_scale`` is ``UTC`` (the CDM convention).
    """

    tca: np.datetime64
    miss_distance: float
    objects: tuple[ConjunctionObject, ConjunctionObject]
    relative_speed: float | None = None
    relative_position: NDArray[np.float64] | None = None
    relative_velocity: NDArray[np.float64] | None = None

    def __post_init__(self) -> None:
        self.tca = self.tca.astype("datetime64[ns]")
        if len(self.objects) != 2:
            raise ValueError(f"a conjunction relates exactly two objects, got {len(self.objects)}")
        self.relative_position = _as_triplet(self.relative_position, "relative_position")
        self.relative_velocity = _as_triplet(self.relative_velocity, "relative_velocity")

    def _eq_payload(self) -> tuple[Any, ...]:
        payload: list[Any] = [
            self.tca,
            self.miss_distance,
            self.relative_speed,
            self.relative_position,
            self.relative_velocity,
        ]
        for obj in self.objects:
            payload += [
                obj.label,
                obj.object_designator,
                obj.ref_frame,
                obj.state,
                obj.covariance,
                obj.object_name,
                obj.catalog_name,
                obj.international_designator,
            ]
        return tuple(payload)


def _as_triplet(value: Any, name: str) -> NDArray[np.float64] | None:
    """Coerce an optional relative-state vector to a ``(3,)`` float array (or ``None``)."""
    if value is None:
        return None
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (3,):
        raise ValueError(f"{name} must have shape (3,), got {array.shape}")
    return array
