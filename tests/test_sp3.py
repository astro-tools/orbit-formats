"""The SP3 reader: parsing, the canonical adaptation, the per-satellite set, detection,
read-only enforcement, and the no-silent-loss contract.

The committed ``sample_sp3c.sp3`` (SP3-c, position+velocity) and ``sample_sp3d.sp3``
(SP3-d, position only) drive the definition-of-done read; inline byte samples cover the
malformed-input and time-system-mapping edges (the file *is* the reference — a parser is
correct when it extracts exactly the values the file states).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    Ephemeris,
    MalformedSourceError,
    UnsupportedFormatError,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.sp3 import Sp3File, read_sp3
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.source import load_source
from orbit_formats.warnings import MissingFieldWarning

DATA = Path(__file__).parent / "data" / "sp3"
SP3C = DATA / "sample_sp3c.sp3"
SP3D = DATA / "sample_sp3d.sp3"

# A minimal valid SP3-c (one satellite, one epoch, position only) the edge-case tests mutate.
# The header is deliberately short — SP3-d allows variable-length sections and the prefix-keyed
# parser does not require the fixed 22-line SP3-c header.
MINIMAL = b"""#cP2024  8 17  0  0  0.00000000       1 ORBIT IGS20 HLM  IGS
## 2326 518400.00000000   900.00000000 60539 0.0000000000000
+    1   G01  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
++         7  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
%c M  cc GPS ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc
%f  1.2500000  1.025000000  0.00000000000  0.000000000000000
/* a minimal hand-authored SP3-c
*  2024  8 17  0  0  0.00000000
PG01  -8000.000000  20000.000000  16000.000000    100.000000
EOF
"""


# --- the definition-of-done read -------------------------------------------------------


def test_sp3c_reads_into_canonical_ephemeris() -> None:
    eph = read(SP3C)
    assert isinstance(eph, Ephemeris)
    # The first listed satellite is the canonical spine; ITRF / Earth / the SP3 time system.
    assert eph.metadata.object_name == "G01"
    assert eph.metadata.reference_frame == "ITRF"
    assert eph.metadata.central_body == "Earth"
    assert eph.metadata.time_scale == "GPS"
    assert eph.metadata.provenance is not None
    assert eph.metadata.provenance.source_format == "sp3"
    assert len(eph) == 2
    assert eph.epochs[0] == np.datetime64("2024-08-17T00:00:00", "ns")
    assert eph.epochs[1] == np.datetime64("2024-08-17T00:15:00", "ns")
    np.testing.assert_array_equal(eph.positions[0], [-8000.0, 20000.0, 16000.0])
    # SP3 velocities are decimetres per second; the canonical Ephemeris holds km/s.
    np.testing.assert_allclose(eph.velocities[0], [3.0, -2.0, 1.0])


def test_sp3d_reads_into_canonical_ephemeris() -> None:
    with pytest.warns(MissingFieldWarning):
        eph = read(SP3D)
    assert isinstance(eph, Ephemeris)
    assert eph.metadata.object_name == "G01"
    assert eph.metadata.reference_frame == "ITRF"
    assert eph.metadata.central_body == "Earth"
    assert eph.metadata.time_scale == "UTC"
    assert len(eph) == 2
    np.testing.assert_array_equal(eph.positions[0], [-8000.0, 20000.0, 16000.0])
    # A position-only file fills velocity with NaN, never a fabricated value.
    assert np.isnan(eph.velocities).all()


# --- the per-satellite ephemeris set ---------------------------------------------------


def test_multi_satellite_maps_to_a_per_satellite_set() -> None:
    sp3 = read(SP3C).source_native
    assert isinstance(sp3, Sp3File)
    ephemerides = sp3.ephemerides()
    assert list(ephemerides) == ["G01", "G02"]
    g02 = ephemerides["G02"]
    assert isinstance(g02, Ephemeris)
    assert g02.metadata.object_name == "G02"
    assert g02.metadata.reference_frame == "ITRF"
    assert g02.metadata.time_scale == "GPS"
    np.testing.assert_array_equal(g02.positions[0], [15000.0, -12000.0, 18000.0])
    np.testing.assert_allclose(g02.velocities[0], [-2.5, 2.8, -1.5])
    # Every per-satellite ephemeris carries the whole file as its source_native handle.
    assert g02.source_native is sp3


def test_ephemerides_does_not_re_emit_the_missing_velocity_warning(
    recwarn: pytest.WarningsRecorder,
) -> None:
    native = read_sp3(load_source(SP3D)).source_native  # read_sp3 raised the one warning
    assert isinstance(native, Sp3File)
    recwarn.clear()
    ephemerides = native.ephemerides()
    assert all(np.isnan(e.velocities).all() for e in ephemerides.values())
    assert len(recwarn) == 0


# --- fidelity preservation -------------------------------------------------------------


def test_source_native_preserves_clock_accuracy_and_header() -> None:
    sp3 = read(SP3C).source_native
    assert isinstance(sp3, Sp3File)
    assert sp3.version == "c"
    assert sp3.mode == "V"
    assert sp3.sat_ids == ("G01", "G02")
    # Per-satellite accuracy codes (the ++ block) and clock offsets are preserved.
    assert sp3.accuracy_codes == (7, 6)
    np.testing.assert_array_equal(sp3.clocks["G01"], [100.0, 101.0])
    np.testing.assert_array_equal(sp3.clocks["G02"], [-200.0, -201.0])
    assert sp3.clock_rates is not None
    np.testing.assert_array_equal(sp3.clock_rates["G01"], [10.0, 11.0])
    # The specific frame realisation, agency, and time system ride on the model.
    assert sp3.coordinate_system == "IGS20"
    assert sp3.agency == "IGS"
    assert sp3.orbit_type == "HLM"
    assert sp3.time_system == "GPS"
    assert sp3.gps_week == 2326
    assert sp3.epoch_interval == 900.0
    assert sp3.mjd == 60539
    assert sp3.comments[0] == "SP3-c sample for orbit-formats tests, not a real IGS product"


def test_retain_source_keeps_the_verbatim_bytes() -> None:
    sp3 = read(SP3C, retain_source=True).source_native
    assert isinstance(sp3, Sp3File)
    assert sp3.raw_bytes == SP3C.read_bytes()
    # The default read holds no extra copy.
    default = read(SP3C).source_native
    assert isinstance(default, Sp3File)
    assert default.raw_bytes is None


# --- detection and registration --------------------------------------------------------


def test_detection_and_format_override() -> None:
    assert detect_format(SP3C) == "sp3"
    assert detect_format(SP3D) == "sp3"
    # An explicit format= forces the SP3 reader.
    eph = read(SP3C, format="sp3")
    assert isinstance(eph, Ephemeris)


def test_sp3_registers_a_reader_but_no_writer() -> None:
    assert get_reader("sp3") is not None
    assert get_writer("sp3") is None


def test_writing_sp3_is_rejected_as_read_only(tmp_path: Path) -> None:
    eph = read(SP3C)
    with pytest.raises(UnsupportedFormatError, match="read-only"):
        write(eph, tmp_path / "out.sp3")


# --- the no-silent-loss contract -------------------------------------------------------


def test_no_silent_loss(assert_no_silent_loss: Callable[..., None]) -> None:
    # Position+velocity loses nothing; position-only warns and names the missing velocity.
    assert_no_silent_loss(lambda: read(SP3C), loses=False)
    assert_no_silent_loss(lambda: read(SP3D), loses=True)


# --- time-system mapping ---------------------------------------------------------------


def test_unmapped_time_system_leaves_scale_unset() -> None:
    # A GNSS system time the canonical spine does not carry (Galileo) stays unset, its raw
    # value preserved on the model — the same rule the GMAT report's A1 scale follows.
    source = MINIMAL.replace(b"cc GPS ccc", b"cc GAL ccc")
    with pytest.warns(MissingFieldWarning):  # MINIMAL is position-only
        eph = read(source, format="sp3")
    assert eph.metadata.time_scale is None
    native = eph.source_native
    assert isinstance(native, Sp3File)
    assert native.time_system == "GAL"


# --- malformed input -------------------------------------------------------------------


def test_unsupported_version_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="unsupported SP3 version"):
        read(MINIMAL.replace(b"#cP", b"#aP"), format="sp3")


def test_missing_satellite_list_is_rejected() -> None:
    source = MINIMAL.replace(b"+    1   G01", b"+    0     0")
    with pytest.raises(MalformedSourceError, match="lists no satellites"):
        read(source, format="sp3")


def test_no_epochs_is_rejected() -> None:
    source = MINIMAL.replace(b"*  2024  8 17  0  0  0.00000000\n", b"")
    with pytest.raises(MalformedSourceError, match="no epochs"):
        read(source, format="sp3")


def test_record_with_too_few_columns_is_rejected() -> None:
    source = MINIMAL.replace(
        b"PG01  -8000.000000  20000.000000  16000.000000    100.000000",
        b"PG01  -8000.000000  20000.000000  16000.000000",
    )
    with pytest.raises(MalformedSourceError, match="value column"):
        read(source, format="sp3")


def test_non_numeric_value_is_rejected() -> None:
    source = MINIMAL.replace(b"PG01  -8000.000000", b"PG01  notanumber")
    with pytest.raises(MalformedSourceError, match="non-numeric"):
        read(source, format="sp3")


def test_record_count_disagreeing_with_epochs_is_rejected() -> None:
    # A second epoch with no records for G01: its one position record cannot fill two epochs.
    source = MINIMAL.replace(b"EOF\n", b"*  2024  8 17  0 15  0.00000000\nEOF\n")
    with pytest.raises(MalformedSourceError, match=r"record.*epoch"):
        read(source, format="sp3")


def test_bad_epoch_line_is_rejected() -> None:
    source = MINIMAL.replace(b"*  2024  8 17  0  0  0.00000000", b"*  2024  8 17  0  0")
    with pytest.raises(MalformedSourceError, match="epoch"):
        read(source, format="sp3")


def test_content_after_eof_is_rejected() -> None:
    source = MINIMAL.replace(b"EOF\n", b"EOF\ntrailing junk\n")
    with pytest.raises(MalformedSourceError, match="after the SP3 'EOF'"):
        read(source, format="sp3")
