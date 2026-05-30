"""Format auto-detection — pick a format from a file's content signature or extension.

Detection is content-signature-first: a binary magic number is checked before any text
decode, a strong text header then identifies the format, the file extension breaks ties
or names a signature-less format (the GMAT report), and an explicit ``format=`` override
always wins. Resolution runs a deterministic, ordered detector list and reports the
highest-confidence match; genuine ambiguity raises a typed error naming the candidates,
and content that matches nothing raises a typed unknown-format error.
"""

from __future__ import annotations

from orbit_formats.errors import AmbiguousFormatError, UnknownFormatError
from orbit_formats.formats import (
    extension_format,
    is_known_format,
    known_format_ids,
    match_binary,
    score_text_formats,
)
from orbit_formats.source import Source, SourceInput, load_source

__all__ = ["detect", "detect_source"]

# How many leading bytes detection inspects. Every signature lives in a file's header, so
# a prefix is enough — a detection-only pass need not read a whole multi-megabyte ephemeris.
DETECT_PREFIX_BYTES = 65536


def detect(source: SourceInput, *, format: str | None = None) -> str:
    """Return the format id of ``source``.

    ``source`` is a path or an in-memory buffer. An explicit ``format=`` always wins (and
    is validated against the catalog). Otherwise detection reads a header prefix and
    resolves the format from its content signature, falling back to the file extension.
    Raises :class:`~orbit_formats.errors.UnknownFormatError` if nothing matches and
    :class:`~orbit_formats.errors.AmbiguousFormatError` if several signatures tie.
    """
    if format is not None:
        return _normalize_explicit(format)
    return detect_source(load_source(source, limit=DETECT_PREFIX_BYTES))


def detect_source(src: Source, *, format: str | None = None) -> str:
    """Detect the format of an already-loaded :class:`Source` (the internal entry point)."""
    if format is not None:
        return _normalize_explicit(format)
    return _detect(src.data, src.suffix, src.name)


def _normalize_explicit(format: str) -> str:
    normalized = format.strip().lower()
    if not is_known_format(normalized):
        raise UnknownFormatError(
            f"unknown format {format!r}; known formats: {', '.join(known_format_ids())}"
        )
    return normalized


def _detect(data: bytes, suffix: str | None, name: str | None) -> str:
    # Binary magic first, before attempting any text decode.
    binary_match = match_binary(data)
    if binary_match is not None:
        return binary_match

    text = _decode(data)
    if text is not None:
        scored = score_text_formats(data, text)
        if scored:
            top = max(confidence for _, confidence in scored)
            winners = [fid for fid, confidence in scored if confidence == top]
            if len(winners) == 1:
                return winners[0]
            # A tie falls to the extension, then to a typed ambiguity error.
            from_extension = extension_format(suffix)
            if from_extension in winners:
                return from_extension
            raise AmbiguousFormatError(winners)

    # No content signature matched: a signature-less format named by extension (e.g. the
    # GMAT report), or text whose format we cannot sniff.
    from_extension = extension_format(suffix)
    if from_extension is not None:
        return from_extension

    raise UnknownFormatError(_unknown_message(name, text is None))


def _decode(data: bytes) -> str | None:
    """Decode a content prefix as text, or ``None`` if it looks binary."""
    if b"\x00" in data[:1024]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _unknown_message(name: str | None, binary: bool) -> str:
    what = repr(name) if name is not None else "the input"
    kind = "binary content" if binary else "content"
    return (
        f"could not detect the format of {what}: its {kind} matched no known signature "
        "and its extension is unrecognised. Pass an explicit format= to override."
    )
