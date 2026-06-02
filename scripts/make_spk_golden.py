#!/usr/bin/env python3
"""Regenerate the committed SPK golden kernel under ``tests/data/spk/golden.bsp``.

The golden is a small, fabricated two-segment SPICE SPK that the SPK reader / writer tests
read back: a **type 9** (Lagrange, unequal steps) segment for a spacecraft-style body and a
**type 13** (Hermite, unequal steps) segment for the Moon, both relative to Earth in the
J2000 frame. The state values are invented (license-clean — our own numbers), so the file
carries no third-party data; only ``spiceypy`` (the ``[spk]`` extra / dev backend) is needed
to produce it.

The byte-exact contents are not asserted by the tests (only the *content* round-trips, and
the byte-identical test echoes whatever bytes are committed), so a newer SPICE toolkit
re-emitting slightly different padding is harmless — the file just has to remain a readable
DAF/SPK. ``tests/data/** -text`` in ``.gitattributes`` keeps it byte-verbatim across platforms.

Usage::

    uv run python scripts/make_spk_golden.py

After running, review the diff and commit ``tests/data/spk/golden.bsp``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import spiceypy as spice

GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "data" / "spk" / "golden.bsp"

_EARTH = 399
_MOON = 301
_SPACECRAFT = -999
_FRAME = "J2000"


def _spacecraft_states(epochs_et: np.ndarray) -> np.ndarray:
    """A gently drifting low-Earth state series — fabricated, not a real trajectory."""
    t = epochs_et
    x = 7000.0 - 1.0e-3 * t
    y = 0.75e-2 * t
    z = np.zeros_like(t)
    vx = -0.75e-3 * t / 60.0
    vy = 7.5 - 1.0e-4 * t / 60.0
    vz = np.zeros_like(t)
    return np.column_stack([x, y, z, vx, vy, vz])


def _moon_states(epochs_et: np.ndarray) -> np.ndarray:
    """A coarse Moon-from-Earth state series — fabricated, not a real ephemeris."""
    t = epochs_et
    x = 384400.0 + 2.0 * t
    y = -1.0 * t
    z = 0.5 * t
    vx = 0.05 * np.ones_like(t)
    vy = 1.02 - 1.0e-5 * t
    vz = -0.01 * np.ones_like(t)
    return np.column_stack([x, y, z, vx, vy, vz])


def main() -> None:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    if GOLDEN.exists():
        GOLDEN.unlink()  # spkopn refuses to overwrite an existing file

    handle = spice.spkopn(str(GOLDEN), "orbit-formats SPK golden", 0)
    try:
        # Segment 1: type 9 (Lagrange, degree 3), the spacecraft relative to Earth.
        seg1_et = np.array([0.0, 600.0, 1200.0, 1800.0, 2400.0])
        seg1 = _spacecraft_states(seg1_et)
        spice.spkw09(
            handle, _SPACECRAFT, _EARTH, _FRAME, seg1_et[0], seg1_et[-1],
            "type-9 spacecraft segment", 3, len(seg1_et), seg1.tolist(), seg1_et.tolist(),
        )  # fmt: skip

        # Segment 2: type 13 (Hermite, degree 3), the Moon relative to Earth.
        seg2_et = np.array([0.0, 900.0, 1800.0, 2700.0])
        seg2 = _moon_states(seg2_et)
        spice.spkw13(
            handle, _MOON, _EARTH, _FRAME, seg2_et[0], seg2_et[-1],
            "type-13 moon segment", 3, len(seg2_et), seg2.tolist(), seg2_et.tolist(),
        )  # fmt: skip
    finally:
        spice.spkcls(handle)

    print(f"wrote {GOLDEN} ({GOLDEN.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
