"""The CCSDS OEM writer: byte-lossless (opt-in), content-lossless, and synthesised paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Ephemeris,
    Metadata,
    StateVector,
    UnsupportedConversionError,
    read,
    write,
)
from orbit_formats.readers.ccsds import OemFile
from orbit_formats.registry import get_writer
from orbit_formats.writers.oem import write_oem

GOLDEN = Path(__file__).parent / "data" / "oem" / "golden_roundtrip.oem"

# A deliberately messy-formatted OEM: CRLF endings, padded "=", multi-space columns, and
# trailing zeros on values and epochs. Re-emitting it byte-for-byte is only possible from
# the retained source; the structural serialiser canonicalises the formatting.
MESSY_OEM = (
    b"CCSDS_OEM_VERS = 2.0\r\n"
    b"CREATION_DATE = 2002-11-04T17:22:31\r\n"
    b"ORIGINATOR = NASA/JPL\r\n"
    b"\r\n"
    b"META_START\r\n"
    b"OBJECT_NAME   =   MARS GLOBAL SURVEYOR\r\n"
    b"OBJECT_ID = 1996-062A\r\n"
    b"CENTER_NAME = MARS BARYCENTER\r\n"
    b"REF_FRAME = EME2000\r\n"
    b"TIME_SYSTEM = UTC\r\n"
    b"START_TIME = 1996-12-18T12:00:00.331\r\n"
    b"STOP_TIME = 1996-12-18T12:01:00.331\r\n"
    b"META_STOP\r\n"
    b"1996-12-18T12:00:00.331    2789.6190  -280.0450  -1746.7550"
    b"   4.7337200  -2.4958600  -1.0419500\r\n"
    b"1996-12-18T12:01:00.331 2783.419 -308.143 -1877.071 5.18604 -2.42124 -1.99608\r\n"
)


def _full_ephemeris() -> Ephemeris:
    """A synthesised ephemeris carrying every OEM-required field (no source_native)."""
    return Ephemeris(
        metadata=Metadata(
            object_name="SAT",
            object_id="2024-001A",
            central_body="EARTH",
            reference_frame="EME2000",
            time_scale="UTC",
        ),
        epochs=np.array(["2024-01-01T00:00:00", "2024-01-01T00:01:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0], [6999.0, 60.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0], [-0.1, 7.5, 0.0]]),
    )


def test_writer_is_registered_for_ccsds_oem() -> None:
    assert get_writer("ccsds-oem") is write_oem


# --- byte-lossless (opt-in) and content-lossless (default) -----------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    eph = read(MESSY_OEM, retain_source=True)
    assert isinstance(eph, Ephemeris)
    assert isinstance(eph.source_native, OemFile)
    assert eph.source_native.raw_bytes == MESSY_OEM
    assert write_oem(eph) == MESSY_OEM


def test_default_read_retains_no_bytes() -> None:
    eph = read(MESSY_OEM)
    assert isinstance(eph.source_native, OemFile)
    assert eph.source_native.raw_bytes is None


def test_default_round_trip_reformats_but_preserves_content() -> None:
    eph = read(MESSY_OEM)
    out = write_oem(eph)
    # The structural serialiser canonicalises formatting, so the bytes change ...
    assert out != MESSY_OEM
    # ... but no orbital content does: the re-read canonical object is equal.
    assert read(out) == eph


def test_golden_round_trip_is_byte_identical() -> None:
    golden = GOLDEN.read_bytes()
    eph = read(golden)
    assert isinstance(eph, Ephemeris)
    assert write_oem(eph) == golden


def test_structural_write_preserves_acceleration_and_covariance() -> None:
    eph = read(GOLDEN.read_bytes())
    reread = read(write_oem(eph))
    before, after = eph.source_native, reread.source_native
    assert isinstance(before, OemFile)
    assert isinstance(after, OemFile)
    assert len(after.segments) == len(before.segments) == 2
    # Acceleration columns on the first segment survive the round trip.
    acc_before = before.segments[0].accelerations
    acc_after = after.segments[0].accelerations
    assert acc_before is not None and acc_after is not None
    np.testing.assert_array_equal(acc_after, acc_before)
    # The covariance block on the second segment survives intact.
    cov_before = before.segments[1].covariances
    cov_after = after.segments[1].covariances
    assert len(cov_after) == len(cov_before) == 1
    assert cov_after[0].matrix == cov_before[0].matrix
    assert cov_after[0].cov_ref_frame == cov_before[0].cov_ref_frame


# --- synthesised / cross-format --------------------------------------------------------


def test_synthesised_write_is_valid_and_round_trips_when_complete() -> None:
    eph = _full_ephemeris()
    reread = read(write_oem(eph))
    assert isinstance(reread, Ephemeris)
    assert reread.metadata.object_name == "SAT"
    assert reread.metadata.reference_frame == "EME2000"
    assert reread.metadata.time_scale == "UTC"
    np.testing.assert_allclose(reread.positions, eph.positions)
    np.testing.assert_allclose(reread.velocities, eph.velocities)


def test_synthesised_write_warns_for_each_missing_required_field() -> None:
    eph = Ephemeris(
        metadata=Metadata(object_name="SAT", central_body="EARTH", reference_frame="EME2000"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.warns(Warning) as caught:
        out = write_oem(eph)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    # object_id and time_scale are absent from the metadata; START/STOP come from epochs.
    assert warned == {"OBJECT_ID", "TIME_SYSTEM"}
    # The output is still structurally valid OEM (placeholders fill the missing fields).
    assert b"OBJECT_ID = UNKNOWN" in out
    assert b"TIME_SYSTEM = UNKNOWN" in out


def test_synthesised_write_of_an_empty_ephemeris_warns_for_the_epoch_bounds() -> None:
    # With no states, START_TIME / STOP_TIME cannot be derived from the epochs.
    eph = Ephemeris(
        metadata=Metadata(
            object_name="SAT",
            object_id="2024-001A",
            central_body="EARTH",
            reference_frame="EME2000",
            time_scale="UTC",
        ),
        epochs=np.empty(0, dtype="datetime64[ns]"),
        positions=np.empty((0, 3)),
        velocities=np.empty((0, 3)),
    )
    with pytest.warns(Warning) as caught:
        write_oem(eph)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert warned == {"START_TIME", "STOP_TIME"}


def test_non_ephemeris_input_is_rejected() -> None:
    state = StateVector(
        metadata=Metadata(reference_frame="EME2000"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 0.0, 0.0]),
        velocity=np.array([0.0, 7.5, 0.0]),
    )
    with pytest.raises(UnsupportedConversionError, match="ccsds-oem"):
        write_oem(state)


# --- the no-silent-loss contract -------------------------------------------------------


def test_same_format_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    eph = read(GOLDEN.read_bytes())
    assert_no_silent_loss(lambda: write_oem(eph), loses=False)


def test_complete_synthesised_write_loses_nothing(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    eph = _full_ephemeris()
    assert_no_silent_loss(lambda: write_oem(eph), loses=False)


def test_synthesised_write_with_missing_fields_warns(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    eph = Ephemeris(
        metadata=Metadata(object_name="SAT", central_body="EARTH", reference_frame="EME2000"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    assert_no_silent_loss(lambda: write_oem(eph), loses=True)


# --- public write() surface ------------------------------------------------------------


def test_public_write_to_file_is_byte_identical_with_retained_source(tmp_path: Path) -> None:
    eph = read(MESSY_OEM, retain_source=True)
    destination = tmp_path / "out.oem"
    write(eph, destination)
    assert destination.read_bytes() == MESSY_OEM
