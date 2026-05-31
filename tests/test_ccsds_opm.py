"""The in-house CCSDS OPM (KVN) reader and writer: OPM <-> canonical StateVector.

A flat KVN sequence of ``KEYWORD = value`` lines parses into the faithful :class:`OpmFile`
fidelity model and adapts to a canonical :class:`StateVector`; the writer re-emits it with
byte-identical (opt-in), content-lossless, and synthesised tiers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    MalformedSourceError,
    Metadata,
    StateVector,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.ccsds_opm import OpmFile, read_opm
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.opm import write_opm

GOLDEN_KVN = Path(__file__).parent / "data" / "opm" / "golden_opm.opm"

# A single-state OPM (header, metadata, state vector, Keplerian) — the common shape. The
# day-of-year EPOCH exercises the DOY epoch path.
OPM_KVN = b"""CCSDS_OPM_VERS = 2.0
COMMENT GEOCENTRIC, CARTESIAN, EARTH FIXED
CREATION_DATE = 2020-065T16:00:00
ORIGINATOR = 18 SPCS
OBJECT_NAME = GODZILLA 5
OBJECT_ID = 1998-057A
CENTER_NAME = EARTH
REF_FRAME = EME2000
TIME_SYSTEM = UTC
COMMENT state vector
EPOCH = 2020-064T14:28:15.1172
X = 6503.514
Y = 1239.647
Z = -717.49
X_DOT = -0.87316
Y_DOT = 8.74042
Z_DOT = -4.191076
COMMENT Keplerian elements
SEMI_MAJOR_AXIS = 6730.96
ECCENTRICITY = 0.0006703
INCLINATION = 51.6416
RA_OF_ASC_NODE = 247.4627
ARG_OF_PERICENTER = 130.536
TRUE_ANOMALY = 325.0288
GM = 398600.9368
"""


def test_reader_and_writer_are_registered_for_ccsds_opm() -> None:
    assert get_reader("ccsds-opm") is read_opm
    assert get_writer("ccsds-opm") is write_opm


def test_opm_signature_is_detected() -> None:
    assert detect_format(OPM_KVN) == "ccsds-opm"


def test_read_returns_a_state_vector() -> None:
    state = read(OPM_KVN)
    assert isinstance(state, StateVector)
    assert state.position == pytest.approx([6503.514, 1239.647, -717.49])
    assert state.velocity == pytest.approx([-0.87316, 8.74042, -4.191076])
    assert state.epoch == np.datetime64("2020-03-04T14:28:15.1172", "ns")


def test_read_populates_canonical_keplerian_from_a_true_anomaly_block() -> None:
    state = read(OPM_KVN)
    assert isinstance(state, StateVector)
    keplerian = state.keplerian
    assert keplerian is not None
    assert keplerian.semi_major_axis == pytest.approx(6730.96)
    assert keplerian.eccentricity == pytest.approx(0.0006703)
    assert keplerian.inclination == pytest.approx(51.6416)
    assert keplerian.true_anomaly == pytest.approx(325.0288)


def test_read_tags_the_spine_from_the_opm() -> None:
    md = read(OPM_KVN).metadata
    assert md.object_name == "GODZILLA 5"
    assert md.object_id == "1998-057A"
    assert md.reference_frame == "EME2000"
    assert md.central_body == "EARTH"
    assert md.time_scale == "UTC"
    assert md.provenance is not None
    assert md.provenance.source_format == "ccsds-opm"
    assert md.provenance.creation_date == "2020-065T16:00:00"


def test_source_native_retains_the_full_opm_fidelity_model() -> None:
    opm = read(OPM_KVN).source_native
    assert isinstance(opm, OpmFile)
    assert opm.ccsds_version == "2.0"
    assert opm.serialization == "kvn"
    assert opm.comments == ("GEOCENTRIC, CARTESIAN, EARTH FIXED",)
    assert opm.state_vector.comments == ("state vector",)
    assert opm.keplerian is not None
    assert opm.keplerian.gm == pytest.approx(398600.9368)


def test_golden_preserves_spacecraft_covariance_and_maneuvers() -> None:
    opm = read(GOLDEN_KVN.read_bytes()).source_native
    assert isinstance(opm, OpmFile)
    assert opm.spacecraft_parameters is not None
    assert opm.spacecraft_parameters.mass == pytest.approx(3000.0)
    assert opm.spacecraft_parameters.drag_coeff == pytest.approx(2.5)
    assert opm.covariance is not None
    assert opm.covariance.cov_ref_frame == "RTN"
    assert len(opm.covariance.matrix) == 21
    assert opm.covariance.matrix[0] == pytest.approx(0.31)
    assert opm.covariance.matrix[-1] == pytest.approx(0.51)
    assert len(opm.maneuvers) == 2
    first, second = opm.maneuvers
    assert first.comments == ("first maneuver: orbit-raising",)
    assert first.man_duration == pytest.approx(286.0)
    assert first.man_delta_mass == pytest.approx(-3.0)
    assert first.man_dv_3 == pytest.approx(-0.001)
    assert first.man_ref_frame == "EME2000"
    assert second.man_ref_frame == "RTN"
    assert second.man_dv_1 == pytest.approx(0.001)
    assert opm.user_defined == (("INTLDES", "1998-057A"),)


def test_a_mean_anomaly_keplerian_block_leaves_canonical_keplerian_unset() -> None:
    # The canonical KeplerianElements carries a true-anomaly representation, so a Keplerian
    # block stated with MEAN_ANOMALY leaves the canonical view unset — but the full block is
    # preserved on the fidelity model.
    mean = OPM_KVN.replace(b"TRUE_ANOMALY = 325.0288", b"MEAN_ANOMALY = 324.8331")
    state = read(mean)
    assert isinstance(state, StateVector)
    assert state.keplerian is None
    opm = state.source_native
    assert isinstance(opm, OpmFile)
    assert opm.keplerian is not None
    assert opm.keplerian.mean_anomaly == pytest.approx(324.8331)
    assert opm.keplerian.true_anomaly is None


def test_odd_whitespace_and_bracketed_units_are_tolerated() -> None:
    messy = OPM_KVN.replace(b"X_DOT = -0.87316", b"X_DOT   =   -0.87316 [km/s]")
    state = read(messy)
    assert isinstance(state, StateVector)
    assert state.velocity[0] == pytest.approx(-0.87316)


def test_a_message_id_round_trips() -> None:
    with_id = OPM_KVN.replace(
        b"ORIGINATOR = 18 SPCS\n", b"ORIGINATOR = 18 SPCS\nMESSAGE_ID = OPM-42\n"
    )
    opm = read(with_id).source_native
    assert isinstance(opm, OpmFile)
    assert opm.message_id == "OPM-42"
    assert b"MESSAGE_ID = OPM-42" in write_opm(read(with_id), ".opm")


# --- malformed inputs ------------------------------------------------------------------


def test_missing_version_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="CCSDS_OPM_VERS"):
        read(OPM_KVN.replace(b"CCSDS_OPM_VERS = 2.0\n", b""), format="ccsds-opm")


def test_missing_required_metadata_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="REF_FRAME"):
        read(OPM_KVN.replace(b"REF_FRAME = EME2000\n", b""), format="ccsds-opm")


def test_missing_state_vector_field_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="X_DOT"):
        read(OPM_KVN.replace(b"X_DOT = -0.87316\n", b""), format="ccsds-opm")


def test_a_non_numeric_state_value_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="X must be a number"):
        read(OPM_KVN.replace(b"X = 6503.514", b"X = oops"), format="ccsds-opm")


def test_a_keplerian_block_without_an_anomaly_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="TRUE_ANOMALY or MEAN_ANOMALY"):
        read(OPM_KVN.replace(b"TRUE_ANOMALY = 325.0288\n", b""), format="ccsds-opm")


def test_an_unknown_keyword_is_rejected() -> None:
    with_mystery = OPM_KVN.replace(
        b"OBJECT_NAME = GODZILLA 5\n", b"MYSTERY = 1\nOBJECT_NAME = GODZILLA 5\n"
    )
    with pytest.raises(MalformedSourceError, match="unexpected OPM keyword 'MYSTERY'"):
        read(with_mystery, format="ccsds-opm")


def test_a_partial_covariance_is_rejected() -> None:
    partial = OPM_KVN + b"COV_REF_FRAME = RTN\nCX_X = 0.31\n"
    with pytest.raises(MalformedSourceError, match="covariance is incomplete"):
        read(partial, format="ccsds-opm")


def test_a_maneuver_keyword_before_ignition_is_rejected() -> None:
    dangling = OPM_KVN + b"MAN_DURATION = 286.0\n"
    with pytest.raises(MalformedSourceError, match="before MAN_EPOCH_IGNITION"):
        read(dangling, format="ccsds-opm")


def test_an_incomplete_maneuver_is_rejected() -> None:
    incomplete = OPM_KVN + b"MAN_EPOCH_IGNITION = 2020-03-05T10:31:36.871\nMAN_DURATION = 286.0\n"
    with pytest.raises(MalformedSourceError, match="MAN_DELTA_MASS"):
        read(incomplete, format="ccsds-opm")


# --- writer tiers ----------------------------------------------------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    messy = OPM_KVN.replace(b"OBJECT_NAME = GODZILLA 5", b"OBJECT_NAME   =   GODZILLA 5")
    state = read(messy, retain_source=True)
    assert isinstance(state.source_native, OpmFile)
    assert state.source_native.raw_bytes == messy
    assert write_opm(state, ".opm") == messy


def test_golden_kvn_round_trip_is_byte_stable() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_opm(read(golden), ".opm") == golden


def test_default_round_trip_reformats_but_preserves_content() -> None:
    messy = OPM_KVN.replace(b"X = 6503.514", b"X   =   6503.5140")
    state = read(messy)
    out = write_opm(state, ".opm")
    assert out != messy
    assert read(out) == state


# --- synthesised / public surface ------------------------------------------------------


def test_synthesised_write_warns_for_missing_required_fields() -> None:
    bare = StateVector(
        metadata=Metadata(object_name="SAT"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 0.0, 0.0]),
        velocity=np.array([0.0, 7.5, 0.0]),
    )
    with pytest.warns(Warning) as caught:
        out = write_opm(bare, ".opm")
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert {"OBJECT_ID", "CENTER_NAME", "REF_FRAME", "TIME_SYSTEM"} <= warned
    assert b"OBJECT_ID = UNKNOWN" in out
    # The mandatory state vector is always written in full.
    assert b"X = 7000.0" in out


def test_public_write_to_file_is_byte_identical_with_retained_source(tmp_path: Path) -> None:
    state = read(OPM_KVN, retain_source=True)
    destination = tmp_path / "out.opm"
    write(state, destination)
    assert destination.read_bytes() == OPM_KVN


def test_non_state_vector_cannot_be_written_as_opm() -> None:
    from orbit_formats import Ephemeris, UnsupportedConversionError

    ephemeris = Ephemeris(
        metadata=Metadata(reference_frame="EME2000"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.raises(UnsupportedConversionError):
        write_opm(ephemeris, ".opm")


def test_same_format_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    state = read(GOLDEN_KVN.read_bytes())
    assert_no_silent_loss(lambda: write_opm(state, ".opm"), loses=False)
