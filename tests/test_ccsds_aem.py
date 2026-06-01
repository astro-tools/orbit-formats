"""The in-house CCSDS AEM (KVN) reader and writer: AEM <-> canonical Attitude.

A multi-segment attitude time series parses into the faithful :class:`AemFile` fidelity model
and adapts to a canonical :class:`Attitude`; the writer re-emits it with byte-identical
(opt-in), content-lossless, and synthesised tiers. AEM is the attitude analogue of OEM.
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
    detect_format,
    read,
)
from orbit_formats.readers.ccsds_aem import AemFile, read_aem
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.aem import write_aem

GOLDEN_KVN = Path(__file__).parent / "data" / "aem" / "golden_aem.aem"

# A single-segment quaternion AEM — the common shape, with the full META.
AEM_KVN = b"""CCSDS_AEM_VERS = 1.0
CREATION_DATE = 2024-03-01T12:00:00
ORIGINATOR = ORBIT-FORMATS

META_START
COMMENT quaternion attitude
OBJECT_NAME = OF-SAT
OBJECT_ID = 2024-018A
CENTER_NAME = EARTH
REF_FRAME_A = EME2000
REF_FRAME_B = SC_BODY
ATTITUDE_DIR = A2B
TIME_SYSTEM = UTC
START_TIME = 2024-03-01T00:00:00
STOP_TIME = 2024-03-01T00:01:00
ATTITUDE_TYPE = QUATERNION
QUATERNION_TYPE = LAST
META_STOP

DATA_START
2024-03-01T00:00:00 0.195286 -0.079460 0.318876 0.924049
2024-03-01T00:01:00 0.195280 -0.079476 0.318950 0.924024
DATA_STOP
"""


def test_reader_and_writer_are_registered_for_ccsds_aem() -> None:
    assert get_reader("ccsds-aem") is read_aem
    assert get_writer("ccsds-aem") is write_aem


def test_aem_signature_is_detected() -> None:
    assert detect_format(AEM_KVN) == "ccsds-aem"


def test_read_returns_an_attitude() -> None:
    att = read(AEM_KVN)
    assert isinstance(att, Attitude)
    assert att.attitude_type == "QUATERNION"
    assert len(att) == 2
    assert att.frame_a == "EME2000"
    assert att.frame_b == "SC_BODY"
    assert att.epochs[0] == np.datetime64("2024-03-01T00:00:00", "ns")
    np.testing.assert_allclose(att.records[0], [0.195286, -0.079460, 0.318876, 0.924049])


def test_read_tags_the_spine_from_the_aem() -> None:
    md = read(AEM_KVN).metadata
    assert md.object_name == "OF-SAT"
    assert md.object_id == "2024-018A"
    assert md.central_body == "EARTH"
    assert md.time_scale == "UTC"
    # The two attitude frames live on the object, not the single-slot spine.
    assert md.reference_frame is None
    assert md.provenance is not None
    assert md.provenance.source_format == "ccsds-aem"
    assert md.provenance.creation_date == "2024-03-01T12:00:00"


def test_source_native_retains_the_full_aem_fidelity_model() -> None:
    aem = read(AEM_KVN).source_native
    assert isinstance(aem, AemFile)
    assert aem.ccsds_version == "1.0"
    assert aem.serialization == "kvn"
    assert len(aem.segments) == 1
    meta = aem.segments[0].meta
    assert meta.attitude_dir == "A2B"
    assert meta.quaternion_type == "LAST"
    assert meta.comments == ("quaternion attitude",)


def test_quaternion_type_first_is_normalised_to_scalar_last() -> None:
    # QUATERNION_TYPE = FIRST writes the scalar first (QC Q1 Q2 Q3); the canonical record
    # always stores it scalar-last (Q1 Q2 Q3 QC).
    first = (
        AEM_KVN.replace(b"QUATERNION_TYPE = LAST", b"QUATERNION_TYPE = FIRST")
        .replace(
            b"2024-03-01T00:00:00 0.195286 -0.079460 0.318876 0.924049",
            b"2024-03-01T00:00:00 0.924049 0.195286 -0.079460 0.318876",
        )
        .replace(
            b"2024-03-01T00:01:00 0.195280 -0.079476 0.318950 0.924024",
            b"2024-03-01T00:01:00 0.924024 0.195280 -0.079476 0.318950",
        )
    )
    att = read(first)
    assert isinstance(att, Attitude)
    np.testing.assert_allclose(att.records[0], [0.195286, -0.079460, 0.318876, 0.924049])
    # And a FIRST round-trip restores the scalar-first column order.
    assert read(write_aem(att, ".aem")) == att


def test_multi_segment_files_concatenate_into_one_attitude() -> None:
    second_segment = b"""
META_START
OBJECT_NAME = OF-SAT
OBJECT_ID = 2024-018A
REF_FRAME_A = EME2000
REF_FRAME_B = SC_BODY
TIME_SYSTEM = UTC
START_TIME = 2024-03-01T00:02:00
STOP_TIME = 2024-03-01T00:02:00
ATTITUDE_TYPE = QUATERNION
META_STOP

DATA_START
2024-03-01T00:02:00 0.195270 -0.079500 0.319067 0.923984
DATA_STOP
"""
    att = read(AEM_KVN + second_segment)
    assert isinstance(att, Attitude)
    assert len(att) == 3
    assert att.epochs[-1] == np.datetime64("2024-03-01T00:02:00", "ns")
    aem = att.source_native
    assert isinstance(aem, AemFile)
    assert len(aem.segments) == 2


def test_euler_angle_attitude_round_trips() -> None:
    euler = (
        AEM_KVN.replace(
            b"ATTITUDE_TYPE = QUATERNION\nQUATERNION_TYPE = LAST",
            b"ATTITUDE_TYPE = EULER_ANGLE\nEULER_ROT_SEQ = 321",
        )
        .replace(
            b"2024-03-01T00:00:00 0.195286 -0.079460 0.318876 0.924049",
            b"2024-03-01T00:00:00 35.45 -15.75 18.80",
        )
        .replace(
            b"2024-03-01T00:01:00 0.195280 -0.079476 0.318950 0.924024",
            b"2024-03-01T00:01:00 35.46 -15.76 18.79",
        )
    )
    att = read(euler)
    assert isinstance(att, Attitude)
    assert att.attitude_type == "EULER_ANGLE"
    assert att.euler_rot_seq == "321"
    np.testing.assert_allclose(att.records[0], [35.45, -15.75, 18.80])
    assert read(write_aem(att, ".aem")) == att


def test_spin_attitude_round_trips() -> None:
    spin = (
        AEM_KVN.replace(
            b"ATTITUDE_TYPE = QUATERNION\nQUATERNION_TYPE = LAST", b"ATTITUDE_TYPE = SPIN"
        )
        .replace(
            b"2024-03-01T00:00:00 0.195286 -0.079460 0.318876 0.924049",
            b"2024-03-01T00:00:00 10.0 20.0 30.0 0.5",
        )
        .replace(
            b"2024-03-01T00:01:00 0.195280 -0.079476 0.318950 0.924024",
            b"2024-03-01T00:01:00 10.1 20.1 30.1 0.51",
        )
    )
    att = read(spin)
    assert isinstance(att, Attitude)
    assert att.attitude_type == "SPIN"
    np.testing.assert_allclose(att.records[0], [10.0, 20.0, 30.0, 0.5])
    assert read(write_aem(att, ".aem")) == att


# --- malformed inputs ------------------------------------------------------------------


def test_missing_version_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="CCSDS_AEM_VERS"):
        read(AEM_KVN.replace(b"CCSDS_AEM_VERS = 1.0\n", b""), format="ccsds-aem")


def test_missing_required_meta_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="REF_FRAME_B"):
        read(AEM_KVN.replace(b"REF_FRAME_B = SC_BODY\n", b""), format="ccsds-aem")


def test_an_unsupported_attitude_type_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="unsupported AEM ATTITUDE_TYPE"):
        read(
            AEM_KVN.replace(b"ATTITUDE_TYPE = QUATERNION", b"ATTITUDE_TYPE = QUATERNION/DERIVATIVE")
        )


def test_a_wrong_width_data_line_is_rejected() -> None:
    short = AEM_KVN.replace(
        b"2024-03-01T00:00:00 0.195286 -0.079460 0.318876 0.924049",
        b"2024-03-01T00:00:00 0.195286 -0.079460 0.318876",
    )
    with pytest.raises(MalformedSourceError, match="must be an epoch plus 4 value"):
        read(short, format="ccsds-aem")


def test_an_unclosed_data_block_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="DATA_STOP"):
        read(AEM_KVN.replace(b"DATA_STOP\n", b""), format="ccsds-aem")


def test_a_missing_data_block_is_rejected() -> None:
    no_data = AEM_KVN.split(b"DATA_START")[0]
    with pytest.raises(MalformedSourceError, match="expected DATA_START"):
        read(no_data, format="ccsds-aem")


def test_segments_that_disagree_on_attitude_type_are_rejected() -> None:
    mismatched = AEM_KVN + (
        b"\nMETA_START\nOBJECT_NAME = OF-SAT\nOBJECT_ID = 2024-018A\n"
        b"REF_FRAME_A = EME2000\nREF_FRAME_B = SC_BODY\nTIME_SYSTEM = UTC\n"
        b"START_TIME = 2024-03-01T00:02:00\nSTOP_TIME = 2024-03-01T00:02:00\n"
        b"ATTITUDE_TYPE = SPIN\nMETA_STOP\n\nDATA_START\n"
        b"2024-03-01T00:02:00 10.0 20.0 30.0 0.5\nDATA_STOP\n"
    )
    with pytest.raises(MalformedSourceError, match="disagree on ATTITUDE_TYPE"):
        read(mismatched, format="ccsds-aem")


# --- writer tiers ----------------------------------------------------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    messy = AEM_KVN.replace(b"OBJECT_NAME = OF-SAT", b"OBJECT_NAME   =   OF-SAT")
    att = read(messy, retain_source=True)
    assert isinstance(att.source_native, AemFile)
    assert att.source_native.raw_bytes == messy
    assert write_aem(att, ".aem") == messy


def test_golden_kvn_round_trip_is_byte_stable() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_aem(read(golden), ".aem") == golden


def test_default_round_trip_reformats_but_preserves_content() -> None:
    messy = AEM_KVN.replace(b"OBJECT_NAME = OF-SAT", b"OBJECT_NAME   =   OF-SAT")
    att = read(messy)
    out = write_aem(att, ".aem")
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
        out = write_aem(bare, ".aem")
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert {"OBJECT_ID", "REF_FRAME_A", "REF_FRAME_B", "TIME_SYSTEM"} <= warned
    assert b"OBJECT_ID = UNKNOWN" in out


def test_non_attitude_cannot_be_written_as_aem() -> None:
    from orbit_formats import Ephemeris, UnsupportedConversionError

    ephemeris = Ephemeris(
        metadata=Metadata(reference_frame="EME2000"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.raises(UnsupportedConversionError):
        write_aem(ephemeris, ".aem")


def test_same_format_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    att = read(GOLDEN_KVN.read_bytes())
    assert_no_silent_loss(lambda: write_aem(att, ".aem"), loses=False)
