"""The CCSDS CDM KVN reader and writer, and the canonical :class:`Conjunction` projection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Conjunction,
    ConjunctionObject,
    MalformedSourceError,
    Metadata,
    UnsupportedConversionError,
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.ccsds_cdm import CdmFile
from orbit_formats.writers.cdm import write_cdm

DATA = Path(__file__).parent / "data" / "cdm"
GOLDEN_KVN = DATA / "golden_cdm.cdm"


# --- reader ----------------------------------------------------------------------------


def test_read_kvn_returns_a_two_object_conjunction() -> None:
    conj = read(GOLDEN_KVN.read_bytes())
    assert isinstance(conj, Conjunction)
    assert [obj.label for obj in conj.objects] == ["OBJECT1", "OBJECT2"]
    assert conj.objects[0].object_designator == "12345"
    assert conj.objects[1].object_designator == "30337"
    assert conj.miss_distance == pytest.approx(715.0)
    assert conj.tca == np.datetime64("2010-03-13T22:37:52.618", "ns")


def test_read_kvn_tags_the_spine_with_the_primary_object_and_utc() -> None:
    conj = read(GOLDEN_KVN.read_bytes())
    assert conj.metadata.object_id == "12345"
    assert conj.metadata.object_name == "SATELLITE A"
    assert conj.metadata.originator == "JSPOC"
    assert conj.metadata.time_scale == "UTC"
    assert conj.metadata.reference_frame is None  # per-object frames live on the objects
    native = conj.source_native
    assert isinstance(native, CdmFile)
    assert native.serialization == "kvn"


def test_read_kvn_carries_the_relative_state_and_a_symmetric_covariance() -> None:
    conj = read(GOLDEN_KVN.read_bytes())
    assert isinstance(conj, Conjunction)
    assert conj.relative_position is not None
    assert conj.relative_velocity is not None
    np.testing.assert_allclose(conj.relative_position, [27.4, -70.2, 711.8])
    np.testing.assert_allclose(conj.relative_velocity, [-7.2, -14692.0, -1437.2])
    cov = conj.objects[0].covariance
    assert cov.shape == (6, 6)
    np.testing.assert_array_equal(cov, cov.T)
    assert cov[0, 0] == pytest.approx(41.42)  # CR_R
    assert cov[1, 0] == pytest.approx(-8.579)  # CT_R


def test_read_kvn_keeps_optional_blocks_on_the_fidelity_model() -> None:
    native = read(GOLDEN_KVN.read_bytes()).source_native
    assert isinstance(native, CdmFile)
    od = native.objects[0].od_parameters
    assert od is not None
    assert od.obs_available == 592
    add = native.objects[0].additional_parameters
    assert add is not None
    assert add.mass == pytest.approx(251.6)
    # Object 2 carries neither optional block.
    assert native.objects[1].od_parameters is None
    assert native.objects[1].additional_parameters is None


# --- writer round-trips ----------------------------------------------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    golden = GOLDEN_KVN.read_bytes()
    conj = read(golden, retain_source=True)
    assert write_cdm(conj, ".cdm") == golden


def test_default_round_trip_is_byte_stable_against_the_golden() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_cdm(read(golden), ".cdm") == golden


def test_public_write_round_trips_through_a_path(tmp_path: Path) -> None:
    conj = read(GOLDEN_KVN.read_bytes())
    destination = tmp_path / "out.cdm"
    write(conj, destination)
    assert read(destination) == conj


def test_writing_a_non_conjunction_is_unsupported() -> None:
    from orbit_formats import StateVector

    state = StateVector(
        metadata=Metadata(time_scale="UTC"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.zeros(3),
        velocity=np.zeros(3),
    )
    with pytest.raises(UnsupportedConversionError):
        write_cdm(state, ".cdm")


# --- detection and conversion ----------------------------------------------------------


def test_detect_and_convert_passthrough(tmp_path: Path) -> None:
    assert detect_format(GOLDEN_KVN.read_bytes()) == "ccsds-cdm"
    conj = read(GOLDEN_KVN.read_bytes())
    # A conjunction is already in the CDM's preferred form — convert returns it unchanged.
    assert convert(conj, "ccsds-cdm") is conj


# --- synthesised CDM from a bare canonical conjunction ---------------------------------


def _bare_conjunction() -> Conjunction:
    objects = (
        ConjunctionObject(
            label="OBJECT1",
            object_designator="111",
            ref_frame="EME2000",
            state=np.arange(6, dtype=np.float64),
            covariance=np.eye(6, dtype=np.float64),
        ),
        ConjunctionObject(
            label="OBJECT2",
            object_designator="222",
            ref_frame="EME2000",
            state=np.arange(10, 16, dtype=np.float64),
            covariance=2.0 * np.eye(6, dtype=np.float64),
        ),
    )
    return Conjunction(
        metadata=Metadata(time_scale="UTC"),
        tca=np.datetime64("2024-03-13T22:37:52", "ns"),
        miss_distance=500.0,
        objects=objects,
    )


def test_synthesised_cdm_warns_for_each_unsupplied_required_field(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    conj = _bare_conjunction()
    assert_no_silent_loss(lambda: write_cdm(conj, ".cdm"), loses=True)
    out = write_cdm(conj, ".cdm")
    assert b"UNKNOWN" in out  # the placeholder for fields the canonical record cannot supply
    # The synthesised CDM still parses back into a two-object conjunction.
    assert isinstance(read(out), Conjunction)


def test_golden_round_trip_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    conj = read(GOLDEN_KVN.read_bytes())
    assert_no_silent_loss(lambda: write_cdm(conj, ".cdm"), loses=False)


# --- malformed input -------------------------------------------------------------------


def test_missing_version_is_rejected() -> None:
    without_version = GOLDEN_KVN.read_bytes().replace(b"CCSDS_CDM_VERS = 1.0\n", b"")
    with pytest.raises(MalformedSourceError, match="CCSDS_CDM_VERS"):
        read(without_version, format="ccsds-cdm")


def test_a_cdm_must_carry_exactly_two_objects() -> None:
    one_object = GOLDEN_KVN.read_bytes().split(b"\nCOMMENT Object2")[0]
    with pytest.raises(MalformedSourceError, match="exactly two objects"):
        read(one_object, format="ccsds-cdm")


def test_a_missing_covariance_element_is_rejected() -> None:
    no_cr_r = GOLDEN_KVN.read_bytes().replace(b"CR_R = 41.42 [m**2]\n", b"", 1)
    with pytest.raises(MalformedSourceError, match="missing required element"):
        read(no_cr_r, format="ccsds-cdm")


def test_a_partial_relative_state_block_is_rejected() -> None:
    no_n = GOLDEN_KVN.read_bytes().replace(b"RELATIVE_POSITION_N = 711.8 [m]\n", b"")
    with pytest.raises(MalformedSourceError, match="RELATIVE_POSITION is incomplete"):
        read(no_n, format="ccsds-cdm")


def test_an_unexpected_keyword_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="unexpected keyword"):
        read(b"CCSDS_CDM_VERS = 1.0\nNONSENSE_KEY = 5\n", format="ccsds-cdm")
