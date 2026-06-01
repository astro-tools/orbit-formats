"""Cross-validate the combined-NDM writer's output against the vendored master NDM XSD.

The aggregate composes members of any type — including the OCM and ACM that ccsds-ndm (3.1.x)
predates and cannot parse — so a member-agnostic oracle is the right independent check: the
``xmlschema`` validator running the official CCSDS schema confirms the emitted ``<ndm>`` is a
structurally valid combined NDM (the wrapper, the type-grouped child elements, and each child's
own required elements and typed values), catching a binding-assembly bug the round-trip and
parity tests — both internal to orbit-formats — cannot.

``xmlschema`` is MIT-licensed but, like the ccsds-ndm oracle, is installed transiently only in
the CI oracle job and imported behind :func:`pytest.importorskip`, so this test skips wherever
it is absent. The vendored ``ndmxml-4.0.0-master-4.0.xsd`` declares the global ``ndm`` element
with no target namespace — exactly the unqualified form orbit-formats serialises — so the
emitted document validates directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("xmlschema")

import xmlschema

from orbit_formats import read
from orbit_formats.writers.ndm import write_ndm

_SCHEMAS = Path(__file__).parents[1] / "schemas" / "ccsds-ndm"
_MASTER_XSD = _SCHEMAS / "ndmxml-4.0.0-master-4.0.xsd"
_DATA = Path(__file__).parent / "data" / "ndm"
GOLDEN_KVN = _DATA / "golden_ndm.ndm"
GOLDEN_XML = _DATA / "golden_ndm.xml"

_SCHEMA = xmlschema.XMLSchema(str(_MASTER_XSD))


def test_writer_xml_validates_against_the_ndm_xsd() -> None:
    combined = read(GOLDEN_KVN.read_bytes())
    _SCHEMA.validate(write_ndm(combined, ".xml").decode("utf-8"))


def test_committed_golden_xml_validates_against_the_ndm_xsd() -> None:
    _SCHEMA.validate(GOLDEN_XML.read_bytes().decode("utf-8"))


def test_the_xsd_oracle_rejects_a_member_missing_a_required_element() -> None:
    # A negative control: the validator must have teeth — dropping a required element from a
    # child (the OEM metadata's TIME_SYSTEM) makes the aggregate invalid, so a passing positive
    # test means something.
    broken = (
        GOLDEN_XML.read_bytes().decode("utf-8").replace("<TIME_SYSTEM>UTC</TIME_SYSTEM>", "", 1)
    )
    assert not _SCHEMA.is_valid(broken)
