"""TLE ↔ OMM conversion and the TLE writer.

TLE and OMM are both mean-element sets, so the conversion is a same-canonical-form
passthrough: the format-specific richness lives in the writers. The OMM writer enriches an
OMM from a TLE source (TLE → OMM); the TLE writer echoes a TLE source verbatim or
reconstructs the lines from the mean elements and the OMM's TLE bookkeeping (OMM → TLE).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest

from orbit_formats import (
    Ephemeris,
    MeanElementSet,
    Metadata,
    UnsupportedConversionError,
    convert,
    read,
)
from orbit_formats.readers.ccsds_omm import OmmFile
from orbit_formats.registry import get_writer
from orbit_formats.warnings import LossyConversionWarning
from orbit_formats.writers.omm import write_omm
from orbit_formats.writers.tle import _format_exponential, write_tle

# A real, checksum-valid ISS 3LE.
TLE_ISS = (
    b"ISS (ZARYA)\n"
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)
# A bare 2LE (no name line) — the OMM OBJECT_NAME must be placeholdered with a warning.
TLE_2LE = (
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)


# --- TLE -> OMM ------------------------------------------------------------------------


def test_tle_to_omm_carries_the_identifiers_and_drag() -> None:
    omm = read(write_omm(read(TLE_ISS), ".omm")).source_native
    assert isinstance(omm, OmmFile)
    assert omm.metadata.object_name == "ISS (ZARYA)"
    assert omm.metadata.object_id == "1998-067A"  # OMM uses the international designator
    assert omm.metadata.ref_frame == "TEME"
    assert omm.metadata.mean_element_theory == "SGP4"
    assert omm.tle_parameters is not None
    assert omm.tle_parameters.norad_cat_id == 25544
    assert omm.tle_parameters.classification_type == "U"
    assert omm.tle_parameters.element_set_no == 292
    assert omm.tle_parameters.rev_at_epoch == 56353
    assert omm.tle_parameters.bstar == pytest.approx(-1.1606e-5)


def test_convert_tle_to_omm_is_a_same_form_passthrough() -> None:
    # Both are mean-element sets, so convert returns the object unchanged (source_native kept).
    mean_set = read(TLE_ISS)
    assert convert(mean_set, to="ccsds-omm") is mean_set


def test_tle_to_omm_without_a_name_warns_for_the_object_name() -> None:
    with pytest.warns(Warning) as caught:
        write_omm(read(TLE_2LE), ".omm")
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "OBJECT_NAME" in warned


# --- the TLE writer --------------------------------------------------------------------


def test_tle_writer_is_registered() -> None:
    assert get_writer("tle") is write_tle


def test_tle_echo_is_byte_identical() -> None:
    assert write_tle(read(TLE_ISS)) == TLE_ISS


def test_writing_a_non_mean_set_to_tle_is_rejected() -> None:
    ephemeris = Ephemeris(
        metadata=Metadata(reference_frame="TEME"),
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.raises(UnsupportedConversionError, match="tle"):
        write_tle(ephemeris)


# --- OMM -> TLE and the full round trip ------------------------------------------------


def test_omm_to_tle_reconstructs_the_lines() -> None:
    # An OMM that came from the ISS TLE carries every identifier, so OMM -> TLE rebuilds the
    # original lines exactly (checksums included).
    omm_bytes = write_omm(read(TLE_ISS), ".omm")
    tle_bytes = write_tle(read(omm_bytes))
    assert tle_bytes == TLE_ISS


def test_tle_to_omm_to_tle_round_trips_losslessly() -> None:
    original = read(TLE_ISS)
    via_omm = read(write_omm(original, ".omm"))  # MeanElementSet from the OMM
    reconstructed = read(write_tle(via_omm))  # MeanElementSet from the rebuilt TLE
    assert isinstance(original, MeanElementSet) and isinstance(reconstructed, MeanElementSet)
    assert reconstructed.mean_motion == pytest.approx(original.mean_motion)
    assert reconstructed.eccentricity == pytest.approx(original.eccentricity)
    assert reconstructed.inclination == pytest.approx(original.inclination)
    assert reconstructed.raan == pytest.approx(original.raan)
    assert reconstructed.arg_periapsis == pytest.approx(original.arg_periapsis)
    assert reconstructed.mean_anomaly == pytest.approx(original.mean_anomaly)
    assert reconstructed.bstar == pytest.approx(original.bstar)
    assert reconstructed.mean_motion_dot == pytest.approx(original.mean_motion_dot)
    assert reconstructed.epoch == original.epoch


def test_round_trip_through_xml_omm_also_reconstructs_the_tle() -> None:
    # The same round trip but through the XML notation of the OMM. The XML notation requires
    # CREATION_DATE and ORIGINATOR, which a TLE does not carry, so the writer fills them with
    # placeholders and warns rather than dropping them silently.
    with pytest.warns(LossyConversionWarning) as caught:
        xml_omm = write_omm(read(TLE_ISS), ".xml")
    dropped = {
        field
        for record in caught
        if isinstance(record.message, LossyConversionWarning)
        for field in record.message.fields
    }
    assert dropped == {"CREATION_DATE", "ORIGINATOR"}
    via_xml_omm = read(xml_omm)
    assert write_tle(via_xml_omm) == TLE_ISS


def test_reconstruction_from_a_bare_mean_set_warns_for_the_bookkeeping() -> None:
    bare = MeanElementSet(
        metadata=Metadata(object_id="25544", reference_frame="TEME"),
        epoch=np.datetime64("2008-09-20T12:25:40.104192", "ns"),
        mean_motion=15.72125391,
        eccentricity=0.0006703,
        inclination=51.6416,
        raan=247.4627,
        arg_periapsis=130.536,
        mean_anomaly=325.0288,
    )
    with pytest.warns(Warning) as caught:
        out = write_tle(bare)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert {"OBJECT_ID", "ELEMENT_SET_NO"} <= warned
    # Still a structurally valid TLE that re-reads to the same elements.
    reread = read(out)
    assert isinstance(reread, MeanElementSet)
    assert reread.mean_motion == pytest.approx(15.72125391)


def test_reconstruction_without_a_catalog_number_warns() -> None:
    bare = MeanElementSet(
        metadata=Metadata(object_id="1998-067A", reference_frame="TEME"),  # designator, not numeric
        epoch=np.datetime64("2008-09-20T12:25:40", "ns"),
        mean_motion=15.7,
        eccentricity=0.0007,
        inclination=51.6,
        raan=247.0,
        arg_periapsis=130.0,
        mean_anomaly=325.0,
    )
    with pytest.warns(Warning) as caught:
        write_tle(bare)
    warned = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "NORAD_CAT_ID" in warned


def test_exponential_field_handles_the_rounding_carry() -> None:
    # A mantissa that rounds up to 100000 must carry into the exponent rather than overflow.
    assert _format_exponential(9.99999e-6) == " 10000-4"
    assert _format_exponential(0.0) == " 00000-0"
    assert _format_exponential(-1.1606e-5) == "-11606-4"


def test_tle_round_trip_through_omm_loses_nothing(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    omm_set = read(write_omm(read(TLE_ISS), ".omm"))
    assert isinstance(omm_set.source_native, OmmFile)
    assert_no_silent_loss(lambda: write_tle(omm_set), loses=False)
