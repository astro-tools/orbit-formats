"""``StateVector`` — a single Cartesian or Keplerian state at one epoch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from orbit_formats.canonical.base import (
    Canonical,
    build_state_frame,
    metadata_from_attrs,
    parse_state_frame_arrays,
)
from orbit_formats.canonical.maneuver import Maneuver

__all__ = ["KeplerianElements", "StateVector"]


@dataclass(frozen=True, slots=True)
class KeplerianElements:
    """Classical orbital elements at one epoch.

    Angles (``inclination`` / ``raan`` / ``arg_periapsis`` / ``true_anomaly``) are in the
    metadata's angle unit (degrees by default); ``semi_major_axis`` is in the length unit.
    Conversion to and from Cartesian (given a gravitational parameter) is the conversion
    layer's job — this type only *holds* the Keplerian representation.
    """

    semi_major_axis: float
    eccentricity: float
    inclination: float
    raan: float
    arg_periapsis: float
    true_anomaly: float


@dataclass(kw_only=True, eq=False)
class StateVector(Canonical):
    """A single Cartesian state at one epoch, with optional Keplerian elements.

    ``position`` and ``velocity`` are length-3 arrays in the metadata's length / speed
    units; ``keplerian`` is an optional parallel representation populated by the
    conversion layer. ``maneuvers`` holds the burns an OPM states (empty for any other
    source); each carries its own frame and Δv, and rides through the conversion layer
    but is dropped — with a named warning — by a write to a format that cannot express it.
    :meth:`to_dataframe` projects to the one-row canonical state frame.
    """

    epoch: np.datetime64
    position: NDArray[np.float64]
    velocity: NDArray[np.float64]
    keplerian: KeplerianElements | None = None
    maneuvers: tuple[Maneuver, ...] = ()

    def __post_init__(self) -> None:
        self.epoch = self.epoch.astype("datetime64[ns]")
        self.position = np.asarray(self.position, dtype=np.float64)
        self.velocity = np.asarray(self.velocity, dtype=np.float64)
        self.maneuvers = tuple(self.maneuvers)
        if self.position.shape != (3,):
            raise ValueError(f"position must have shape (3,), got {self.position.shape}")
        if self.velocity.shape != (3,):
            raise ValueError(f"velocity must have shape (3,), got {self.velocity.shape}")

    def _eq_payload(self) -> tuple[Any, ...]:
        return (self.epoch, self.position, self.velocity, self.keplerian, self.maneuvers)

    def to_dataframe(self) -> pd.DataFrame:
        """Project to a one-row state frame (``Epoch`` + ``X, Y, Z, VX, VY, VZ``).

        Same schema and ``attrs`` as :meth:`Ephemeris.to_dataframe`, with a single row.
        """
        epochs = np.array([self.epoch], dtype="datetime64[ns]")
        return build_state_frame(
            epochs, self.position[None, :], self.velocity[None, :], self.metadata
        )

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> StateVector:
        """Reconstruct a ``StateVector`` from a one-row canonical state frame."""
        epochs, positions, velocities = parse_state_frame_arrays(df)
        if epochs.shape[0] != 1:
            raise ValueError(
                f"StateVector.from_dataframe expects exactly one row, got {epochs.shape[0]}"
            )
        return cls(
            metadata=metadata_from_attrs(df),
            epoch=epochs[0],
            position=positions[0],
            velocity=velocities[0],
        )
