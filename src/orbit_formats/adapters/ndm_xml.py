"""The combined-NDM/XML seam: the xsdata ``Ndm`` wrapper ↔ a sequence of canonical messages.

The aggregate is a *container*, so its adapter is an orchestration layer rather than a new
mapping: it reuses each member message's existing reader and writer through a thin bytes
bridge. Reading parses the ``<ndm>`` wrapper into the xsdata :class:`~orbit_formats._ccsds_xsd.Ndm`
binding, re-emits each child element as its own one-message document, and hands that to the
member format's registered reader — so every child is produced by exactly the code path that
reads it standalone, ``source_native`` and all. Writing is the mirror: each child canonical is
serialised by its registered XML writer, reparsed to its binding, and nested into a fresh
``Ndm``.

Two consequences of the xsdata binding shape are load-bearing:

- ``NdmType`` stores children in one typed list *per message type* (``oem``, ``cdm``, …), not a
  single ordered choice, so serialisation **groups children by type** in declaration order.
  The reader yields them in that same grouped order, and the KVN writer normalises to it too,
  which is what lets the KVN and XML notations stay at parity.
- The wrapper carries only ``MESSAGE_ID`` and wrapper-level ``COMMENT``s; there is no
  per-wrapper header (no ``CREATION_DATE`` / ``ORIGINATOR``). Each child keeps its own header.

``acm`` / ``rdm`` children are part of the schema but have no reader/writer in this library; an
aggregate that carries one is rejected rather than silently dropped. Imported lazily (only when
a combined NDM in XML is read or written), never at package import time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields as dataclass_fields
from typing import Any

from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    Aem,
    Apm,
    Cdm,
    Ndm,
    Ocm,
    Oem,
    Omm,
    Opm,
    Tdm,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.canonical.base import Canonical
from orbit_formats.errors import MalformedSourceError, UnsupportedFormatError
from orbit_formats.readers.ccsds_ndm import NDM_CHILD_ORDER
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.source import Source
from orbit_formats.writers.ndm import member_format

__all__ = ["combined_children_from_xml", "xml_bytes_from_messages"]

# Each supported member format id mapped to its xsdata *root* binding class (which subclasses
# the ``ndmType`` field's base, so it nests directly into ``Ndm``) and the ``Ndm`` field that
# holds it. Keyed in ``NDM_CHILD_ORDER`` so iteration yields the type-grouped order the XML
# wrapper itself serialises in.
_ROOT_BY_FORMAT: dict[str, tuple[type[Any], str]] = {
    "ccsds-aem": (Aem, "aem"),
    "ccsds-apm": (Apm, "apm"),
    "ccsds-cdm": (Cdm, "cdm"),
    "ccsds-ocm": (Ocm, "ocm"),
    "ccsds-oem": (Oem, "oem"),
    "ccsds-omm": (Omm, "omm"),
    "ccsds-opm": (Opm, "opm"),
    "ccsds-tdm": (Tdm, "tdm"),
}

# Schema-defined child elements with no reader/writer in this library. Present in an input
# aggregate, they are rejected (never dropped silently).
_UNSUPPORTED_CHILDREN = ("acm", "rdm")


# --- XML -> canonical messages ---------------------------------------------------------


def combined_children_from_xml(
    data: bytes,
) -> tuple[tuple[Canonical, ...], str | None, tuple[str, ...]]:
    """Parse combined-NDM XML into ``(messages, message_id, comments)``.

    ``messages`` are the children in the wrapper's type-grouped order, each produced by its
    member format's registered reader (so each carries its own ``source_native``). Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for XML that is not a well-formed
    ``<ndm>`` and :class:`~orbit_formats.errors.UnsupportedFormatError` for an aggregate that
    carries a child type this library cannot read (``acm`` / ``rdm``).
    """
    try:
        ndm = parse_ndm_xml(data, Ndm)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the combined NDM XML: {exc}") from exc

    present_unsupported = [name for name in _UNSUPPORTED_CHILDREN if getattr(ndm, name)]
    if present_unsupported:
        raise UnsupportedFormatError(
            f"the combined NDM carries {', '.join(present_unsupported)} message(s), which this "
            "version does not read"
        )

    messages: list[Canonical] = []
    for fmt in NDM_CHILD_ORDER:
        root_cls, field_name = _ROOT_BY_FORMAT[fmt]
        for child in getattr(ndm, field_name):
            messages.append(_read_child(child, root_cls, fmt))
    return tuple(messages), ndm.message_id, tuple(ndm.comment)


def _read_child(child: Any, root_cls: type[Any], fmt: str) -> Canonical:
    """Route one parsed child binding through ``fmt``'s registered reader via a bytes bridge.

    The parsed child is a base ``ndmType`` element; re-rooting it as its own root binding
    (``OemType`` → ``Oem`` etc., a copy of the writable fields) lets it serialise as a
    standalone one-message document the member reader accepts unchanged. Fixed ``init=False``
    attributes (the ``id`` version marker) are not constructor arguments — the root restores
    them from their own defaults.
    """
    root = root_cls(**{f.name: getattr(child, f.name) for f in dataclass_fields(child) if f.init})
    reader = get_reader(fmt)
    if reader is None:  # pragma: no cover - every _ROOT_BY_FORMAT id has a registered reader
        raise UnsupportedFormatError(f"no reader is registered for the NDM member {fmt!r}")
    return reader(Source(data=serialize_ndm_xml(root)))


# --- canonical messages -> XML ---------------------------------------------------------


def xml_bytes_from_messages(
    messages: Sequence[Canonical], message_id: str | None, comments: Sequence[str]
) -> bytes:
    """Serialise canonical ``messages`` into a combined-NDM ``<ndm>`` document.

    Each child is serialised by its member format's registered XML writer and reparsed to its
    binding, then nested into a fresh ``Ndm`` whose typed-list fields group the children by
    type. The member format of each child is taken from its ``source_native``; a child not
    carrying an NDM member ``source_native`` raises
    :class:`~orbit_formats.errors.UnsupportedConversionError`.
    """
    ndm = Ndm(message_id=message_id, comment=list(comments))
    for child in messages:
        field_name, binding = _child_binding(child)
        getattr(ndm, field_name).append(binding)
    return serialize_ndm_xml(ndm)


def _child_binding(child: Canonical) -> tuple[str, object]:
    """The ``(ndm_field_name, root_binding)`` for one child, via its registered XML writer."""
    fmt = member_format(child)
    root_cls, field_name = _ROOT_BY_FORMAT[fmt]
    writer = get_writer(fmt)
    if writer is None:  # pragma: no cover - every _ROOT_BY_FORMAT id has a registered writer
        raise UnsupportedFormatError(f"no writer is registered for the NDM member {fmt!r}")
    return field_name, parse_ndm_xml(writer(child, ".xml"), root_cls)
