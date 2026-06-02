"""Cross-validate the SPK writer against SPICE's own evaluator — an independent oracle.

The SPK reader/writer live behind the ``[spk]`` extra and are built on ``spiceypy``'s DAF
*segment* primitives (``spkw09`` / ``spkw13`` and the low-level DAF readers). This oracle
closes that loop with a genuinely independent path: it furnishes the kernel we wrote and asks
SPICE's high-level geometric-state evaluator (:func:`spiceypy.spkgeo`) to interpolate the
states back. ``spkgeo`` walks the SPK type-9 / type-13 interpolation machinery, not our DAF
parser, so agreement here means the bytes we emit are a valid SPK that an outside toolkit
reads as the same trajectory — not merely that we read back our own writes.

Like the CCSDS oracles, this runs only where its reference is present: ``spiceypy`` is the
``[spk]`` extra's own implementation library (so this also exercises that install path), and
the module skips wherever it is absent via :func:`pytest.importorskip`. It is named and run as
a standing CI oracle job, extending the one-off reference check that landed with the SPK
reader/writer into the external-cross-validation discipline the v1.0 charter gates on.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("spiceypy")

import spiceypy as spice

from orbit_formats import Ephemeris, Metadata, Provenance, read
from orbit_formats._spice import J2000_TDB, datetime64_to_et
from orbit_formats.writers.spk import write_spk

GOLDEN = Path(__file__).parent / "data" / "spk" / "golden.bsp"

# SPICE evaluates the geometric state from the sampled nodes by interpolation; the written
# nodes are float64 km / km·s⁻¹ and SPICE returns the same units. The residual is interpolation
# round-off at the node epochs (where the polynomial passes through the sample), so the bound is
# tight: sub-micrometre on position, sub-nm·s⁻¹ on velocity. A looser fit would mean we wrote
# the nodes or epochs wrong, which is exactly what this oracle is here to catch.
POS_ATOL_KM = 1e-6
VEL_ATOL_KM_S = 1e-9


def _assert_spice_reads_back(target: int, observer: int, eph: Ephemeris, tmp_path: Path) -> None:
    """Write ``eph`` to an SPK, furnish it, and assert SPICE's evaluator recovers its states.

    ``spkgeo`` is SPICE's own geometric-state lookup: it interpolates the segment we wrote at
    each node epoch and returns the Earth-relative state in the J2000 frame, entirely outside
    our DAF reader. We assert it matches the canonical positions / velocities node-for-node.
    """
    kernel = tmp_path / "xcheck.bsp"
    kernel.write_bytes(write_spk(eph))
    try:
        spice.furnsh(str(kernel))
        for index, et in enumerate(datetime64_to_et(eph.epochs)):
            state, _light_time = spice.spkgeo(target, float(et), "J2000", observer)
            np.testing.assert_allclose(state[:3], eph.positions[index], rtol=0, atol=POS_ATOL_KM)
            np.testing.assert_allclose(state[3:], eph.velocities[index], rtol=0, atol=VEL_ATOL_KM_S)
    finally:
        spice.unload(str(kernel))


def _synthesised_moon_ephemeris() -> Ephemeris:
    """A complete MOON/EARTH/J2000/TDB ephemeris with no SPK source — a synthesised write.

    ``MOON`` and ``EARTH`` resolve to NAIF ids and ``J2000`` is a SPICE frame, so the writer
    emits a valid SPK that SPICE can furnish and evaluate against the Moon's NAIF id.
    """
    return Ephemeris(
        metadata=Metadata(
            object_name="MOON",
            central_body="EARTH",
            reference_frame="J2000",
            time_scale="TDB",
            provenance=Provenance(source_format="synthetic"),
        ),
        epochs=J2000_TDB + np.arange(4).astype("timedelta64[s]") * 600,
        positions=np.array(
            [
                [384400.0, 0.0, 0.0],
                [384402.0, -10.0, 5.0],
                [384404.0, -20.0, 10.0],
                [384406.0, -30.0, 15.0],
            ]
        ),
        velocities=np.array([[0.05, 1.02, -0.01]] * 4),
    )


def test_spice_evaluator_reads_back_the_golden_round_trip(tmp_path: Path) -> None:
    # The two-segment golden re-emitted from the canonical ephemeris: SPICE's evaluator must
    # recover the first segment's spacecraft states (NAIF id -999, no name) node-for-node.
    eph = read(GOLDEN.read_bytes())
    assert isinstance(eph, Ephemeris)
    _assert_spice_reads_back(-999, 399, eph, tmp_path)


def test_spice_evaluator_reads_back_a_synthesised_write(tmp_path: Path) -> None:
    # A from-scratch synthesised ephemeris (no SPK source bytes): SPICE reads the kernel we
    # built against the Moon's NAIF id, confirming the synthesised write path is valid SPK too.
    eph = _synthesised_moon_ephemeris()
    _assert_spice_reads_back(spice.bodn2c("MOON"), spice.bodn2c("EARTH"), eph, tmp_path)
