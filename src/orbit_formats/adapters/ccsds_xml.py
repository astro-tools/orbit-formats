"""The CCSDS NDM/XML plumbing seam — parse and serialise the xsdata bindings.

This module is the *XML half* of the binding↔canonical adapter seam. The xsdata-generated
bindings under :mod:`orbit_formats._ccsds_xsd` are schema-faithful dataclasses (one per NDM
message: ``Oem``, ``Omm``, ``Opm``, …); this module turns NDM/XML bytes into those bindings
and back, so a per-message reader/writer only has to write its *mapping* — the binding's
fields to and from the canonical metamodel — and never touches the XML machinery.

A per-message XML reader is therefore::

    from orbit_formats._ccsds_xsd import Oem
    from orbit_formats.adapters.ccsds_xml import parse_ndm_xml

    binding = parse_ndm_xml(source.read_bytes(), Oem)   # bytes -> faithful binding
    ephemeris = _OemXmlAdapter().to_canonical(binding)  # binding -> canonical (the mapping)

and the writer is the mirror image, ending in :func:`serialize_ndm_xml`. The mapping step
is an :class:`~orbit_formats.adapters.base.Adapter` like every other format's; only the
binding type and the two helpers here are CCSDS-XML-specific.

These helpers are deliberately generic over the binding type the caller supplies, so this
module imports only the xsdata runtime — never the large generated binding module. That
keeps it (and anything that imports it) cheap until a real message binding is actually
parsed. It is *not* re-exported from :mod:`orbit_formats.adapters`, so importing the
package stays free of the xsdata dependency until an XML path is exercised.
"""

from __future__ import annotations

from typing import TypeVar

from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.serializers import XmlSerializer
from xsdata.formats.dataclass.serializers.config import SerializerConfig

__all__ = ["NDM_XML_NAMESPACE", "parse_ndm_xml", "serialize_ndm_xml"]

T = TypeVar("T")

#: The single XML namespace every NDM/XML (unqualified) message lives in. The vendored
#: schemas declare it as ``targetNamespace``; it is the same ``urn:ccsds:`` marker the KVN
#: detector keys on.
NDM_XML_NAMESPACE = "urn:ccsds:schema:ndmxml"


def parse_ndm_xml(data: bytes, binding_type: type[T]) -> T:
    """Parse NDM/XML ``data`` into an instance of ``binding_type``.

    ``binding_type`` is one of the generated message bindings (e.g.
    :class:`orbit_formats._ccsds_xsd.Oem`). The whole document is bound — every element and
    attribute the schema defines — so the returned object is the faithful fidelity model a
    same-format write reconstructs from. A document that does not match the binding's schema
    raises an :class:`xsdata.exceptions.ParserError`; callers translate that into the
    library's :class:`~orbit_formats.errors.MalformedSourceError` at the reader boundary.
    """
    return XmlParser().from_bytes(data, binding_type)


def serialize_ndm_xml(binding: object, *, indent: bool = True) -> bytes:
    """Serialise a generated NDM/XML binding back to UTF-8 bytes with an XML declaration.

    ``binding`` is any populated message binding (the object :func:`parse_ndm_xml` returns,
    or one a writer builds). ``indent`` pretty-prints with two-space indentation (the form
    the CCSDS examples use); pass ``indent=False`` for a compact single-line document.
    """
    config = SerializerConfig(indent="  " if indent else None)
    return XmlSerializer(config=config).render(binding).encode("utf-8")
