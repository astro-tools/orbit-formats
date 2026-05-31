"""Cross-validate the OPM writer's output against the dev-only ccsds-ndm oracle.

ccsds-ndm is GPL-3.0 and is never a runtime/dev dependency, never imported by the package,
and never distributed; it is installed transiently in one CI job and pulled in here only
behind :func:`pytest.importorskip`. The check is independence: the writer emits OPM (KVN and
XML), a separate CCSDS implementation parses it, and we assert it reads back the same object
id, frame, time system, epoch, and Cartesian state the canonical state holds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("ccsds_ndm")

from ccsds_ndm.ndm_io import NdmIo

from orbit_formats import StateVector, read
from orbit_formats.writers.opm import write_opm

GOLDEN = Path(__file__).parent / "data" / "opm" / "golden_opm.opm"


def _assert_oracle_matches(opm_bytes: bytes, state: StateVector) -> None:
    parsed = NdmIo().from_string(opm_bytes.decode("utf-8"))
    metadata = parsed.body.segment.metadata
    assert metadata.object_id == state.metadata.object_id
    assert metadata.ref_frame == state.metadata.reference_frame
    assert metadata.time_system == state.metadata.time_scale

    vector: Any = parsed.body.segment.data.state_vector
    assert np.datetime64(str(vector.epoch), "ns") == state.epoch
    position = [float(vector.x.value), float(vector.y.value), float(vector.z.value)]
    velocity = [float(vector.x_dot.value), float(vector.y_dot.value), float(vector.z_dot.value)]
    assert position == pytest.approx(list(state.position))
    assert velocity == pytest.approx(list(state.velocity))


def test_kvn_output_is_read_consistently_by_the_oracle() -> None:
    state = read(GOLDEN.read_bytes())
    assert isinstance(state, StateVector)
    _assert_oracle_matches(write_opm(state, ".opm"), state)


def test_xml_output_is_read_consistently_by_the_oracle() -> None:
    state = read(GOLDEN.read_bytes())
    assert isinstance(state, StateVector)
    _assert_oracle_matches(write_opm(state, ".xml"), state)
