"""The in-house CCSDS OMM (KVN) reader and writer: OMM <-> canonical MeanElementSet.

A flat KVN sequence of ``KEYWORD = value`` lines parses into the faithful :class:`OmmFile`
fidelity model and adapts to a canonical :class:`MeanElementSet`; the writer re-emits it with
byte-identical (opt-in), content-lossless, and synthesised tiers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    MalformedSourceError,
    MeanElementSet,
    Metadata,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.ccsds_omm import OmmFile, read_omm
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.omm import write_omm

GOLDEN_KVN = Path(__file__).parent / "data" / "omm" / "golden_omm.omm"

# A single-block OMM (header, metadata, mean elements, TLE parameters) — the common shape.
OMM_KVN = b"""CCSDS_OMM_VERS = 2.0
COMMENT GENERATED FROM SPACE-TRACK
CREATION_DATE = 2020-065T16:00:00
ORIGINATOR = 18 SPCS
OBJECT_NAME = STARLETTE
OBJECT_ID = 1975-010A
CENTER_NAME = EARTH
REF_FRAME = TEME
TIME_SYSTEM = UTC
MEAN_ELEMENT_THEORY = SGP4
COMMENT mean elements follow
EPOCH = 2020-064T10:34:41.4264
MEAN_MOTION = 13.84653757
ECCENTRICITY = 0.0205751
INCLINATION = 49.8237
RA_OF_ASC_NODE = 99.5917
ARG_OF_PERICENTER = 224.3636
MEAN_ANOMALY = 133.6754
EPHEMERIS_TYPE = 0
CLASSIFICATION_TYPE = U
NORAD_CAT_ID = 7646
ELEMENT_SET_NO = 999
REV_AT_EPOCH = 32997
BSTAR = 0.00021071
MEAN_MOTION_DOT = -0.00000016
MEAN_MOTION_DDOT = 0.0
"""


def test_reader_and_writer_are_registered_for_ccsds_omm() -> None:
    assert get_reader("ccsds-omm") is read_omm
    assert get_writer("ccsds-omm") is write_omm


def test_omm_signature_is_detected() -> None:
    assert detect_format(OMM_KVN) == "ccsds-omm"


def test_read_returns_a_mean_element_set() -> None:
    mean_set = read(OMM_KVN)
    assert isinstance(mean_set, MeanElementSet)
    assert mean_set.mean_motion == pytest.approx(13.84653757)
    assert mean_set.eccentricity == pytest.approx(0.0205751)
    assert mean_set.inclination == pytest.approx(49.8237)
    assert mean_set.raan == pytest.approx(99.5917)
    assert mean_set.arg_periapsis == pytest.approx(224.3636)
    assert mean_set.mean_anomaly == pytest.approx(133.6754)
    assert mean_set.bstar == pytest.approx(0.00021071)
    assert mean_set.mean_motion_dot == pytest.approx(-0.00000016)
    assert mean_set.epoch == np.datetime64("2020-03-04T10:34:41.4264", "ns")


def test_read_tags_the_spine_from_the_omm() -> None:
    md = read(OMM_KVN).metadata
    assert md.object_name == "STARLETTE"
    assert md.object_id == "1975-010A"
    assert md.reference_frame == "TEME"
    assert md.central_body == "EARTH"
    assert md.time_scale == "UTC"
    assert md.provenance is not None
    assert md.provenance.source_format == "ccsds-omm"
    assert md.provenance.creation_date == "2020-065T16:00:00"


def test_source_native_retains_the_full_omm_fidelity_model() -> None:
    omm = read(OMM_KVN).source_native
    assert isinstance(omm, OmmFile)
    assert omm.ccsds_version == "2.0"
    assert omm.serialization == "kvn"
    assert omm.metadata.mean_element_theory == "SGP4"
    assert omm.comments == ("GENERATED FROM SPACE-TRACK",)
    assert omm.mean_elements.comments == ("mean elements follow",)
    assert omm.tle_parameters is not None
    assert omm.tle_parameters.norad_cat_id == 7646
    assert omm.tle_parameters.classification_type == "U"
    assert omm.tle_parameters.element_set_no == 999
    assert omm.tle_parameters.rev_at_epoch == 32997
    assert omm.tle_parameters.ephemeris_type == 0


def test_golden_preserves_spacecraft_covariance_and_user_defined() -> None:
    omm = read(GOLDEN_KVN.read_bytes()).source_native
    assert isinstance(omm, OmmFile)
    assert omm.spacecraft_parameters is not None
    assert omm.spacecraft_parameters.mass == pytest.approx(47.0)
    assert omm.spacecraft_parameters.drag_coeff == pytest.approx(2.2)
    assert omm.covariance is not None
    assert omm.covariance.cov_ref_frame == "RTN"
    assert len(omm.covariance.matrix) == 21
    assert omm.covariance.matrix[0] == pytest.approx(0.31)
    assert omm.covariance.matrix[-1] == pytest.approx(0.51)
    assert omm.user_defined == (("INTLDES", "1975-010A"),)


def test_a_keplerian_omm_without_mean_motion_derives_it_from_sma() -> None:
    keplerian = b"""CCSDS_OMM_VERS = 2.0
OBJECT_NAME = SAT
OBJECT_ID = 2000-000A
CENTER_NAME = EARTH
REF_FRAME = TEME
TIME_SYSTEM = UTC
MEAN_ELEMENT_THEORY = DSST
EPOCH = 2000-01-01T00:00:00
SEMI_MAJOR_AXIS = 6800.0
ECCENTRICITY = 0.001
INCLINATION = 51.6
RA_OF_ASC_NODE = 247.0
ARG_OF_PERICENTER = 130.0
MEAN_ANOMALY = 325.0
GM = 398600.4418
"""
    mean_set = read(keplerian)
    assert isinstance(mean_set, MeanElementSet)
    # n = sqrt(mu/a^3) in rad/s, expressed in rev/day.
    expected = np.sqrt(398600.4418 / 6800.0**3) * 86400.0 / (2.0 * np.pi)
    assert mean_set.mean_motion == pytest.approx(expected)


def test_odd_whitespace_and_bracketed_units_are_tolerated() -> None:
    messy = OMM_KVN.replace(
        b"MEAN_MOTION = 13.84653757", b"MEAN_MOTION   =   13.84653757 [rev/day]"
    )
    mean_set = read(messy)
    assert isinstance(mean_set, MeanElementSet)
    assert mean_set.mean_motion == pytest.approx(13.84653757)


# --- malformed inputs ------------------------------------------------------------------


def test_missing_version_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="CCSDS_OMM_VERS"):
        read(OMM_KVN.replace(b"CCSDS_OMM_VERS = 2.0\n", b""), format="ccsds-omm")


def test_missing_required_metadata_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="MEAN_ELEMENT_THEORY"):
        read(OMM_KVN.replace(b"MEAN_ELEMENT_THEORY = SGP4\n", b""), format="ccsds-omm")


def test_mean_elements_without_motion_or_sma_are_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="MEAN_MOTION or SEMI_MAJOR_AXIS"):
        read(OMM_KVN.replace(b"MEAN_MOTION = 13.84653757\n", b""), format="ccsds-omm")


def test_a_non_numeric_element_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="ECCENTRICITY must be a number"):
        read(
            OMM_KVN.replace(b"ECCENTRICITY = 0.0205751", b"ECCENTRICITY = oops"), format="ccsds-omm"
        )


def test_an_unknown_keyword_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="unexpected OMM keyword 'MYSTERY'"):
        read(
            OMM_KVN.replace(
                b"OBJECT_NAME = STARLETTE\n", b"MYSTERY = 1\nOBJECT_NAME = STARLETTE\n"
            ),
            format="ccsds-omm",
        )


def test_a_partial_covariance_is_rejected() -> None:
    partial = OMM_KVN + b"COV_REF_FRAME = RTN\nCX_X = 0.31\n"
    with pytest.raises(MalformedSourceError, match="covariance is incomplete"):
        read(partial, format="ccsds-omm")


# --- writer tiers ----------------------------------------------------------------------


def test_retain_source_round_trip_is_byte_identical() -> None:
    messy = OMM_KVN.replace(b"OBJECT_NAME = STARLETTE", b"OBJECT_NAME   =   STARLETTE")
    mean_set = read(messy, retain_source=True)
    assert isinstance(mean_set.source_native, OmmFile)
    assert mean_set.source_native.raw_bytes == messy
    assert write_omm(mean_set, ".omm") == messy


def test_golden_kvn_round_trip_is_byte_stable() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_omm(read(golden), ".omm") == golden


def test_default_round_trip_reformats_but_preserves_content() -> None:
    messy = OMM_KVN.replace(b"OBJECT_NAME = STARLETTE", b"OBJECT_NAME   =   STARLETTE")
    mean_set = read(messy)
    out = write_omm(mean_set, ".omm")
    assert out != messy
    assert read(out) == mean_set


# --- synthesised / public surface ------------------------------------------------------


def test_synthesised_write_warns_for_missing_required_fields() -> None:
    bare = MeanElementSet(
        metadata=Metadata(object_name="SAT"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        mean_motion=15.0,
        eccentricity=0.001,
        inclination=51.6,
        raan=247.0,
        arg_periapsis=130.0,
        mean_anomaly=325.0,
    )
    with pytest.warns(Warning) as caught:
        out = write_omm(bare, ".omm")
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert {"OBJECT_ID", "CENTER_NAME", "REF_FRAME", "TIME_SYSTEM"} <= warned
    assert b"OBJECT_ID = UNKNOWN" in out


def test_synthesised_tle_block_warns_when_mean_motion_dot_is_absent() -> None:
    # A mean set carrying BSTAR but no MEAN_MOTION_DOT still needs the OMM-mandatory
    # MEAN_MOTION_DOT in the TLE-parameters block; the writer placeholders it and warns.
    bare = MeanElementSet(
        metadata=Metadata(
            object_name="SAT",
            object_id="2000-000A",
            central_body="EARTH",
            reference_frame="TEME",
            time_scale="UTC",
        ),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        mean_motion=15.0,
        eccentricity=0.001,
        inclination=51.6,
        raan=247.0,
        arg_periapsis=130.0,
        mean_anomaly=325.0,
        bstar=0.0001,
    )
    with pytest.warns(Warning) as caught:
        out = write_omm(bare, ".omm")
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "MEAN_MOTION_DOT" in warned
    assert b"MEAN_MOTION_DOT = 0.0" in out


def test_public_write_to_file_is_byte_identical_with_retained_source(tmp_path: Path) -> None:
    mean_set = read(OMM_KVN, retain_source=True)
    destination = tmp_path / "out.omm"
    write(mean_set, destination)
    assert destination.read_bytes() == OMM_KVN


def test_same_format_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    mean_set = read(GOLDEN_KVN.read_bytes())
    assert_no_silent_loss(lambda: write_omm(mean_set, ".omm"), loses=False)
