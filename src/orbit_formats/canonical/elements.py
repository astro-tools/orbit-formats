"""``MeanElementSet`` — a mean-element set such as a TLE/SGP4 or CCSDS OMM record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from orbit_formats.canonical.base import Canonical, apply_spine_attrs, metadata_from_attrs
from orbit_formats.errors import IncompatibleMeanElementTheoryError

__all__ = [
    "BROADCAST_MEAN_ELEMENT_THEORY",
    "SGP4_MEAN_ELEMENT_THEORY",
    "MeanElementSet",
    "ensure_convertible_to_mean_format",
]

# Named mean-element theories carried on ``MeanElementSet.mean_element_theory``. ``SGP4`` is
# the theory a TLE / OMM mean set obeys; ``GNSS broadcast`` is the quasi-Keplerian broadcast
# parameterisation a RINEX navigation record carries (a different theory in an Earth-fixed
# frame). The pair drives :func:`ensure_convertible_to_mean_format`.
SGP4_MEAN_ELEMENT_THEORY = "SGP4"
BROADCAST_MEAN_ELEMENT_THEORY = "GNSS broadcast"

# The writable mean-element formats, which are all SGP4 / TEME mean-element formats. A
# broadcast mean set cannot be written as one of these without a propagate-and-refit.
_SGP4_MEAN_ELEMENT_FORMATS = frozenset({"tle", "ccsds-omm"})

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

    ``mean_element_theory`` records *which* mean-element theory produced the elements —
    :data:`SGP4_MEAN_ELEMENT_THEORY` for a TLE / OMM, :data:`BROADCAST_MEAN_ELEMENT_THEORY`
    for a RINEX broadcast record, ``None`` when unknown. It is a semantic provenance tag, not
    part of the numeric payload: it is excluded from equality and from the DataFrame
    projection (like ``source_native`` and the off-spine metadata), and it gates conversion
    to the SGP4 mean-element formats via :func:`ensure_convertible_to_mean_format`.
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
    mean_element_theory: str | None = None

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


def ensure_convertible_to_mean_format(meanset: MeanElementSet, target_format: str) -> None:
    """Refuse converting a GNSS broadcast mean set to an SGP4 mean-element format.

    TLE and OMM are SGP4 / TEME mean-element formats. A broadcast set
    (:data:`BROADCAST_MEAN_ELEMENT_THEORY`) shares the ``mean-elements`` form but a different
    theory and an Earth-fixed frame, so the form-keyed pass-through would relabel numbers that
    mean different things. Raises :class:`~orbit_formats.errors.IncompatibleMeanElementTheoryError`
    in that case; a no-op for any other (theory, target) pair, including same-theory or
    untagged sets and non-SGP4 targets.
    """
    if (
        target_format in _SGP4_MEAN_ELEMENT_FORMATS
        and meanset.mean_element_theory == BROADCAST_MEAN_ELEMENT_THEORY
    ):
        raise IncompatibleMeanElementTheoryError(meanset.mean_element_theory, target_format)


def _optional_float(value: Any) -> float | None:
    """Round-trip a nullable numeric cell back to ``float`` or ``None``."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return float(value)
