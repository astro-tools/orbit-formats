"""The federated canonical base — the metadata-spine carrier, value equality, and the
DataFrame-projection helpers shared by the state-series category types.

:class:`Canonical` is the base every category dataclass (``StateVector``, ``Ephemeris``,
``MeanElementSet``) builds on. It carries the typed
:class:`~orbit_formats.canonical.metadata.Metadata` spine and an optional
``source_native`` handle back to the format-fidelity model the object was read from, so
a same-format write recovers full fidelity without the format-specific fields ever
polluting the canonical schema. Equality is by canonical *content* — the metadata plus
the numeric payload — and deliberately excludes ``source_native``: two canonical objects
with the same content are equal regardless of which native handle (if any) is attached.

The ``*_state_frame`` helpers implement the gmat-run-identical state-series projection
(columns ``Epoch, X, Y, Z, VX, VY, VZ`` with the metadata spine on ``DataFrame.attrs``)
shared by ``Ephemeris`` (N rows) and ``StateVector`` (a single row).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata
from orbit_formats.units import DEFAULT_UNITS, UnitSpec

__all__ = ["Canonical"]

# The canonical state-series schema, reused verbatim from gmat-run so the DataFrame
# projection is schema-identical and downstream consumers need zero reshaping.
EPOCH_COLUMN = "Epoch"
STATE_COLUMNS = ["X", "Y", "Z", "VX", "VY", "VZ"]


@dataclass(kw_only=True, eq=False)
class Canonical:
    """Base for the federated canonical category types.

    Carries the :class:`Metadata` spine and the optional ``source_native`` fidelity
    handle. Equality compares canonical content (metadata + numeric payload) and ignores
    ``source_native``; instances are intentionally unhashable value objects.
    """

    metadata: Metadata
    source_native: FidelityModel | None = None

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        assert isinstance(other, Canonical)
        if self.metadata != other.metadata:
            return False
        return _payload_equal(self._eq_payload(), other._eq_payload())

    def _eq_payload(self) -> tuple[Any, ...]:
        raise NotImplementedError  # pragma: no cover - overridden by every category type


def _payload_equal(left: tuple[Any, ...], right: tuple[Any, ...]) -> bool:
    """Element-wise equality that compares numpy arrays with :func:`numpy.array_equal`."""
    if len(left) != len(right):
        return False  # pragma: no cover - payload arity is fixed per type
    for a, b in zip(left, right, strict=True):
        if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
            if not np.array_equal(a, b):
                return False
        elif a != b:
            return False
    return True


def units_to_dict(units: UnitSpec) -> dict[str, str]:
    """Project a :class:`UnitSpec` to the plain dict carried on ``DataFrame.attrs``."""
    return {
        "length": units.length,
        "speed": units.speed,
        "angle": units.angle,
        "time": units.time,
    }


def units_from_attrs(value: Any) -> UnitSpec:
    """Reconstruct a :class:`UnitSpec` from a ``DataFrame.attrs["units"]`` value."""
    if not isinstance(value, dict):
        return DEFAULT_UNITS
    return UnitSpec(
        length=value.get("length", DEFAULT_UNITS.length),
        speed=value.get("speed", DEFAULT_UNITS.speed),
        angle=value.get("angle", DEFAULT_UNITS.angle),
        time=value.get("time", DEFAULT_UNITS.time),
    )


def apply_spine_attrs(df: pd.DataFrame, metadata: Metadata) -> None:
    """Materialise the metadata spine onto ``df.attrs`` using gmat-run's flat-key names.

    Keys are set only when the corresponding value is known (mirroring gmat-run, which
    omits absent metadata), except ``units`` — always known via the :class:`UnitSpec`
    default. ``reference_frame`` is exposed under gmat-run's ``coordinate_system`` name,
    and ``epoch_scales`` mirrors gmat-run's per-column time-scale convention.
    """
    if metadata.object_name is not None:
        df.attrs["object_name"] = metadata.object_name
    if metadata.central_body is not None:
        df.attrs["central_body"] = metadata.central_body
    if metadata.reference_frame is not None:
        df.attrs["coordinate_system"] = metadata.reference_frame
    if metadata.time_scale is not None:
        df.attrs["time_scale"] = metadata.time_scale
        df.attrs["epoch_scales"] = {EPOCH_COLUMN: metadata.time_scale}
    df.attrs["units"] = units_to_dict(metadata.units)


def metadata_from_attrs(df: pd.DataFrame) -> Metadata:
    """Reconstruct the spine from a projected DataFrame's ``attrs``.

    The inverse of :func:`apply_spine_attrs` over the projected fields. Off-projection
    spine fields (``object_id`` / ``originator`` / ``provenance``) are not carried by the
    gmat-run schema and come back ``None`` — they live on the object and its
    ``source_native`` handle, not in the DataFrame.
    """
    attrs = df.attrs
    return Metadata(
        object_name=attrs.get("object_name"),
        central_body=attrs.get("central_body"),
        reference_frame=attrs.get("coordinate_system"),
        time_scale=attrs.get("time_scale"),
        units=units_from_attrs(attrs.get("units")),
    )


def build_state_frame(
    epochs: NDArray[np.datetime64],
    positions: NDArray[np.float64],
    velocities: NDArray[np.float64],
    metadata: Metadata,
    *,
    extra_attrs: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Build the canonical state frame: ``Epoch`` + ``X, Y, Z, VX, VY, VZ`` with spine attrs."""
    frame = pd.DataFrame(
        {
            EPOCH_COLUMN: epochs,
            "X": positions[:, 0],
            "Y": positions[:, 1],
            "Z": positions[:, 2],
            "VX": velocities[:, 0],
            "VY": velocities[:, 1],
            "VZ": velocities[:, 2],
        }
    )
    apply_spine_attrs(frame, metadata)
    if extra_attrs is not None:
        for key, value in extra_attrs.items():
            if value is not None:
                frame.attrs[key] = value
    return frame


def parse_state_frame_arrays(
    df: pd.DataFrame,
) -> tuple[NDArray[np.datetime64], NDArray[np.float64], NDArray[np.float64]]:
    """Extract ``(epochs, positions, velocities)`` arrays from a canonical state frame."""
    missing = [c for c in [EPOCH_COLUMN, *STATE_COLUMNS] if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame is missing required state columns: {missing}")
    epochs = np.asarray(df[EPOCH_COLUMN].to_numpy(), dtype="datetime64[ns]")
    positions = np.column_stack(
        [df["X"].to_numpy(), df["Y"].to_numpy(), df["Z"].to_numpy()]
    ).astype(np.float64)
    velocities = np.column_stack(
        [df["VX"].to_numpy(), df["VY"].to_numpy(), df["VZ"].to_numpy()]
    ).astype(np.float64)
    return epochs, positions, velocities
