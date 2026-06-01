"""The CCSDS TDM KVN reader and writer, and the canonical :class:`Tracking` projection."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    MalformedSourceError,
    Metadata,
    Tracking,
    TrackingObservation,
    UnsupportedConversionError,
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.ccsds_tdm import TdmFile
from orbit_formats.writers.tdm import write_tdm

DATA = Path(__file__).parent / "data" / "tdm"
GOLDEN_KVN = DATA / "golden_tdm.tdm"


# --- reader ----------------------------------------------------------------------------


def test_read_kvn_returns_a_tracking_set_flattened_across_segments() -> None:
    tracking = read(GOLDEN_KVN.read_bytes())
    assert isinstance(tracking, Tracking)
    assert tracking.participants == ("DSS-25", "1999-099A")
    # Two segments — the range/Doppler pass and the angle pass — flattened into one sequence.
    assert len(tracking) == 11
    first = tracking.observations[0]
    assert first.observation_type == "TRANSMIT_FREQ_1"
    assert first.epoch == np.datetime64("2005-06-08T17:41:00", "ns")
    assert first.value == pytest.approx(7.18e9)
    assert tracking.observations[-1].observation_type == "ANGLE_2"


def test_read_kvn_tags_the_spine_and_records_the_notation() -> None:
    tracking = read(GOLDEN_KVN.read_bytes())
    assert tracking.metadata.originator == "NASA/JPL"
    assert tracking.metadata.time_scale == "UTC"
    native = tracking.source_native
    assert isinstance(native, TdmFile)
    assert native.serialization == "kvn"
    assert native.message_id == "TDM-GOLDEN-0001"


def test_read_kvn_keeps_per_segment_metadata_typed_on_the_fidelity_model() -> None:
    native = read(GOLDEN_KVN.read_bytes()).source_native
    assert isinstance(native, TdmFile)
    assert len(native.segments) == 2
    meta0 = native.segments[0].meta
    assert meta0.get("MODE") == "SEQUENTIAL"
    assert meta0.get("RANGE_UNITS") == "RU"
    assert meta0.get("TURNAROUND_NUMERATOR") == 240  # int-typed
    assert meta0.get("INTEGRATION_INTERVAL") == pytest.approx(1.0)  # float-typed
    # The second segment carries the angle metadata, not range metadata.
    meta1 = native.segments[1].meta
    assert meta1.get("ANGLE_TYPE") == "AZEL"
    assert meta1.get("RANGE_UNITS") is None


# --- writer round-trips ----------------------------------------------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    golden = GOLDEN_KVN.read_bytes()
    tracking = read(golden, retain_source=True)
    assert write_tdm(tracking, ".tdm") == golden


def test_default_round_trip_is_byte_stable_against_the_golden() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_tdm(read(golden), ".tdm") == golden


def test_public_write_round_trips_through_a_path(tmp_path: Path) -> None:
    tracking = read(GOLDEN_KVN.read_bytes())
    destination = tmp_path / "out.tdm"
    write(tracking, destination)
    assert read(destination) == tracking


def test_writing_a_non_tracking_is_unsupported() -> None:
    from orbit_formats import StateVector

    state = StateVector(
        metadata=Metadata(time_scale="UTC"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.zeros(3),
        velocity=np.zeros(3),
    )
    with pytest.raises(UnsupportedConversionError):
        write_tdm(state, ".tdm")


# --- detection and conversion ----------------------------------------------------------


def test_detect_and_convert_passthrough() -> None:
    assert detect_format(GOLDEN_KVN.read_bytes()) == "ccsds-tdm"
    tracking = read(GOLDEN_KVN.read_bytes())
    # A tracking set is already in the TDM's preferred form — convert returns it unchanged.
    assert convert(tracking, "ccsds-tdm") is tracking


# --- synthesised TDM from a bare canonical tracking set --------------------------------


def _bare_tracking() -> Tracking:
    return Tracking(
        metadata=Metadata(),
        participants=(),
        observations=(
            TrackingObservation("RANGE", np.datetime64("2024-01-01T00:00:00", "ns"), 1.0),
        ),
    )


def test_synthesised_tdm_warns_for_each_unsupplied_required_field(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    tracking = _bare_tracking()
    assert_no_silent_loss(lambda: write_tdm(tracking, ".tdm"), loses=True)
    out = write_tdm(tracking, ".tdm")
    assert b"UNKNOWN" in out  # the placeholder for TIME_SYSTEM / PARTICIPANT_1
    assert isinstance(read(out), Tracking)


def test_a_supplied_tracking_set_synthesises_without_warning(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    tracking = Tracking(
        metadata=Metadata(time_scale="UTC"),
        participants=("DSS-25",),
        observations=(
            TrackingObservation("RANGE", np.datetime64("2024-01-01T00:00:00", "ns"), 1.0),
        ),
    )
    assert_no_silent_loss(lambda: write_tdm(tracking, ".tdm"), loses=False)


def test_golden_round_trip_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    tracking = read(GOLDEN_KVN.read_bytes())
    assert_no_silent_loss(lambda: write_tdm(tracking, ".tdm"), loses=False)


# --- malformed input -------------------------------------------------------------------


def _minimal(meta: str = "TIME_SYSTEM = UTC\nPARTICIPANT_1 = DSS-25", data: str = "") -> bytes:
    body = f"META_START\n{meta}\nMETA_STOP\n\nDATA_START\n{data}DATA_STOP\n"
    return f"CCSDS_TDM_VERS = 2.0\n\n{body}".encode()


def test_missing_version_is_rejected() -> None:
    without_version = _minimal().replace(b"CCSDS_TDM_VERS = 2.0\n", b"")
    with pytest.raises(MalformedSourceError, match="CCSDS_TDM_VERS"):
        read(without_version, format="ccsds-tdm")


def test_missing_a_required_meta_keyword_is_rejected() -> None:
    no_participant = _minimal(meta="TIME_SYSTEM = UTC")
    with pytest.raises(MalformedSourceError, match=r"missing required keyword.*PARTICIPANT_1"):
        read(no_participant, format="ccsds-tdm")


def test_an_unexpected_meta_keyword_is_rejected() -> None:
    bogus = _minimal(meta="TIME_SYSTEM = UTC\nPARTICIPANT_1 = DSS-25\nNONSENSE = 5")
    with pytest.raises(MalformedSourceError, match="unexpected TDM META keyword"):
        read(bogus, format="ccsds-tdm")


def test_an_unknown_observation_keyword_is_rejected() -> None:
    bogus = _minimal(data="BOGUS = 2005-159T00:00:00 1.0\n")
    with pytest.raises(MalformedSourceError, match="unknown TDM observation keyword"):
        read(bogus, format="ccsds-tdm")


def test_a_malformed_observation_line_is_rejected() -> None:
    extra = _minimal(data="RANGE = 2005-159T00:00:00 1.0 2.0\n")
    with pytest.raises(MalformedSourceError, match="must be an epoch plus one value"):
        read(extra, format="ccsds-tdm")


def test_an_unclosed_data_block_is_rejected() -> None:
    unclosed = b"CCSDS_TDM_VERS = 2.0\n\nMETA_START\nTIME_SYSTEM = UTC\nPARTICIPANT_1 = X\n"
    unclosed += b"META_STOP\n\nDATA_START\nRANGE = 2005-159T00:00:00 1.0\n"
    with pytest.raises(MalformedSourceError, match="not closed with DATA_STOP"):
        read(unclosed, format="ccsds-tdm")
