"""Cross-validate the AEM writer's output against the dev-only ccsds-ndm oracle.

ccsds-ndm is GPL-3.0 and is never a runtime/dev dependency, never imported by the package,
and never distributed; it is installed transiently in one CI job and pulled in here only
behind :func:`pytest.importorskip`. The check is independence: the writer emits AEM (KVN and
XML), a separate CCSDS implementation parses it, and we assert it reads back the same object
id, frames, time system, and quaternion records the canonical attitude holds. ccsds-ndm reads
both the version-1 KVN and the version-2 XML the writer emits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("ccsds_ndm")

from ccsds_ndm.ndm_io import NdmIo

from orbit_formats import Attitude, read
from orbit_formats.writers.aem import write_aem

GOLDEN = Path(__file__).parent / "data" / "aem" / "golden_aem.aem"


def _quaternion(state: Any) -> Any:
    """The quaternion of an oracle attitude state, across the v1 / v2 model shapes."""
    block: Any = getattr(state, "quaternion_state", None)
    if block is None:
        block = state.quaternion_ephemeris
    return block.quaternion


def _assert_oracle_matches(aem_bytes: bytes, attitude: Attitude) -> None:
    parsed = NdmIo().from_string(aem_bytes.decode("utf-8"))
    segment = parsed.body.segment[0]
    meta = segment.metadata
    assert meta.object_id == attitude.metadata.object_id
    assert meta.ref_frame_a == attitude.frame_a
    assert meta.ref_frame_b == attitude.frame_b

    states = segment.data.attitude_state
    assert len(states) == len(attitude)
    for index, state in enumerate(states):
        quaternion = _quaternion(state)
        components = [quaternion.q1, quaternion.q2, quaternion.q3, quaternion.qc]
        np.testing.assert_allclose(components, attitude.records[index], atol=1e-9)


def test_kvn_output_is_read_consistently_by_the_oracle() -> None:
    attitude = read(GOLDEN.read_bytes())
    assert isinstance(attitude, Attitude)
    _assert_oracle_matches(write_aem(attitude, ".aem"), attitude)


def test_xml_output_is_read_consistently_by_the_oracle() -> None:
    attitude = read(GOLDEN.read_bytes())
    assert isinstance(attitude, Attitude)
    _assert_oracle_matches(write_aem(attitude, ".xml"), attitude)
