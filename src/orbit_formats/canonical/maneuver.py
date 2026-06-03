"""``Maneuver`` — one impulsive or finite burn read from an OPM or OCM.

A plain sub-record (like :class:`~orbit_formats.canonical.conjunction.ConjunctionObject` and
:class:`~orbit_formats.canonical.tracking.TrackingObservation`), **not** a federated category
of its own: a maneuver belongs to the body whose state it acts on, so the canonical layer
carries it as a ``maneuvers`` collection on the
:class:`~orbit_formats.canonical.state.StateVector` an OPM reads into and the
:class:`~orbit_formats.canonical.ephemeris.Ephemeris` an OCM reads into, sharing that object's
metadata spine rather than a spine of its own.

The record holds the burn's common denominator across the two formats: the ignition epoch, the
duration (``0.0`` for an impulsive burn), the Δv vector and the reference frame it is expressed
in, and the Δ-mass when the source states it. It records *what the file states*; it does not
model or apply the burn (a charter non-goal). Format-specific detail the record has no slot for
— an OPM has none beyond these fields; an OCM ``man`` block can carry thrust, deterministic-
command timing, and per-element sigmas — stays on the ``source_native`` fidelity model, so a
same-format write is unaffected and a cross-format write reports the loss through the
no-silent-loss warning seam.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

__all__ = ["Maneuver"]


@dataclass(frozen=True, slots=True, eq=False)
class Maneuver:
    """One maneuver (impulsive or finite) read from an OPM ``MAN_*`` block or an OCM ``man`` line.

    ``epoch_ignition`` is the burn's ignition time and ``ref_frame`` the frame its ``delta_v`` is
    expressed in (e.g. ``"RTN"`` / ``"EME2000"``) — the maneuver names its own frame rather than
    borrowing the parent object's, since a burn is commonly given in RTN while the state is
    inertial. ``duration`` is in seconds (``0.0`` ⇒ an impulsive maneuver). ``delta_v`` is the
    ``(3,)`` Δv vector in km/s when the source provides it, else ``None`` (an OCM ``man`` block
    that expresses, say, thrust but no Δv leaves it unset). ``delta_mass`` is the mass change in
    kg (non-positive) when stated. ``comments`` are the block's leading ``COMMENT`` lines.
    """

    epoch_ignition: np.datetime64
    ref_frame: str
    duration: float = 0.0
    delta_v: NDArray[np.float64] | None = None
    delta_mass: float | None = None
    comments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "epoch_ignition", self.epoch_ignition.astype("datetime64[ns]"))
        object.__setattr__(self, "duration", float(self.duration))
        if self.delta_v is not None:
            delta_v = np.asarray(self.delta_v, dtype=np.float64)
            if delta_v.shape != (3,):
                raise ValueError(f"a maneuver delta_v must have shape (3,), got {delta_v.shape}")
            object.__setattr__(self, "delta_v", delta_v)
        if self.delta_mass is not None:
            object.__setattr__(self, "delta_mass", float(self.delta_mass))
        object.__setattr__(self, "comments", tuple(self.comments))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Maneuver):
            return NotImplemented
        return bool(
            self.epoch_ignition == other.epoch_ignition
            and self.ref_frame == other.ref_frame
            and self.duration == other.duration
            and _optional_array_equal(self.delta_v, other.delta_v)
            and self.delta_mass == other.delta_mass
            and self.comments == other.comments
        )


def _optional_array_equal(
    left: NDArray[np.float64] | None, right: NDArray[np.float64] | None
) -> bool:
    """Equality for an optional ``(3,)`` vector — both unset, or both set and element-wise equal."""
    if left is None or right is None:
        return left is None and right is None
    return bool(np.array_equal(left, right))
