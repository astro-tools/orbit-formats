"""Content-signature-first format auto-detection."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from orbit_formats import AmbiguousFormatError, UnknownFormatError, detect_format
from orbit_formats.formats import (
    Confidence,
    canonical_form,
    extension_format,
    is_writable,
    known_format_ids,
    match_binary,
)

# A real, checksum-valid ISS TLE (the canonical sgp4 test element set).
TLE = (
    b"ISS (ZARYA)\n"
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)
OEM_KVN = b"CCSDS_OEM_VERS = 2.0\nCREATION_DATE = 2024-08-17T00:00:00\nORIGINATOR = ASTRO\n"
OMM_KVN = b"CCSDS_OMM_VERS = 2.0\nCREATION_DATE = 2024-08-17T00:00:00\n"
OPM_KVN = b"CCSDS_OPM_VERS = 2.0\n"
AEM_KVN = b"CCSDS_AEM_VERS = 1.0\n"
CDM_KVN = b"CCSDS_CDM_VERS = 1.0\n"
OEM_XML = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<oem id="CCSDS_OEM_VERS" version="2.0" '
    b'xmlns="urn:ccsds:recommendation:navigation:schema:ndmxml">\n'
)
# The unqualified form orbit-formats' own serialiser emits — no urn:ccsds: namespace, just
# the <oem> root and the CCSDS_OEM_VERS id marker.
OEM_XML_UNQUALIFIED = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<oem id="CCSDS_OEM_VERS" version="3.0">\n'
    b"  <header><CREATION_DATE>2024-01-01T00:00:00</CREATION_DATE>"
    b"<ORIGINATOR>ASTRO-TOOLS</ORIGINATOR></header>\n"
)
SP3 = b"#cP2024  8 17  0  0  0.00000000      96 ORBIT IGS20 HLM  IGS\n"
STK = b"stk.v.11.0\nBEGIN Ephemeris\nNumberOfEphemerisPoints 2\n"
RINEX = b"     3.04           N: GNSS NAV DATA    M: MIXED            RINEX VERSION / TYPE\n"
SPK = b"DAF/SPK " + b"\x00" * 120


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (TLE, "tle"),
        (OEM_KVN, "ccsds-oem"),
        (OMM_KVN, "ccsds-omm"),
        (OPM_KVN, "ccsds-opm"),
        (AEM_KVN, "ccsds-aem"),
        (CDM_KVN, "ccsds-cdm"),
        (OEM_XML, "ccsds-oem"),
        (SP3, "sp3"),
        (STK, "stk-ephemeris"),
        (RINEX, "rinex-nav"),
        (SPK, "spk"),
    ],
)
def test_detect_by_content_signature(content: bytes, expected: str) -> None:
    assert detect_format(content) == expected


def test_unqualified_oem_xml_is_detected_by_content() -> None:
    # orbit-formats' serialiser emits OEM XML without the urn:ccsds: namespace; the signature
    # must recognise it from the <oem> root plus the CCSDS_OEM_VERS marker alone.
    assert detect_format(OEM_XML_UNQUALIFIED) == "ccsds-oem"


def test_binary_magic_is_checked_before_text_decode() -> None:
    # The SPK id word is valid UTF-8, so this also proves the binary detector wins outright.
    assert match_binary(SPK) == "spk"
    assert match_binary(OEM_KVN) is None


def test_detect_from_a_path(tmp_path: Path) -> None:
    target = tmp_path / "sat.tle"
    target.write_bytes(TLE)
    assert detect_format(target) == "tle"


def test_detect_from_a_named_buffer() -> None:
    buffer = io.BytesIO(SP3)
    buffer.name = "igs.sp3"
    assert detect_format(buffer) == "sp3"


def test_gmat_report_is_detected_by_extension(tmp_path: Path) -> None:
    # The GMAT report has no content signature; only its extension identifies it.
    target = tmp_path / "mission.report"
    target.write_text("A1ModJulian   X   Y   Z\n12345.0  7000 0 0\n")
    assert detect_format(target) == "gmat-report"


def test_extension_breaks_a_signature_tie(tmp_path: Path) -> None:
    target = tmp_path / "doc.oem"
    target.write_bytes(OEM_KVN + OMM_KVN)  # both CCSDS_*_VERS keywords present
    assert detect_format(target) == "ccsds-oem"


def test_ambiguous_content_without_a_tiebreaker_raises() -> None:
    with pytest.raises(AmbiguousFormatError) as excinfo:
        detect_format(OEM_KVN + OMM_KVN)  # bytes: no extension to break the tie
    assert set(excinfo.value.candidates) == {"ccsds-oem", "ccsds-omm"}


def test_a_corrupted_tle_checksum_is_not_detected_as_tle() -> None:
    broken = TLE.replace(b"0  2927\n", b"0  2928\n")  # flip line-1 checksum
    with pytest.raises(UnknownFormatError):
        detect_format(broken)


def test_unknown_text_content_raises() -> None:
    with pytest.raises(UnknownFormatError, match="matched no known signature"):
        detect_format(b"just some notes\nwith nothing recognisable\n")


def test_unknown_binary_content_raises() -> None:
    with pytest.raises(UnknownFormatError, match="binary content"):
        detect_format(b"\x00\x01\x02\x03 not a kernel")


def test_non_utf8_text_still_decodes_via_latin1() -> None:
    # Invalid UTF-8 but no NUL byte: decodes as latin-1, then fails to match a signature.
    with pytest.raises(UnknownFormatError):
        detect_format(b"\xff\xfe some latin-1 bytes, no signature")


def test_catalog_helpers() -> None:
    assert "tle" in known_format_ids()
    assert canonical_form("ccsds-oem") == "ephemeris"
    assert canonical_form("tle") == "mean-elements"
    assert is_writable("ccsds-oem") is True
    assert is_writable("rinex-nav") is False
    assert is_writable("gmat-report") is False  # read-only: GMAT writes reports, we only read
    assert extension_format(".oem") == "ccsds-oem"
    assert extension_format(".21n") == "rinex-nav"  # version-2 RINEX nav suffix
    assert extension_format(".xml") is None  # too generic to map
    assert extension_format(None) is None
    assert Confidence.HIGH > Confidence.NONE
