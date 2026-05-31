"""Cross-validate the OEM writer's output against the dev-only ccsds-ndm oracle.

ccsds-ndm is GPL-3.0 and is therefore **never** a runtime, extra, or dev dependency of
orbit-formats, never imported by the package, and never distributed. It is installed
transiently in one dedicated CI job (``uv run --with ccsds-ndm``) and pulled in here only
behind :func:`pytest.importorskip`, so this module simply skips anywhere the oracle is not
present (the main test matrix, a normal local run).

The check is independence: the writer emits OEM, an entirely separate CCSDS implementation
parses it, and we assert that third party reads back the same object identity, frame, time
system, and state values the canonical ``Ephemeris`` holds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("ccsds_ndm")

from ccsds_ndm.ndm_io import NdmIo

from orbit_formats import Ephemeris, Metadata, Provenance, read
from orbit_formats.writers.oem import write_oem

GOLDEN = Path(__file__).parent / "data" / "oem" / "golden_roundtrip.oem"


def _oracle_states(oem_bytes: bytes) -> list[Any]:
    """Flatten the oracle's per-segment state vectors into one list, in file order."""
    parsed = NdmIo().from_string(oem_bytes.decode("utf-8"))
    states = []
    for segment in parsed.body.segment:
        states.extend(segment.data.state_vector)
    return states


def _assert_oracle_matches(oem_bytes: bytes, eph: Ephemeris) -> None:
    parsed = NdmIo().from_string(oem_bytes.decode("utf-8"))
    first = parsed.body.segment[0].metadata
    assert first.object_name == eph.metadata.object_name
    assert first.ref_frame == eph.metadata.reference_frame
    assert first.time_system == eph.metadata.time_scale

    states = _oracle_states(oem_bytes)
    assert len(states) == len(eph)
    for index, state in enumerate(states):
        assert np.datetime64(str(state.epoch), "ns") == eph.epochs[index]
        np.testing.assert_allclose(
            [state.x.value, state.y.value, state.z.value], eph.positions[index]
        )
        np.testing.assert_allclose(
            [state.x_dot.value, state.y_dot.value, state.z_dot.value], eph.velocities[index]
        )


def test_structural_output_is_read_consistently_by_the_oracle() -> None:
    # Tier 2: a default read (no retained bytes) re-serialises structurally; the oracle must
    # read back the same multi-segment states the canonical ephemeris carries.
    eph = read(GOLDEN.read_bytes())
    assert isinstance(eph, Ephemeris)
    _assert_oracle_matches(write_oem(eph), eph)


def _synthesised_ephemeris() -> Ephemeris:
    # An ephemeris with no OEM source_native, built from the canonical fields. The originator
    # and creation date are supplied so the OEM XML header (which requires both) is complete.
    return Ephemeris(
        metadata=Metadata(
            object_name="SAT",
            object_id="2024-001A",
            originator="ASTRO-TOOLS",
            central_body="EARTH",
            reference_frame="EME2000",
            time_scale="UTC",
            provenance=Provenance(source_format="synthetic", creation_date="2024-01-01T00:00:00"),
        ),
        epochs=np.array(["2024-01-01T00:00:00", "2024-01-01T00:01:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.123456, 1.0, -2.0], [6999.0, 60.5, 0.25]]),
        velocities=np.array([[0.001, 7.546, -0.5], [-0.1, 7.5, 0.0]]),
    )


def test_synthesised_output_is_read_consistently_by_the_oracle() -> None:
    eph = _synthesised_ephemeris()
    _assert_oracle_matches(write_oem(eph), eph)


def test_structural_xml_output_is_read_consistently_by_the_oracle() -> None:
    # The XML notation re-emitted from a read OEM: an independent CCSDS implementation must
    # read back the same multi-segment states.
    eph = read(GOLDEN.read_bytes())
    assert isinstance(eph, Ephemeris)
    _assert_oracle_matches(write_oem(eph, ".xml"), eph)


def test_synthesised_xml_output_is_read_consistently_by_the_oracle() -> None:
    eph = _synthesised_ephemeris()
    _assert_oracle_matches(write_oem(eph, ".xml"), eph)
