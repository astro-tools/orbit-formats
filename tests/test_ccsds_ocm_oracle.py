"""Cross-validate the OCM writer's output against the vendored official OCM XSD.

The other NDM members cross-check against ccsds-ndm, but ccsds-ndm (3.1.x) predates the OCM
(CCSDS 502.0-B-3, 2023) and cannot parse it, so there is no independent Python implementation
to read our output back. The independent check here is instead schema conformance: a separate
implementation — the ``xmlschema`` validator running the official CCSDS schema — confirms the
writer's XML is a structurally valid OCM (element order, required elements, enumerations, and
typed values), which catches a binding-serialisation bug the round-trip and parity tests, both
internal to orbit-formats, cannot.

``xmlschema`` is MIT-licensed but, like the ccsds-ndm oracle, is installed transiently only in
the CI oracle job and imported behind :func:`pytest.importorskip`, so this test skips wherever
it is absent. The vendored ``ndmxml-4.0.0-master-4.0.xsd`` declares the global ``ocm`` element
with no target namespace — exactly the unqualified form orbit-formats serialises — so the
emitted document validates directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("xmlschema")

import xmlschema

from orbit_formats import read
from orbit_formats.writers.ocm import write_ocm

_SCHEMAS = Path(__file__).parents[1] / "schemas" / "ccsds-ndm"
_MASTER_XSD = _SCHEMAS / "ndmxml-4.0.0-master-4.0.xsd"
_DATA = Path(__file__).parent / "data" / "ocm"
GOLDEN_KVN = _DATA / "golden_ocm.ocm"
GOLDEN_XML = _DATA / "golden_ocm.xml"

_SCHEMA = xmlschema.XMLSchema(str(_MASTER_XSD))


def test_writer_xml_validates_against_the_ocm_xsd() -> None:
    eph = read(GOLDEN_KVN.read_bytes())
    _SCHEMA.validate(write_ocm(eph, ".xml").decode("utf-8"))


def test_committed_golden_xml_validates_against_the_ocm_xsd() -> None:
    _SCHEMA.validate(GOLDEN_XML.read_bytes().decode("utf-8"))


def test_the_xsd_oracle_rejects_a_message_missing_a_required_element() -> None:
    # A negative control: the validator must have teeth — dropping a required element
    # (TIME_SYSTEM) makes the document invalid, so a passing positive test means something.
    broken = (
        GOLDEN_XML.read_bytes().decode("utf-8").replace("<TIME_SYSTEM>UTC</TIME_SYSTEM>", "", 1)
    )
    assert not _SCHEMA.is_valid(broken)
