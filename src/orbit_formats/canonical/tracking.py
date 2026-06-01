"""``Tracking`` — a tracking-data set (CCSDS TDM): timed observations and their participants.

A federated category type alongside the implemented
:class:`~orbit_formats.canonical.ephemeris.Ephemeris`,
:class:`~orbit_formats.canonical.state.StateVector`,
:class:`~orbit_formats.canonical.elements.MeanElementSet`,
:class:`~orbit_formats.canonical.attitude.Attitude`, and
:class:`~orbit_formats.canonical.conjunction.Conjunction`. Where those describe *where* or
*how oriented* a body is, ``Tracking`` carries the raw radiometric and angular measurements a
ground station records about it — range, Doppler, angles, frequencies, meteorological terms —
as a flat sequence of timed :class:`TrackingObservation` triples, tagged with the tracking
``participants`` (the ground stations and spacecraft the observations relate).

A TDM is heterogeneous: each observation is a single ``(type, epoch, value)`` triple, and the
types vary row to row, so there is no single Cartesian or quaternion layout the state-series
categories use. Each observation therefore stands alone. The full per-segment TDM metadata —
the mode, signal path, bands, integration, delays, corrections, and the rest — rides on the
``source_native`` fidelity model rather than the canonical spine, which carries only the
originator and the time scale; a multi-segment TDM is flattened into one observation sequence
with the participants and time scale taken from the first segment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from orbit_formats.canonical.base import Canonical

__all__ = ["Tracking", "TrackingObservation"]


@dataclass(frozen=True, slots=True)
class TrackingObservation:
    """One tracking observation: its measurement type, epoch, and scalar value.

    ``observation_type`` is the CCSDS TDM observation keyword (e.g. ``"RANGE"``,
    ``"DOPPLER_INSTANTANEOUS"``, ``"ANGLE_1"``); ``epoch`` is the measurement time; ``value`` is
    the scalar reading in the units the segment's metadata declares (range units, angle type,
    and so on live on the ``source_native`` model, not on each observation).
    """

    observation_type: str
    epoch: np.datetime64
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "epoch", self.epoch.astype("datetime64[ns]"))
        object.__setattr__(self, "value", float(self.value))


@dataclass(kw_only=True, eq=False)
class Tracking(Canonical):
    """A tracking-data set (CCSDS TDM): its participants and a flat observation sequence.

    ``participants`` is the ordered tuple of tracking participants (the TDM ``PARTICIPANT_1`` …
    ``PARTICIPANT_5`` — ground stations and the tracked spacecraft); ``observations`` is the
    full sequence of :class:`TrackingObservation` triples, in file order, concatenated across
    every segment of a multi-segment message. The metadata spine carries the originator and the
    time scale; everything format-specific rides on ``source_native``.
    """

    participants: tuple[str, ...]
    observations: tuple[TrackingObservation, ...]

    def __post_init__(self) -> None:
        self.participants = tuple(self.participants)
        self.observations = tuple(self.observations)

    def __len__(self) -> int:
        return len(self.observations)

    def _eq_payload(self) -> tuple[Any, ...]:
        return (self.participants, self.observations)
