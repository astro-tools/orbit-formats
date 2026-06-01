"""The combined-NDM XML reader and writer, and KVN ↔ XML parity.

The XML notation is the standardised ``<ndm>`` wrapper. It is parsed by routing each child
element through its member format's own reader, and written by nesting each member's own XML
output into the wrapper. ``golden_ndm.xml`` is the XML twin of ``golden_ndm.ndm`` — the same
aggregate (a CDM and an OEM, no wrapper ``MESSAGE_ID``) in the other notation — so the two
parse to an equal :class:`~orbit_formats.Combined`. The XML wrapper groups members by type,
and the KVN writer normalises to the same order, which is what makes the parity hold.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orbit_formats import (
    Combined,
    MalformedSourceError,
    UnknownFormatError,
    UnsupportedFormatError,
    detect_format,
    read,
    write,
)
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.readers.ccsds_ndm import NdmFile
from orbit_formats.writers.ndm import write_ndm

DATA = Path(__file__).parent / "data"
GOLDEN_KVN = DATA / "ndm" / "golden_ndm.ndm"
GOLDEN_XML = DATA / "ndm" / "golden_ndm.xml"
GOLDEN_OEM = DATA / "oem" / "golden_roundtrip.oem"
GOLDEN_CDM = DATA / "cdm" / "golden_cdm.cdm"


# --- reader ----------------------------------------------------------------------------


def test_unqualified_ndm_xml_is_detected() -> None:
    assert detect_format(GOLDEN_XML.read_bytes()) == "ccsds-ndm"


def test_read_xml_returns_a_combined_tagged_xml() -> None:
    combined = read(GOLDEN_XML.read_bytes())
    assert isinstance(combined, Combined)
    assert [type(m).__name__ for m in combined.messages] == ["Conjunction", "Ephemeris"]
    native = combined.source_native
    assert isinstance(native, NdmFile)
    assert native.serialization == "xml"
    # each member was read through its own XML reader, so its fidelity model is tagged xml too
    assert all(getattr(m.source_native, "serialization", None) == "xml" for m in combined.messages)


def test_read_xml_from_a_path(tmp_path: Path) -> None:
    target = tmp_path / "aggregate.xml"
    target.write_bytes(GOLDEN_XML.read_bytes())
    assert isinstance(read(target, format="ccsds-ndm"), Combined)


def test_malformed_ndm_xml_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="could not parse the combined NDM XML"):
        read(b"<ndm><oem>", format="ccsds-ndm")


def test_an_unreadable_member_type_in_xml_is_rejected() -> None:
    # An <ndm> carrying an ACM — a member type this library has no reader for — must fail loudly
    # rather than drop it. (The committed fixture is a minimal but schema-shaped ACM child.)
    aggregate = (DATA / "ndm" / "unsupported_member.xml").read_bytes()
    assert detect_format(aggregate) == "ccsds-ndm"
    with pytest.raises(UnsupportedFormatError, match="acm"):
        read(aggregate, format="ccsds-ndm")


# --- writer tiers ----------------------------------------------------------------------


def test_xml_round_trip_is_byte_stable_against_the_golden() -> None:
    golden = GOLDEN_XML.read_bytes()
    assert write_ndm(read(golden), ".xml") == golden


def test_retain_source_xml_round_trip_is_byte_identical() -> None:
    golden = GOLDEN_XML.read_bytes()
    combined = read(golden, retain_source=True)
    assert write_ndm(combined, ".xml") == golden


def test_public_write_to_xml_needs_an_explicit_format(tmp_path: Path) -> None:
    combined = read(GOLDEN_KVN.read_bytes())
    with pytest.raises(UnknownFormatError, match="could not infer the target format"):
        write(combined, tmp_path / "out.xml")
    destination = tmp_path / "out.xml"
    write(combined, destination, format="ccsds-ndm")
    assert destination.read_bytes().startswith(b"<?xml")
    assert read(destination) == combined


def test_destination_extension_overrides_the_source_notation() -> None:
    from_xml = read(GOLDEN_XML.read_bytes())
    as_kvn = write_ndm(from_xml, ".ndm")
    assert as_kvn.startswith(b"COMMENT")
    assert read(as_kvn) == from_xml

    from_kvn = read(GOLDEN_KVN.read_bytes())
    as_xml = write_ndm(from_kvn, ".xml")
    assert as_xml.startswith(b"<?xml")
    assert read(as_xml) == from_kvn


def test_message_id_round_trips_through_xml() -> None:
    cdm = read(GOLDEN_CDM.read_bytes())
    oem = read(GOLDEN_OEM.read_bytes())
    combined = Combined(
        metadata=Metadata(provenance=Provenance(source_format="ccsds-ndm")),
        messages=(oem, cdm),
        message_id="NDM-MSG-7",
        comments=("with a wrapper id",),
    )
    via_xml = read(write_ndm(combined, ".xml"))
    assert isinstance(via_xml, Combined)
    assert via_xml.message_id == "NDM-MSG-7"
    assert via_xml.comments == ("with a wrapper id",)


# --- KVN <-> XML parity ----------------------------------------------------------------


def test_kvn_and_xml_parse_to_an_equal_combined() -> None:
    assert read(GOLDEN_KVN.read_bytes()) == read(GOLDEN_XML.read_bytes())


def test_parity_holds_through_a_kvn_to_xml_to_kvn_round_trip() -> None:
    from_kvn = read(GOLDEN_KVN.read_bytes())
    via_xml = read(write_ndm(from_kvn, ".xml"))
    assert via_xml == from_kvn
