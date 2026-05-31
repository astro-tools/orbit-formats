"""Cross-validate the OMM writer's output against the dev-only ccsds-ndm oracle.

ccsds-ndm is GPL-3.0 and is never a runtime/dev dependency, never imported by the package,
and never distributed; it is installed transiently in one CI job and pulled in here only
behind :func:`pytest.importorskip`. The check is independence: the writer emits OMM (KVN and
XML), a separate CCSDS implementation parses it, and we assert it reads back the same object
id, frame, time system, mean-element theory, and mean elements the canonical set holds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("ccsds_ndm")

from ccsds_ndm.ndm_io import NdmIo

from orbit_formats import MeanElementSet, read
from orbit_formats.writers.omm import write_omm

GOLDEN = Path(__file__).parent / "data" / "omm" / "golden_omm.omm"

TLE_ISS = (
    b"ISS (ZARYA)\n"
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)


def _assert_oracle_matches(
    omm_bytes: bytes, mean_set: MeanElementSet, *, object_id: str | None = None
) -> None:
    # OMM OBJECT_ID is the international designator, which differs from the canonical
    # object_id (the catalog number) for a TLE-derived OMM; the caller names the expected id.
    expected_object_id = object_id if object_id is not None else mean_set.metadata.object_id
    parsed = NdmIo().from_string(omm_bytes.decode("utf-8"))
    metadata = parsed.body.segment.metadata
    assert metadata.object_id == expected_object_id
    assert metadata.ref_frame == mean_set.metadata.reference_frame
    assert metadata.time_system == mean_set.metadata.time_scale

    elements: Any = parsed.body.segment.data.mean_elements
    assert float(elements.mean_motion.value) == pytest.approx(mean_set.mean_motion)
    assert float(elements.eccentricity) == pytest.approx(mean_set.eccentricity)
    assert float(elements.inclination.value) == pytest.approx(mean_set.inclination)
    assert float(elements.ra_of_asc_node.value) == pytest.approx(mean_set.raan)
    assert float(elements.arg_of_pericenter.value) == pytest.approx(mean_set.arg_periapsis)
    assert float(elements.mean_anomaly.value) == pytest.approx(mean_set.mean_anomaly)
    assert np.datetime64(str(elements.epoch), "ns") == mean_set.epoch


def test_kvn_output_is_read_consistently_by_the_oracle() -> None:
    mean_set = read(GOLDEN.read_bytes())
    assert isinstance(mean_set, MeanElementSet)
    _assert_oracle_matches(write_omm(mean_set, ".omm"), mean_set)


def test_xml_output_is_read_consistently_by_the_oracle() -> None:
    mean_set = read(GOLDEN.read_bytes())
    assert isinstance(mean_set, MeanElementSet)
    _assert_oracle_matches(write_omm(mean_set, ".xml"), mean_set)


def test_tle_derived_omm_is_read_consistently_by_the_oracle() -> None:
    # A synthesised OMM (from the ISS TLE) must also satisfy the independent parser. Its
    # OBJECT_ID is the international designator derived from the TLE.
    mean_set = read(TLE_ISS)
    assert isinstance(mean_set, MeanElementSet)
    _assert_oracle_matches(write_omm(mean_set, ".omm"), mean_set, object_id="1998-067A")
