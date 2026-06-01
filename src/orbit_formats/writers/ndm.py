"""Combined-NDM writer — KVN concatenation and ``<ndm>`` XML for an aggregate of messages.

Like the reader, this is an orchestration layer: it serialises each child through the member
format's own registered writer (so every member is written by the exact code path that writes
it standalone) and assembles the result.

- **XML** builds the standardised ``<ndm>`` wrapper through the xsdata bindings
  (:mod:`orbit_formats.adapters.ndm_xml`, imported lazily). Children group by message type.
- **KVN** concatenates the members' own KVN output, normalised to the same type-grouped order
  the XML wrapper uses, so the two notations stay at parity. The wrapper comments lead as
  ``COMMENT`` lines; the wrapper ``MESSAGE_ID`` has no KVN home, so it is reported as a loss
  rather than dropped silently.

The notation is chosen from the destination extension (``.ndm`` / ``.kvn`` → KVN, ``.xml`` →
XML), else the source's own notation, else KVN. Tier one (byte-identical) echoes the retained
source bytes when the requested notation matches; otherwise the aggregate is re-serialised from
its members (content-lossless). The member format each child writes as is taken from its
``source_native``, so the children must be objects read from — or tagged with — an NDM message.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.combined import Combined
from orbit_formats.errors import UnsupportedConversionError, UnsupportedFormatError
from orbit_formats.readers.ccsds_ndm import NDM_CHILD_ORDER, NdmFile
from orbit_formats.registry import get_writer, register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _comment_lines

__all__ = ["member_format", "write_ndm"]

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".ndm", ".kvn")

# Every member's own KVN extension forces its writer into KVN (all member writers accept this).
_MEMBER_KVN_SUFFIX = ".kvn"


def write_ndm(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`Combined`) to combined-NDM bytes (KVN or XML).

    Picks the byte-identical or re-serialised path automatically, and the KVN or XML notation
    from ``suffix`` else the source's own notation else KVN. Raises
    :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not a
    :class:`Combined`, or if a child does not carry an NDM member ``source_native`` identifying
    the message it serialises as.
    """
    if not isinstance(obj, Combined):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-ndm", "ndm")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    source_notation = native.serialization if isinstance(native, NdmFile) else None
    notation = requested or source_notation or "kvn"
    if isinstance(native, NdmFile) and native.raw_bytes is not None and notation == source_notation:
        return native.raw_bytes
    if notation == "xml":
        from orbit_formats.adapters.ndm_xml import xml_bytes_from_messages

        return xml_bytes_from_messages(obj.messages, obj.message_id, obj.comments)
    return _serialize_kvn(obj)


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_kvn(combined: Combined) -> bytes:
    """Concatenate the members' KVN output under the wrapper comments, in type-grouped order."""
    if combined.message_id is not None:
        warn_lossy(
            LossyConversionWarning(
                "the combined-NDM MESSAGE_ID has no KVN representation; it was dropped",
                dropped=(
                    DroppedField("MESSAGE_ID", "KVN has no combined-NDM wrapper to carry it"),
                ),
            ),
            stacklevel=3,
        )
    blocks: list[str] = []
    header = _comment_lines(combined.comments)
    if header:
        blocks.append("\n".join(header))
    blocks.extend(_member_kvn(child) for child in _ordered(combined.messages))
    return ("\n\n".join(blocks) + "\n").encode("utf-8")


def _ordered(messages: Iterable[Canonical]) -> list[Canonical]:
    """The members in the canonical type-grouped order, stable within a type."""
    return sorted(messages, key=lambda child: NDM_CHILD_ORDER.index(member_format(child)))


def _member_kvn(child: Canonical) -> str:
    """One member's KVN text (no trailing blank line) via its registered writer."""
    fmt = member_format(child)
    writer = get_writer(fmt)
    if writer is None:  # pragma: no cover - every NDM_CHILD_ORDER id has a registered writer
        raise UnsupportedFormatError(f"no writer is registered for the NDM member {fmt!r}")
    return writer(child, _MEMBER_KVN_SUFFIX).decode("utf-8").rstrip("\n")


def member_format(child: Canonical) -> str:
    """The NDM member format id a child serialises as, taken from its ``source_native``.

    Shared by the KVN concatenation here and the XML wrapper assembly in
    :mod:`orbit_formats.adapters.ndm_xml`. Raises
    :class:`~orbit_formats.errors.UnsupportedConversionError` when a child carries no NDM member
    ``source_native`` to identify the message it should serialise as.
    """
    native = child.source_native
    fmt = getattr(native, "format_name", None) if native is not None else None
    if not isinstance(fmt, str) or fmt not in NDM_CHILD_ORDER:
        raise UnsupportedConversionError(type(child).__name__, "ccsds-ndm", "ndm")
    return fmt


register_writer("ccsds-ndm", write_ndm)
