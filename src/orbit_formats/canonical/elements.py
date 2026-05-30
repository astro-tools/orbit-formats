"""``MeanElementSet`` — a mean-element set such as a TLE/SGP4 or CCSDS OMM record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from orbit_formats.canonical.base import Canonical, apply_spine_attrs, metadata_from_attrs

__all__ = ["MeanElementSet"]

# Column names for the one-row mean-element projection. This is a different canonical
# category from the Cartesian state series, so it deliberately does not share the
# X/Y/Z/VX/VY/VZ schema.
_COLUMNS = [
    "Epoch",
    "MeanMotion",
    "Eccentricity",
    "Inclination",
    "RAAN",
    "ArgPeriapsis",
    "MeanAnomaly",
    "BStar",
    "MeanMotionDot",
    "MeanMotionDdot",
]


@dataclass(kw_only=True, eq=False)
class MeanElementSet(Canonical):
    """A mean-element set (TLE / SGP4 or CCSDS OMM): mean elements at an epoch.

    These are *mean* — not osculating — elements; turning them into an osculating state
    is a propagation (an sgp4 model step), out of scope for the format layer. ``mean_motion``
    is in revolutions/day and the angles are in degrees (the TLE/OMM convention).
    ``bstar`` and the mean-motion derivatives are the optional SGP4 drag terms; a pure
    Keplerian mean set leaves them ``None``. TLE-text specifics (line numbers, checksums,
    classification) live on the ``source_native`` fidelity model, and the NORAD id rides
    ``metadata.object_id``.
    """

    epoch: np.datetime64
    mean_motion: float
    eccentricity: float
    inclination: float
    raan: float
    arg_periapsis: float
    mean_anomaly: float
    bstar: float | None = None
    mean_motion_dot: float | None = None
    mean_motion_ddot: float | None = None

    def __post_init__(self) -> None:
        self.epoch = self.epoch.astype("datetime64[ns]")
        if not 0.0 <= self.eccentricity < 1.0:
            raise ValueError(f"eccentricity must be in [0, 1), got {self.eccentricity}")

    def _eq_payload(self) -> tuple[Any, ...]:
        return (
            self.epoch,
            self.mean_motion,
            self.eccentricity,
            self.inclination,
            self.raan,
            self.arg_periapsis,
            self.mean_anomaly,
            self.bstar,
            self.mean_motion_dot,
            self.mean_motion_ddot,
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Project to a one-row mean-element frame, with the metadata spine on ``attrs``."""
        frame = pd.DataFrame(
            {
                "Epoch": np.array([self.epoch], dtype="datetime64[ns]"),
                "MeanMotion": [self.mean_motion],
                "Eccentricity": [self.eccentricity],
                "Inclination": [self.inclination],
                "RAAN": [self.raan],
                "ArgPeriapsis": [self.arg_periapsis],
                "MeanAnomaly": [self.mean_anomaly],
                "BStar": [self.bstar],
                "MeanMotionDot": [self.mean_motion_dot],
                "MeanMotionDdot": [self.mean_motion_ddot],
            }
        )
        apply_spine_attrs(frame, self.metadata)
        return frame

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> MeanElementSet:
        """Reconstruct a ``MeanElementSet`` from a one-row mean-element frame."""
        missing = [c for c in _COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"DataFrame is missing required mean-element columns: {missing}")
        if len(df) != 1:
            raise ValueError(
                f"MeanElementSet.from_dataframe expects exactly one row, got {len(df)}"
            )
        row = df.iloc[0]
        return cls(
            metadata=metadata_from_attrs(df),
            epoch=np.datetime64(row["Epoch"], "ns"),
            mean_motion=float(row["MeanMotion"]),
            eccentricity=float(row["Eccentricity"]),
            inclination=float(row["Inclination"]),
            raan=float(row["RAAN"]),
            arg_periapsis=float(row["ArgPeriapsis"]),
            mean_anomaly=float(row["MeanAnomaly"]),
            bstar=_optional_float(row["BStar"]),
            mean_motion_dot=_optional_float(row["MeanMotionDot"]),
            mean_motion_ddot=_optional_float(row["MeanMotionDdot"]),
        )


def _optional_float(value: Any) -> float | None:
    """Round-trip a nullable numeric cell back to ``float`` or ``None``."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return float(value)
