"""The in-house CCSDS APM (KVN) reader and writer: APM <-> a one-row canonical Attitude.

A single quaternion attitude parses into the faithful :class:`ApmFile` fidelity model and
adapts to a one-row :class:`Attitude`; the writer re-emits it with byte-identical (opt-in),
content-lossless, and synthesised tiers. APM is the attitude analogue of OPM.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Attitude,
    MalformedSourceError,
    Metadata,
    UnsupportedConversionError,
    detect_format,
    read,
)
from orbit_formats.readers.ccsds_apm import ApmFile, read_apm
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.apm import write_apm

GOLDEN_KVN = Path(__file__).parent / "data" / "apm" / "golden_apm.apm"

APM_KVN = b"""CCSDS_APM_VERS = 1.0
CREATION_DATE = 2024-03-01T12:00:00
ORIGINATOR = ORBIT-FORMATS

META_START
COMMENT single quaternion attitude
OBJECT_NAME = OF-SAT
OBJECT_ID = 2024-018A
CENTER_NAME = EARTH
TIME_SYSTEM = UTC
META_STOP

EPOCH = 2024-03-01T00:00:00
Q_FRAME_A = EME2000
Q_FRAME_B = SC_BODY
Q_DIR = A2B
Q1 = 0.195286
Q2 = -0.079460
Q3 = 0.318876
QC = 0.924049
"""


def test_reader_and_writer_are_registered_for_ccsds_apm() -> None:
    assert get_reader("ccsds-apm") is read_apm
    assert get_writer("ccsds-apm") is write_apm


def test_apm_signature_is_detected() -> None:
    assert detect_format(APM_KVN) == "ccsds-apm"


def test_read_returns_a_single_row_attitude() -> None:
    att = read(APM_KVN)
    assert isinstance(att, Attitude)
    assert att.attitude_type == "QUATERNION"
    assert len(att) == 1
    assert att.frame_a == "EME2000"
    assert att.frame_b == "SC_BODY"
    assert att.epochs[0] == np.datetime64("2024-03-01T00:00:00", "ns")
    np.testing.assert_allclose(att.records[0], [0.195286, -0.079460, 0.318876, 0.924049])


def test_read_tags_the_spine_from_the_apm() -> None:
    md = read(APM_KVN).metadata
    assert md.object_name == "OF-SAT"
    assert md.object_id == "2024-018A"
    assert md.central_body == "EARTH"
    assert md.time_scale == "UTC"
    assert md.reference_frame is None
    assert md.provenance is not None
    assert md.provenance.source_format == "ccsds-apm"


def test_source_native_retains_the_full_apm_fidelity_model() -> None:
    apm = read(APM_KVN).source_native
    assert isinstance(apm, ApmFile)
    assert apm.ccsds_version == "1.0"
    assert apm.serialization == "kvn"
    assert apm.metadata.comments == ("single quaternion attitude",)
    assert apm.quaternion.q_dir == "A2B"
    assert apm.quaternion.qc == pytest.approx(0.924049)


def test_a_quaternion_rate_block_round_trips() -> None:
    with_rate = APM_KVN.rstrip() + (
        b"\nQ1_DOT = 0.001\nQ2_DOT = 0.002\nQ3_DOT = 0.003\nQC_DOT = 0.004\n"
    )
    apm = read(with_rate).source_native
    assert isinstance(apm, ApmFile)
    assert apm.quaternion.q1_dot == pytest.approx(0.001)
    assert apm.quaternion.qc_dot == pytest.approx(0.004)
    assert read(write_apm(read(with_rate), ".apm")) == read(with_rate)


# --- malformed / unsupported inputs ----------------------------------------------------


def test_missing_version_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="CCSDS_APM_VERS"):
        read(APM_KVN.replace(b"CCSDS_APM_VERS = 1.0\n", b""), format="ccsds-apm")


def test_missing_required_metadata_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="OBJECT_ID"):
        read(APM_KVN.replace(b"OBJECT_ID = 2024-018A\n", b""), format="ccsds-apm")


def test_a_missing_quaternion_field_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="QC"):
        read(APM_KVN.replace(b"QC = 0.924049\n", b""), format="ccsds-apm")


def test_a_partial_quaternion_rate_is_rejected() -> None:
    partial = APM_KVN.rstrip() + b"\nQ1_DOT = 0.001\n"
    with pytest.raises(MalformedSourceError, match="rate is incomplete"):
        read(partial, format="ccsds-apm")


def test_an_unsupported_attitude_block_is_rejected() -> None:
    with_euler = APM_KVN.rstrip() + b"\nEULER_FRAME_A = EME2000\n"
    with pytest.raises(MalformedSourceError, match="unsupported APM data keyword"):
        read(with_euler, format="ccsds-apm")


# --- writer tiers ----------------------------------------------------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    messy = APM_KVN.replace(b"OBJECT_NAME = OF-SAT", b"OBJECT_NAME   =   OF-SAT")
    att = read(messy, retain_source=True)
    assert isinstance(att.source_native, ApmFile)
    assert write_apm(att, ".apm") == messy


def test_golden_kvn_round_trip_is_byte_stable() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_apm(read(golden), ".apm") == golden


def test_default_round_trip_reformats_but_preserves_content() -> None:
    messy = APM_KVN.replace(b"Q1 = 0.195286", b"Q1   =   0.1952860")
    att = read(messy)
    out = write_apm(att, ".apm")
    assert out != messy
    assert read(out) == att


def test_synthesised_write_warns_for_missing_required_fields() -> None:
    bare = Attitude(
        metadata=Metadata(object_name="SAT"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0]]),
    )
    with pytest.warns(Warning) as caught:
        out = write_apm(bare, ".apm")
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert {"OBJECT_ID", "TIME_SYSTEM", "Q_FRAME_A", "Q_FRAME_B"} <= warned
    assert b"Q_FRAME_A = UNKNOWN" in out


def test_a_multi_row_attitude_cannot_be_written_as_apm() -> None:
    att = Attitude(
        metadata=Metadata(object_name="SAT", object_id="X", time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00", "2024-01-01T00:01:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]]),
        frame_a="EME2000",
        frame_b="SC_BODY",
    )
    with pytest.raises(UnsupportedConversionError):
        write_apm(att, ".apm")


def test_a_non_quaternion_attitude_cannot_be_written_as_apm() -> None:
    att = Attitude(
        metadata=Metadata(object_name="SAT", object_id="X", time_scale="UTC"),
        attitude_type="EULER_ANGLE",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[35.0, -15.0, 18.0]]),
        frame_a="EME2000",
        frame_b="SC_BODY",
        euler_rot_seq="321",
    )
    with pytest.raises(UnsupportedConversionError):
        write_apm(att, ".apm")


def test_same_format_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    att = read(GOLDEN_KVN.read_bytes())
    assert_no_silent_loss(lambda: write_apm(att, ".apm"), loses=False)
