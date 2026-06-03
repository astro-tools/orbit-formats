"""``Ephemeris`` — a state-vector time series with a ``to_dataframe()`` projection.

The DataFrame projection matches gmat-run's schema verbatim — columns ``X, Y, Z, VX,
VY, VZ`` with ``coordinate_system`` / ``central_body`` / ``time_scale`` / ``object_name``
on ``DataFrame.attrs``, extended with ``units`` and ``interpolation`` — so downstream
consumers need zero reshaping.
"""

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

__all__ = ["Ephemeris"]


@dataclass(kw_only=True, eq=False)
class Ephemeris(Canonical):
    """A Cartesian state-vector time series.

    ``epochs`` is a length-N ``datetime64[ns]`` array in the metadata's time scale;
    ``positions`` and ``velocities`` are ``(N, 3)`` arrays in the length / speed units.
    ``interpolation`` / ``interpolation_degree`` carry the source ephemeris's
    interpolation hint. A multi-segment source (e.g. a multi-segment OEM) is concatenated
    into one canonical ephemeris here; the per-segment detail is preserved on the
    ``source_native`` fidelity model. ``maneuvers`` holds the burns an OCM states (empty for
    any other source); each carries its own frame and Δv, and rides through the conversion
    layer but is dropped — with a named warning — by a write to a format that cannot express
    it.
    """

    epochs: NDArray[np.datetime64]
    positions: NDArray[np.float64]
    velocities: NDArray[np.float64]
    interpolation: str | None = None
    interpolation_degree: int | None = None
    maneuvers: tuple[Maneuver, ...] = ()

    def __post_init__(self) -> None:
        self.epochs = np.asarray(self.epochs, dtype="datetime64[ns]")
        self.positions = np.asarray(self.positions, dtype=np.float64)
        self.velocities = np.asarray(self.velocities, dtype=np.float64)
        self.maneuvers = tuple(self.maneuvers)
        if self.epochs.ndim != 1:
            raise ValueError(f"epochs must be 1-D, got shape {self.epochs.shape}")
        n = self.epochs.shape[0]
        if self.positions.shape != (n, 3):
            raise ValueError(f"positions must have shape ({n}, 3), got {self.positions.shape}")
        if self.velocities.shape != (n, 3):
            raise ValueError(f"velocities must have shape ({n}, 3), got {self.velocities.shape}")

    def __len__(self) -> int:
        return int(self.epochs.shape[0])

    def _eq_payload(self) -> tuple[Any, ...]:
        return (
            self.epochs,
            self.positions,
            self.velocities,
            self.interpolation,
            self.interpolation_degree,
            self.maneuvers,
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Project to the gmat-run-identical state frame.

        Columns ``Epoch`` (``datetime64[ns]``) + ``X, Y, Z, VX, VY, VZ`` (``float64``);
        ``df.attrs`` carries ``object_name`` / ``central_body`` / ``coordinate_system`` /
        ``time_scale`` (set when known), ``units``, ``epoch_scales``, and
        ``interpolation`` / ``interpolation_degree`` when present. The projection is the
        canonical *edge* form: provenance and the ``source_native`` handle live on the
        object, not in the DataFrame. No astropy objects leak — values are plain numpy.
        """
        extra_attrs = {
            "interpolation": self.interpolation,
            "interpolation_degree": self.interpolation_degree,
        }
        return build_state_frame(
            self.epochs, self.positions, self.velocities, self.metadata, extra_attrs=extra_attrs
        )

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> Ephemeris:
        """Reconstruct an ``Ephemeris`` from a canonical state frame.

        The inverse of :meth:`to_dataframe` over the projected fields — the round-trip
        ``object -> to_dataframe -> from_dataframe`` reproduces the projected content
        without drift. Also the construction path a producer (e.g. the GMAT-report
        reader) uses to build an ``Ephemeris`` from a parsed table.
        """
        epochs, positions, velocities = parse_state_frame_arrays(df)
        interpolation_degree = df.attrs.get("interpolation_degree")
        return cls(
            metadata=metadata_from_attrs(df),
            epochs=epochs,
            positions=positions,
            velocities=velocities,
            interpolation=df.attrs.get("interpolation"),
            interpolation_degree=(
                None if interpolation_degree is None else int(interpolation_degree)
            ),
        )
