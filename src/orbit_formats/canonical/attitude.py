"""``Attitude`` — an attitude history (CCSDS AEM) or a single attitude (CCSDS APM).

A federated category type alongside the implemented
:class:`~orbit_formats.canonical.ephemeris.Ephemeris`,
:class:`~orbit_formats.canonical.state.StateVector`, and
:class:`~orbit_formats.canonical.elements.MeanElementSet`. Where those describe *where* a
body is, ``Attitude`` describes how it is *oriented* — the rotation from one reference frame
to another, sampled at one epoch (APM) or over a time series (AEM).

Unlike the Cartesian categories there is no single numeric layout: an attitude is expressed
as a quaternion, a set of Euler angles, or a spin state, each with a different column set.
``attitude_type`` tags which representation ``records`` holds (the layouts are catalogued in
:data:`ATTITUDE_TYPES`), and ``frame_a`` / ``frame_b`` name the two frames the rotation is
expressed *between* — the metadata spine's single ``reference_frame`` cannot, so it is left
unset and the frame pair lives on the object. Per-format specifics (the AEM interpolation
block, the v1 ``ATTITUDE_DIR`` / ``QUATERNION_TYPE`` notation tags, the APM quaternion-rate
block) ride on the ``source_native`` fidelity model, keeping this schema clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.base import Canonical

__all__ = ["ATTITUDE_TYPES", "Attitude"]

# The attitude representations the canonical record models, each mapped to its ordered
# component columns. A row of ``records`` carries exactly these values, in this order —
# quaternion with the scalar last (the CCSDS ``Q1 Q2 Q3 QC`` canonical order, regardless of
# the ``QUATERNION_TYPE FIRST/LAST`` notation a source used), the three Euler angles in the
# rotation-sequence order, or the spin state. Derivative / angular-velocity / nutation
# variants are not modelled here; a reader that meets one raises rather than guessing.
ATTITUDE_TYPES: dict[str, tuple[str, ...]] = {
    "QUATERNION": ("Q1", "Q2", "Q3", "QC"),
    "EULER_ANGLE": ("ANGLE_1", "ANGLE_2", "ANGLE_3"),
    "SPIN": ("SPIN_ALPHA", "SPIN_DELTA", "SPIN_ANGLE", "SPIN_ANGLE_VEL"),
}


@dataclass(kw_only=True, eq=False)
class Attitude(Canonical):
    """An attitude history (CCSDS AEM) or single attitude (CCSDS APM).

    ``attitude_type`` is one of :data:`ATTITUDE_TYPES`; ``records`` is an ``(N, k)`` array of
    the attitude components (``k`` fixed by the type), one row per epoch in ``epochs`` (``N``
    rows — many for an AEM time series, one for an APM). ``frame_a`` and ``frame_b`` are the
    two reference frames the rotation maps between (e.g. ``EME2000`` → ``SC_BODY``);
    ``euler_rot_seq`` is the rotation sequence for the Euler representation (e.g. ``"321"``),
    ``None`` otherwise. Quaternion components are always stored scalar-last (``Q1 Q2 Q3 QC``).
    """

    attitude_type: str
    epochs: NDArray[np.datetime64]
    records: NDArray[np.float64]
    frame_a: str | None = None
    frame_b: str | None = None
    euler_rot_seq: str | None = None

    def __post_init__(self) -> None:
        if self.attitude_type not in ATTITUDE_TYPES:
            raise ValueError(
                f"unknown attitude_type {self.attitude_type!r}; "
                f"expected one of {sorted(ATTITUDE_TYPES)}"
            )
        self.epochs = np.asarray(self.epochs, dtype="datetime64[ns]")
        self.records = np.asarray(self.records, dtype=np.float64)
        width = len(ATTITUDE_TYPES[self.attitude_type])
        if self.records.ndim != 2 or self.records.shape[1] != width:
            raise ValueError(
                f"{self.attitude_type} records must have shape (N, {width}), "
                f"got {self.records.shape}"
            )
        if self.records.shape[0] != self.epochs.shape[0]:
            raise ValueError(
                f"epochs and records disagree on length: {self.epochs.shape[0]} epoch(s) "
                f"vs {self.records.shape[0]} record(s)"
            )

    def __len__(self) -> int:
        return int(self.epochs.shape[0])

    @property
    def columns(self) -> tuple[str, ...]:
        """The component column names for this attitude's representation."""
        return ATTITUDE_TYPES[self.attitude_type]

    def _eq_payload(self) -> tuple[Any, ...]:
        return (
            self.attitude_type,
            self.epochs,
            self.records,
            self.frame_a,
            self.frame_b,
            self.euler_rot_seq,
        )
