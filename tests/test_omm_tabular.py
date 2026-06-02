"""OMM in the Celestrak / Space-Track JSON and CSV encodings — reader and writer.

The flat JSON / CSV OMM encodings parse into the same canonical ``MeanElementSet`` as the CCSDS
OMM, reusing its fidelity model and adapter; a file is a catalogue of one or more records. The
writer re-emits the flat operational field set, with byte-identical (opt-in), content-lossless,
and synthesised tiers, warning on any OMM field the flat columns cannot hold.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    MalformedSourceError,
    MeanElementSet,
    Metadata,
    UnsupportedConversionError,
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.readers.ccsds_omm import OmmFile
from orbit_formats.readers.omm_tabular import OmmCatalog, read_omm_csv, read_omm_json
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.omm_tabular import write_omm_csv, write_omm_json

_DATA = Path(__file__).parent / "data" / "omm"
GOLDEN_JSON = _DATA / "golden_omm.json"
GOLDEN_CSV = _DATA / "golden_omm.csv"
GOLDEN_CATALOG_CSV = _DATA / "golden_omm_catalog.csv"

# A single Celestrak-style OMM JSON record (the common shape — no header / frame / theory keys).
OMM_JSON = b"""[{
  "OBJECT_NAME": "VANGUARD 1",
  "OBJECT_ID": "1958-002B",
  "EPOCH": "2025-02-14T14:36:48.662784",
  "MEAN_MOTION": 10.85873516,
  "ECCENTRICITY": 0.1841322,
  "INCLINATION": 34.2493,
  "RA_OF_ASC_NODE": 19.2327,
  "ARG_OF_PERICENTER": 100.1057,
  "MEAN_ANOMALY": 281.1229,
  "EPHEMERIS_TYPE": 0,
  "CLASSIFICATION_TYPE": "U",
  "NORAD_CAT_ID": 5,
  "ELEMENT_SET_NO": 999,
  "REV_AT_EPOCH": 39027,
  "BSTAR": 0.00035436,
  "MEAN_MOTION_DOT": 2.64e-6,
  "MEAN_MOTION_DDOT": 0
}]"""

OMM_CSV = (
    b"OBJECT_NAME,OBJECT_ID,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION,RA_OF_ASC_NODE,"
    b"ARG_OF_PERICENTER,MEAN_ANOMALY,EPHEMERIS_TYPE,CLASSIFICATION_TYPE,NORAD_CAT_ID,"
    b"ELEMENT_SET_NO,REV_AT_EPOCH,BSTAR,MEAN_MOTION_DOT,MEAN_MOTION_DDOT\n"
    b"VANGUARD 1,1958-002B,2020-10-13T04:52:48.472320,10.84869164,.1845686,34.2443,225.5254,"
    b"162.2516,205.2356,0,U,5,999,21814,-.22483E-4,-1.6E-7,0\n"
)


# --- registration & detection ----------------------------------------------------------


def test_readers_and_writers_are_registered() -> None:
    assert get_reader("omm-json") is read_omm_json
    assert get_reader("omm-csv") is read_omm_csv
    assert get_writer("omm-json") is write_omm_json
    assert get_writer("omm-csv") is write_omm_csv


def test_detection_is_by_content_signature() -> None:
    assert detect_format(OMM_JSON) == "omm-json"
    assert detect_format(OMM_CSV) == "omm-csv"
    assert detect_format(GOLDEN_JSON.read_bytes()) == "omm-json"
    assert detect_format(GOLDEN_CSV.read_bytes()) == "omm-csv"


def test_a_single_json_object_is_detected_too() -> None:
    assert detect_format(OMM_JSON.strip().lstrip(b"[").rstrip(b"]")) == "omm-json"


def test_ambiguous_extension_is_a_fallback_when_the_signature_is_silent(tmp_path: Path) -> None:
    # An empty JSON array has no OMM keys for the signature to match; the .json extension then
    # resolves it (signature-first, extension as the fallback).
    empty = tmp_path / "catalogue.json"
    empty.write_bytes(b"[]")
    assert detect_format(empty) == "omm-json"


def test_explicit_format_overrides_detection() -> None:
    # CSV content read under an explicit omm-csv format, with no reliance on detection.
    mean_set = read(io.BytesIO(OMM_CSV), format="omm-csv")
    assert isinstance(mean_set, MeanElementSet)
    assert mean_set.metadata.object_name == "VANGUARD 1"


# --- reading ---------------------------------------------------------------------------


def test_json_reads_into_a_mean_element_set() -> None:
    mean_set = read(OMM_JSON)
    assert isinstance(mean_set, MeanElementSet)
    assert mean_set.mean_motion == pytest.approx(10.85873516)
    assert mean_set.eccentricity == pytest.approx(0.1841322)
    assert mean_set.inclination == pytest.approx(34.2493)
    assert mean_set.bstar == pytest.approx(0.00035436)
    assert mean_set.mean_motion_dot == pytest.approx(2.64e-6)
    assert mean_set.epoch == np.datetime64("2025-02-14T14:36:48.662784", "ns")


def test_csv_reads_celestrak_number_formatting() -> None:
    mean_set = read(OMM_CSV)
    assert isinstance(mean_set, MeanElementSet)
    assert mean_set.eccentricity == pytest.approx(0.1845686)  # ".1845686"
    assert mean_set.bstar == pytest.approx(-0.22483e-4)  # "-.22483E-4"
    assert mean_set.mean_motion_dot == pytest.approx(-1.6e-7)


def test_implied_metadata_defaults_to_a_teme_utc_sgp4_set() -> None:
    md = read(OMM_JSON).metadata
    assert md.reference_frame == "TEME"
    assert md.central_body == "EARTH"
    assert md.time_scale == "UTC"
    assert md.provenance is not None
    assert md.provenance.source_format == "omm-json"


def test_stated_metadata_is_honoured_over_the_default() -> None:
    framed = OMM_JSON.replace(b'"OBJECT_NAME"', b'"REF_FRAME": "GCRF",\n  "OBJECT_NAME"')
    assert read(framed).metadata.reference_frame == "GCRF"


def test_source_native_is_the_catalogue() -> None:
    catalog = read(OMM_JSON).source_native
    assert isinstance(catalog, OmmCatalog)
    assert catalog.serialization == "json"
    assert len(catalog.records) == 1
    assert isinstance(catalog.records[0], OmmFile)
    assert catalog.records[0].tle_parameters is not None
    assert catalog.records[0].tle_parameters.norad_cat_id == 5


def test_a_multi_record_catalogue_parses_into_a_sequence() -> None:
    catalog = read(GOLDEN_CATALOG_CSV.read_bytes(), format="omm-csv").source_native
    assert isinstance(catalog, OmmCatalog)
    sequence = catalog.to_canonical()
    assert len(sequence) == 3
    assert [m.metadata.object_name for m in sequence] == ["ISS (ZARYA)", "VANGUARD 1", "STARLETTE"]
    assert [m.metadata.object_id for m in sequence] == ["1998-067A", "1958-002B", "1975-010A"]
    assert sequence[1].mean_motion == pytest.approx(10.85873516)
    # each record carries its own fidelity model, so it round-trips on its own
    assert all(isinstance(m.source_native, OmmFile) for m in sequence)


# --- round trips -----------------------------------------------------------------------


def test_golden_json_round_trip_is_byte_stable() -> None:
    golden = GOLDEN_JSON.read_bytes()
    assert write_omm_json(read(golden, format="omm-json")) == golden


def test_golden_csv_round_trip_is_byte_stable() -> None:
    golden = GOLDEN_CSV.read_bytes()
    assert write_omm_csv(read(golden, format="omm-csv")) == golden


def test_catalogue_round_trip_reproduces_every_record() -> None:
    golden = GOLDEN_CATALOG_CSV.read_bytes()
    assert write_omm_csv(read(golden, format="omm-csv")) == golden


def test_default_round_trip_preserves_canonical_content() -> None:
    mean_set = read(OMM_JSON)
    assert read(write_omm_json(mean_set)) == mean_set


def test_json_to_csv_cross_encoding_is_content_lossless() -> None:
    mean_set = read(OMM_JSON)
    via_csv = read(write_omm_csv(mean_set), format="omm-csv")
    assert isinstance(mean_set, MeanElementSet) and isinstance(via_csv, MeanElementSet)
    # the same canonical mean set, only the provenance source-format differs (json vs csv)
    assert via_csv.metadata.object_id == mean_set.metadata.object_id
    assert via_csv.epoch == mean_set.epoch
    assert via_csv.mean_motion == pytest.approx(mean_set.mean_motion)
    assert via_csv.eccentricity == pytest.approx(mean_set.eccentricity)
    assert via_csv.inclination == pytest.approx(mean_set.inclination)
    assert via_csv.raan == pytest.approx(mean_set.raan)
    assert via_csv.arg_periapsis == pytest.approx(mean_set.arg_periapsis)
    assert via_csv.mean_anomaly == pytest.approx(mean_set.mean_anomaly)
    assert via_csv.bstar == pytest.approx(mean_set.bstar)
    assert via_csv.mean_motion_dot == pytest.approx(mean_set.mean_motion_dot)


def test_retain_source_round_trip_is_byte_identical() -> None:
    mean_set = read(OMM_JSON, retain_source=True)
    assert isinstance(mean_set.source_native, OmmCatalog)
    assert mean_set.source_native.raw_bytes == OMM_JSON
    assert write_omm_json(mean_set) == OMM_JSON


def test_public_write_to_file_round_trips(tmp_path: Path) -> None:
    destination = tmp_path / "out.csv"
    write(read(GOLDEN_CSV.read_bytes(), format="omm-csv"), destination)
    assert destination.read_bytes() == GOLDEN_CSV.read_bytes()


# --- the TLE -> OMM-JSON route (same canonical form, no new edge) -----------------------


def test_tle_converts_to_omm_json_carrying_the_identifiers() -> None:
    tle = (
        b"ISS (ZARYA)\n"
        b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
        b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
    )
    out = write_omm_json(convert(read(io.BytesIO(tle), format="tle"), to="omm-json"))
    record = read(out).source_native
    assert isinstance(record, OmmCatalog)
    assert record.records[0].metadata.object_name == "ISS (ZARYA)"
    assert record.records[0].tle_parameters is not None
    assert record.records[0].tle_parameters.norad_cat_id == 25544


# --- the "warn on a field the encoding cannot hold" contract ---------------------------


def test_writing_an_omm_with_covariance_warns_for_what_is_dropped() -> None:
    omm_kvn = (_DATA / "golden_omm.omm").read_bytes()
    mean_set = convert(read(omm_kvn), to="omm-json")
    with pytest.warns(Warning) as caught:
        write_omm_json(mean_set)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert {"COVARIANCE", "SPACECRAFT_PARAMETERS", "CREATION_DATE", "USER_DEFINED"} <= warned


def test_writing_a_non_default_frame_warns() -> None:
    framed = OMM_JSON.replace(b'"OBJECT_NAME"', b'"REF_FRAME": "GCRF",\n  "OBJECT_NAME"')
    with pytest.warns(Warning) as caught:
        write_omm_csv(read(framed))
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "REF_FRAME" in warned


def test_same_encoding_write_loses_nothing(assert_no_silent_loss: Callable[..., None]) -> None:
    mean_set = read(GOLDEN_JSON.read_bytes(), format="omm-json")
    assert_no_silent_loss(lambda: write_omm_json(mean_set), loses=False)


def test_writing_a_non_mean_set_is_rejected() -> None:
    from orbit_formats import Ephemeris

    ephemeris = Ephemeris(
        metadata=Metadata(reference_frame="TEME"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.raises(UnsupportedConversionError, match="omm-json"):
        write_omm_json(ephemeris)


# --- malformed inputs ------------------------------------------------------------------


def test_malformed_json_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="not valid JSON"):
        read(b"{not json", format="omm-json")


def test_a_json_scalar_top_level_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="object or an array"):
        read(b"42", format="omm-json")


def test_a_non_object_record_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="not an object"):
        read(b'["nope"]', format="omm-json")


def test_an_empty_catalogue_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="no records"):
        read(b"[]", format="omm-json")


def test_a_header_only_csv_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="no records"):
        read(b"OBJECT_NAME,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION\n", format="omm-csv")


def test_an_empty_csv_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="empty"):
        read(b"\n\n", format="omm-csv")


def test_a_record_missing_the_mean_elements_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="EPOCH"):
        read(b'[{"OBJECT_NAME": "SAT"}]', format="omm-json")
