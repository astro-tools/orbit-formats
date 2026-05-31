"""Smoke-test the CCSDS NDM/XML binding layer and its parse/serialise seam.

This exercises the v0.2 foundation (the xsdata-generated bindings plus the
``adapters.ccsds_xml`` plumbing) end to end, without any per-message canonical mapping —
that lands with the individual XML readers/writers. The contract proven here is the one the
per-message issues build on: NDM/XML bytes parse into a schema-faithful binding, and that
binding serialises back to a well-formed NDM/XML document that round-trips.
"""

from __future__ import annotations

from pathlib import Path

from orbit_formats._ccsds_xsd import Oem
from orbit_formats.adapters.ccsds_xml import (
    NDM_XML_NAMESPACE,
    parse_ndm_xml,
    serialize_ndm_xml,
)

SAMPLE = Path(__file__).parent / "data" / "oem" / "sample_oem.xml"


def test_parse_binds_every_field_of_the_message() -> None:
    oem = parse_ndm_xml(SAMPLE.read_bytes(), Oem)

    assert oem.id == "CCSDS_OEM_VERS"
    assert oem.version == "3.0"
    assert oem.header.originator == "ASTRO-TOOLS"

    segment = oem.body.segment[0]
    assert segment.metadata.object_name == "SAT"
    assert segment.metadata.ref_frame == "EME2000"
    assert segment.metadata.time_system == "UTC"

    states = segment.data.state_vector
    assert len(states) == 2
    assert str(states[0].epoch) == "2024-01-01T00:00:00"
    assert states[0].x.value == 7000.0
    assert states[1].z_dot.value == 0.0


def test_serialise_emits_a_well_formed_ndm_xml_document() -> None:
    oem = parse_ndm_xml(SAMPLE.read_bytes(), Oem)
    rendered = serialize_ndm_xml(oem)

    assert isinstance(rendered, bytes)
    assert rendered.startswith(b"<?xml")
    assert b"<oem" in rendered


def test_binding_round_trips_through_the_seam() -> None:
    original = parse_ndm_xml(SAMPLE.read_bytes(), Oem)
    reparsed = parse_ndm_xml(serialize_ndm_xml(original), Oem)

    # The faithful binding survives a parse -> serialise -> parse cycle unchanged: the
    # xsdata bindings are plain dataclasses, so structural equality is exact.
    assert reparsed == original


def test_compact_and_indented_serialisations_parse_to_the_same_binding() -> None:
    oem = parse_ndm_xml(SAMPLE.read_bytes(), Oem)

    indented = serialize_ndm_xml(oem, indent=True)
    compact = serialize_ndm_xml(oem, indent=False)

    assert b"\n  " in indented  # the indented form carries two-space indentation
    assert b"\n  " not in compact  # the compact form is a single line of elements
    assert parse_ndm_xml(indented, Oem) == parse_ndm_xml(compact, Oem)


def test_namespace_constant_matches_the_vendored_schema() -> None:
    assert NDM_XML_NAMESPACE == "urn:ccsds:schema:ndmxml"
