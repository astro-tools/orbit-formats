"""The SP3 writer: byte-lossless (opt-in), content-lossless, and synthesised SP3-d paths,
the field-width-truncation and missing-field warnings, and the no-silent-loss contract.

The committed ``golden_roundtrip.sp3`` (SP3-d, position+velocity, two satellites) drives the
byte-identical structural round trip; inline byte samples cover the messy-reformat and
synthesised edges (a serialiser is correct when re-reading its output reproduces the content).
"""

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
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.sp3 import Sp3File
from orbit_formats.registry import get_writer
from orbit_formats.warnings import PrecisionLossWarning
from orbit_formats.writers.sp3 import write_sp3

DATA = Path(__file__).parent / "data" / "sp3"
SP3C = DATA / "sample_sp3c.sp3"
GOLDEN = DATA / "golden_roundtrip.sp3"

# A deliberately messy-formatted SP3-c (one satellite, position+velocity): CRLF endings, a
# short variable-length header, and single-space multi-width record columns. Re-emitting it
# byte-for-byte is only possible from the retained source; the structural serialiser
# canonicalises the fixed-column layout.
MESSY_SP3 = (
    b"#cV2024  8 17  0  0  0.00000000       2 ORBIT IGS20 HLM  IGS\r\n"
    b"## 2326 518400.00000000   900.00000000 60539 0.0000000000000\r\n"
    b"+    1   G01\r\n"
    b"++         5\r\n"
    b"%c M  cc GPS ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc\r\n"
    b"%f  1.2500000  1.025000000  0.00000000000  0.000000000000000\r\n"
    b"/* messy but valid\r\n"
    b"*  2024  8 17  0  0  0.00000000\r\n"
    b"PG01 -8000.0 20000.0 16000.0 100.0\r\n"
    b"VG01 30000.0 -20000.0 10000.0 10.0\r\n"
    b"*  2024  8 17  0 15  0.00000000\r\n"
    b"PG01 -8100.0 19900.0 16100.0 101.0\r\n"
    b"VG01 30100.0 -20100.0 10100.0 11.0\r\n"
    b"EOF\r\n"
)


def _full_ephemeris() -> Ephemeris:
    """A synthesised ephemeris with a valid SP3 satellite id and every header field."""
    return Ephemeris(
        metadata=Metadata(
            object_name="G05",
            central_body="Earth",
            reference_frame="ITRF",
            time_scale="GPS",
        ),
        epochs=np.array(["2024-01-01T00:00:00", "2024-01-01T00:15:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0], [6999.0, 60.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0], [-0.1, 7.5, 0.0]]),
    )


def test_writer_is_registered_for_sp3() -> None:
    assert get_writer("sp3") is write_sp3


# --- byte-lossless (opt-in) and content-lossless (default) -----------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    eph = read(SP3C, retain_source=True)
    assert isinstance(eph, Ephemeris)
    assert isinstance(eph.source_native, Sp3File)
    assert eph.source_native.raw_bytes == SP3C.read_bytes()
    assert write_sp3(eph) == SP3C.read_bytes()


def test_default_read_retains_no_bytes_so_the_structural_path_runs() -> None:
    eph = read(SP3C)
    assert isinstance(eph.source_native, Sp3File)
    assert eph.source_native.raw_bytes is None


def test_default_round_trip_reformats_but_preserves_content() -> None:
    eph = read(MESSY_SP3)
    out = write_sp3(eph)
    # The structural serialiser canonicalises the fixed-column layout, so the bytes change ...
    assert out != MESSY_SP3
    # ... but no orbital content does: the re-read canonical object is equal.
    assert read(out) == eph


def test_golden_round_trip_is_byte_identical() -> None:
    golden = GOLDEN.read_bytes()
    eph = read(golden)
    assert isinstance(eph, Ephemeris)
    assert write_sp3(eph) == golden


def test_content_lossless_preserves_every_satellite_and_the_clock_series() -> None:
    before = read(GOLDEN.read_bytes())
    after = read(write_sp3(before))
    native_before, native_after = before.source_native, after.source_native
    assert isinstance(native_before, Sp3File)
    assert isinstance(native_after, Sp3File)
    # Both satellites, their accuracy codes, and the clock series survive — not just the
    # first satellite the canonical spine exposes.
    assert native_after.sat_ids == native_before.sat_ids == ("G01", "G02")
    assert native_after.accuracy_codes == native_before.accuracy_codes == (7, 6)
    np.testing.assert_array_equal(native_after.clocks["G02"], native_before.clocks["G02"])
    assert native_after.clock_rates is not None and native_before.clock_rates is not None
    np.testing.assert_array_equal(native_after.clock_rates["G01"], native_before.clock_rates["G01"])


# --- synthesised / cross-format --------------------------------------------------------


def test_synthesised_write_is_valid_sp3d_and_round_trips_when_complete() -> None:
    eph = _full_ephemeris()
    with pytest.warns(Warning):  # the unsupplied clock — see the no-silent-loss tests below
        out = write_sp3(eph)
    # A synthesised file is SP3-d and re-detects/re-reads as SP3.
    assert out.startswith(b"#dV")
    assert detect_format(out) == "sp3"
    reread = read(out)
    assert isinstance(reread, Ephemeris)
    assert reread.source_native is not None
    assert reread.metadata.object_name == "G05"
    assert reread.metadata.reference_frame == "ITRF"
    assert reread.metadata.time_scale == "GPS"
    np.testing.assert_allclose(reread.positions, eph.positions)
    # SP3 velocities round-trip through decimetres·s⁻¹ back to km·s⁻¹.
    np.testing.assert_allclose(reread.velocities, eph.velocities)
    np.testing.assert_array_equal(reread.epochs, eph.epochs)


def test_synthesised_write_warns_for_the_unsupplied_clock() -> None:
    with pytest.warns(Warning) as caught:
        write_sp3(_full_ephemeris())
    dropped = {field for record in caught for field in getattr(record.message, "fields", ())}
    # A complete ephemeris carries the frame/time/id; only the clock has no canonical slot.
    assert dropped == {"clock"}


def test_synthesised_write_uses_a_valid_object_name_as_the_satellite_id() -> None:
    with pytest.warns(Warning):  # the unsupplied clock
        out = write_sp3(_full_ephemeris())
    assert b"PG05" in out  # object_name "G05" is already a system+PRN id


def test_synthesised_write_placeholders_a_non_sp3_object_name() -> None:
    eph = Ephemeris(
        metadata=Metadata(
            object_name="MARS GLOBAL SURVEYOR",
            reference_frame="ITRF",
            time_scale="UTC",
        ),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.warns(Warning) as caught:
        out = write_sp3(eph)
    dropped = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "satellite id" in dropped
    assert b"PL00" in out  # the placeholder id


def test_synthesised_write_warns_for_a_missing_frame_and_time_system() -> None:
    eph = Ephemeris(
        metadata=Metadata(object_name="G01"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.warns(Warning) as caught:
        write_sp3(eph)
    dropped = {field for record in caught for field in getattr(record.message, "fields", ())}
    # No reference_frame and no time_scale; the clock is always unsupplied too.
    assert {"coordinate system", "time system", "clock"} <= dropped


def test_synthesised_position_only_when_velocities_are_nan() -> None:
    eph = Ephemeris(
        metadata=Metadata(object_name="G01", reference_frame="ITRF", time_scale="GPS"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.full((1, 3), np.nan),
    )
    with pytest.warns(Warning):  # the unsupplied clock
        out = write_sp3(eph)
    assert out.startswith(b"#dP")  # position-only mode
    assert b"\nVG01" not in out  # no velocity records
    # Re-reading a position-only file fills velocities with NaN and warns about them.
    with pytest.warns(Warning):
        reread = read(out)
    assert isinstance(reread, Ephemeris)
    assert np.isnan(reread.velocities).all()


def test_synthesised_write_warns_on_field_width_truncation() -> None:
    # A coordinate far outside SP3's GNSS domain overflows the fixed F14.6 column.
    eph = Ephemeris(
        metadata=Metadata(object_name="G01", reference_frame="ITRF", time_scale="GPS"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[1.0e9, 0.0, 0.0]]),
        velocities=np.full((1, 3), np.nan),
    )
    with pytest.warns(Warning) as caught:
        out = write_sp3(eph)
    assert any(isinstance(record.message, PrecisionLossWarning) for record in caught)
    assert detect_format(out) == "sp3"  # still a structurally valid SP3 file


def test_synthesised_write_of_an_empty_ephemeris_warns_for_the_start_epoch() -> None:
    eph = Ephemeris(
        metadata=Metadata(object_name="G01", reference_frame="ITRF", time_scale="GPS"),
        epochs=np.empty(0, dtype="datetime64[ns]"),
        positions=np.empty((0, 3)),
        velocities=np.empty((0, 3)),
    )
    with pytest.warns(Warning) as caught:
        out = write_sp3(eph)
    dropped = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "start epoch" in dropped
    assert out.rstrip().endswith(b"EOF")


def test_convert_to_sp3_is_a_same_form_passthrough() -> None:
    # sp3 prefers the ephemeris form, so routing an Ephemeris to it is a no-op pass-through —
    # the conversion-matrix cell. Writing is what synthesises the SP3 bytes.
    eph = read(GOLDEN.read_bytes())
    assert convert(eph, to="sp3") is eph


def test_non_ephemeris_input_is_rejected() -> None:
    state = StateVector(
        metadata=Metadata(reference_frame="ITRF"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 0.0, 0.0]),
        velocity=np.array([0.0, 7.5, 0.0]),
    )
    with pytest.raises(UnsupportedConversionError, match="sp3"):
        write_sp3(state)


# --- the no-silent-loss contract -------------------------------------------------------


def test_content_lossless_write_loses_nothing(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    eph = read(GOLDEN.read_bytes())
    assert_no_silent_loss(lambda: write_sp3(eph), loses=False)


def test_byte_lossless_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    eph = read(SP3C, retain_source=True)
    assert_no_silent_loss(lambda: write_sp3(eph), loses=False)


def test_synthesised_write_with_an_unsupplied_clock_warns(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    assert_no_silent_loss(lambda: write_sp3(_full_ephemeris()), loses=True)


# --- public write() surface ------------------------------------------------------------


def test_public_write_to_file_is_byte_identical_with_retained_source(tmp_path: Path) -> None:
    eph = read(SP3C, retain_source=True)
    destination = tmp_path / "out.sp3"
    write(eph, destination)
    assert destination.read_bytes() == SP3C.read_bytes()


def test_public_write_synthesises_a_readable_sp3(tmp_path: Path) -> None:
    destination = tmp_path / "out.sp3"
    with pytest.warns(Warning):  # the unsupplied clock
        write(_full_ephemeris(), destination)
    assert read(destination).metadata.object_name == "G05"
