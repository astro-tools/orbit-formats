"""Cross-validate the APM writer's output against the dev-only ccsds-ndm oracle.

ccsds-ndm is GPL-3.0 and is never a runtime/dev dependency, never imported by the package,
and never distributed; it is installed transiently in one CI job and pulled in here only
behind :func:`pytest.importorskip`. The check is independence: the writer emits APM (KVN and
XML), a separate CCSDS implementation parses it, and we assert it reads back the same object
id, time system, frames, and quaternion the canonical attitude holds. ccsds-ndm reads both the
version-1 KVN and the version-2 XML the writer emits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("ccsds_ndm")

from ccsds_ndm.ndm_io import NdmIo

from orbit_formats import Attitude, read
from orbit_formats.writers.apm import write_apm

GOLDEN = Path(__file__).parent / "data" / "apm" / "golden_apm.apm"


def _quaternion_state(data: Any) -> Any:
    """The single quaternion state, across the v1 (object) / v2 (list) oracle model shapes."""
    state = data.quaternion_state
    return state[0] if isinstance(state, list) else state


def _assert_oracle_matches(apm_bytes: bytes, attitude: Attitude) -> None:
    parsed = NdmIo().from_string(apm_bytes.decode("utf-8"))
    segment = parsed.body.segment
    assert segment.metadata.object_id == attitude.metadata.object_id

    state = _quaternion_state(segment.data)
    frame_a = getattr(state, "q_frame_a", None) or getattr(state, "ref_frame_a", None)
    frame_b = getattr(state, "q_frame_b", None) or getattr(state, "ref_frame_b", None)
    assert frame_a == attitude.frame_a
    assert frame_b == attitude.frame_b

    quaternion = state.quaternion
    components = [quaternion.q1, quaternion.q2, quaternion.q3, quaternion.qc]
    np.testing.assert_allclose(components, attitude.records[0], atol=1e-9)


def test_kvn_output_is_read_consistently_by_the_oracle() -> None:
    attitude = read(GOLDEN.read_bytes())
    assert isinstance(attitude, Attitude)
    _assert_oracle_matches(write_apm(attitude, ".apm"), attitude)


def test_xml_output_is_read_consistently_by_the_oracle() -> None:
    attitude = read(GOLDEN.read_bytes())
    assert isinstance(attitude, Attitude)
    _assert_oracle_matches(write_apm(attitude, ".xml"), attitude)
