"""Combined-NDM reader — the aggregate container that holds several member messages in one file.

The combined NDM composes the individual messages this library already reads: an OPM plus a
CDM, several OEMs, any mix. This reader is an orchestration layer, not a new parser — it splits
the aggregate into its members and hands each to the member format's existing registered reader,
so every child is the same object reading that message alone would produce, ``source_native``
and all. The members are returned in a :class:`~orbit_formats.canonical.combined.Combined`, the
canonical container :func:`~orbit_formats.read` yields for an aggregate.

The two notations:

- **XML** is the standardised ``<ndm>`` wrapper, parsed through the xsdata bindings
  (:mod:`orbit_formats.adapters.ndm_xml`, imported lazily). Its children are grouped by message
  type; this reader yields them in that grouped order.
- **KVN** has no standardised wrapper, so the aggregate is the individual KVN messages
  concatenated, each keeping its ``CCSDS_<TYPE>_VERS =`` header. The reader splits on those
  headers and dispatches each chunk. ``COMMENT`` lines before the first member become the
  wrapper's comments; there is no KVN home for the wrapper ``MESSAGE_ID`` (it reads as ``None``).

A member type the library has no reader for (``acm`` / ``rdm``, or a ``CCSDS_ACM_VERS`` /
``CCSDS_RDM_VERS`` KVN header) is rejected, never dropped silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar, Literal

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.combined import Combined
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError, UnsupportedFormatError
from orbit_formats.readers.ccsds import _comment_text, _is_comment, _looks_like_xml
from orbit_formats.registry import get_reader, register_reader
from orbit_formats.source import Source

__all__ = ["NDM_CHILD_ORDER", "NdmFile", "read_ndm"]

# The member format ids in the order the XML ``<ndm>`` wrapper serialises them (the xsdata
# ``NdmType`` field order, minus the ``acm`` / ``rdm`` types this library does not read). The
# XML reader yields children in this order and the KVN writer normalises to it, so the two
# notations agree — the precondition for the KVN ↔ XML parity assertion.
NDM_CHILD_ORDER: tuple[str, ...] = (
    "ccsds-aem",
    "ccsds-apm",
    "ccsds-cdm",
    "ccsds-ocm",
    "ccsds-oem",
    "ccsds-omm",
    "ccsds-opm",
    "ccsds-tdm",
)

# A member's opening KVN header keyword mapped to its format id, for splitting a concatenation.
_VERS_TO_FORMAT: dict[str, str] = {
    "CCSDS_AEM_VERS": "ccsds-aem",
    "CCSDS_APM_VERS": "ccsds-apm",
    "CCSDS_CDM_VERS": "ccsds-cdm",
    "CCSDS_OCM_VERS": "ccsds-ocm",
    "CCSDS_OEM_VERS": "ccsds-oem",
    "CCSDS_OMM_VERS": "ccsds-omm",
    "CCSDS_OPM_VERS": "ccsds-opm",
    "CCSDS_TDM_VERS": "ccsds-tdm",
}

# A KVN member header line, e.g. ``CCSDS_OEM_VERS = 2.0`` — the boundary between members.
_VERS_HEADER_RE = re.compile(r"^\s*(CCSDS_[A-Z0-9]+_VERS)\s*=")


@dataclass(frozen=True, eq=False)
class NdmFile(FidelityModel):
    """The combined-NDM wrapper's own content — its ``MESSAGE_ID`` and comments, plus notation.

    The member messages live on the canonical :class:`Combined`, each with its own
    ``source_native``; this model carries only the wrapper-level fields a same-format write
    reconstructs. ``raw_bytes`` is the verbatim source kept when the read opted in via
    ``retain_source=True``; ``serialization`` records the notation read (``"kvn"`` / ``"xml"``)
    so a write re-emits in it by default.
    """

    format_name: ClassVar[str] = "ccsds-ndm"

    message_id: str | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_ndm(source: Source) -> Combined:
    """Read a combined NDM (KVN concatenation or ``<ndm>`` XML) into a :class:`Combined`.

    Splits the aggregate into its member messages and reads each through its registered member
    reader, preserving the wrapper ``MESSAGE_ID`` (XML only) and comments on an :class:`NdmFile`
    held as ``source_native``. Raises :class:`~orbit_formats.errors.MalformedSourceError` for a
    malformed wrapper (fewer than two KVN members, content before the first member, malformed
    XML) and :class:`~orbit_formats.errors.UnsupportedFormatError` for a member type this
    version cannot read (``acm`` / ``rdm``).

    When the read opted into retention (``read(..., retain_source=True)``), the verbatim bytes
    are kept on the fidelity model so a same-notation write reproduces them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.ndm_xml import combined_children_from_xml

        messages, message_id, comments = combined_children_from_xml(source.read_bytes())
        serialization: Literal["kvn", "xml"] = "xml"
    else:
        messages, message_id, comments = _parse_kvn_aggregate(text)
        serialization = "kvn"
    native = NdmFile(message_id=message_id, comments=comments, serialization=serialization)
    if source.retain:
        native = replace(native, raw_bytes=source.read_bytes())
    return Combined(
        metadata=Metadata(provenance=Provenance(source_format="ccsds-ndm")),
        source_native=native,
        messages=messages,
        message_id=message_id,
        comments=comments,
    )


def _parse_kvn_aggregate(
    text: str,
) -> tuple[tuple[Canonical, ...], str | None, tuple[str, ...]]:
    """Split a KVN concatenation into ``(messages, message_id, comments)``.

    Boundaries are the ``CCSDS_<TYPE>_VERS =`` header lines; each chunk runs from one header to
    the next. ``COMMENT`` lines before the first member become the wrapper comments. There must
    be at least two members for the file to be a combined NDM (a single member is that message).
    """
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if _VERS_HEADER_RE.match(line)]
    if len(headers) < 2:
        raise MalformedSourceError(
            "not a combined NDM: a KVN aggregate must concatenate two or more CCSDS messages "
            "(each with its own 'CCSDS_<TYPE>_VERS =' header)"
        )

    comments = _wrapper_comments(lines[: headers[0]])
    # Each member runs from its header line to the next header (or end of file).
    stops = [*headers[1:], len(lines)]
    messages = tuple(
        _read_kvn_member(lines[start:stop]) for start, stop in zip(headers, stops, strict=True)
    )
    return messages, None, comments


def _wrapper_comments(lines: list[str]) -> tuple[str, ...]:
    """The wrapper ``COMMENT`` lines preceding the first member; reject any other content."""
    comments: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not _is_comment(stripped):
            raise MalformedSourceError(
                f"unexpected content before the first combined-NDM member: {line!r}"
            )
        comments.append(_comment_text(stripped))
    return tuple(comments)


def _read_kvn_member(chunk: list[str]) -> Canonical:
    """Read one member chunk through its registered reader, keyed by its VERS header keyword."""
    match = _VERS_HEADER_RE.match(chunk[0])
    assert match is not None  # the chunk starts on a header by construction
    keyword = match.group(1)
    fmt = _VERS_TO_FORMAT.get(keyword)
    if fmt is None:
        raise UnsupportedFormatError(
            f"the combined NDM contains a {keyword} member, which this version does not read"
        )
    reader = get_reader(fmt)
    if reader is None:  # pragma: no cover - every _VERS_TO_FORMAT id has a registered reader
        raise UnsupportedFormatError(f"no reader is registered for the NDM member {fmt!r}")
    return reader(Source(data=("\n".join(chunk) + "\n").encode("utf-8")))


register_reader("ccsds-ndm", read_ndm)
