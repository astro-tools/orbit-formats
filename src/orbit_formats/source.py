"""Resolve a read/detect input into raw bytes plus optional origin metadata.

The public entry points accept either a path (``str`` / :class:`os.PathLike`) or an
in-memory buffer (``bytes`` / a file-like object). :func:`load_source` collapses those
into one :class:`Source` — the raw bytes plus, when known, the originating path and a
display name — so detection and the readers work against a single uniform input. A
:class:`Source` is also the contract a registered reader consumes: it can pull the raw
bytes, the decoded text, or (for kernel-backed formats) the path the bytes came from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import IO

__all__ = ["Source", "SourceInput", "load_source"]

# What the public read/detect surface accepts: a filesystem path or an in-memory buffer.
SourceInput = str | bytes | bytearray | os.PathLike[str] | IO[bytes] | IO[str]


@dataclass(frozen=True, slots=True)
class Source:
    """A resolved input: raw bytes, plus the origin path/name when one was given.

    ``data`` is the (possibly prefix-truncated, for detection) raw content. ``path`` is
    set only when the input was a filesystem path; ``name`` is a display name used for
    extension hints and error messages. Readers consume a ``Source`` rather than a raw
    path so the same reader works for a file and an in-memory buffer.

    ``retain`` is the caller's opt-in (via :func:`~orbit_formats.read`'s
    ``retain_source``) to keep the raw bytes on the fidelity model for a verbatim,
    byte-identical same-format re-emit. It defaults to ``False`` so an ordinary read holds
    no extra copy; a reader that supports verbatim retention (e.g. the OEM reader) consults
    this flag to decide whether to stash the source bytes.
    """

    data: bytes
    path: Path | None = None
    name: str | None = None
    retain: bool = False

    @property
    def suffix(self) -> str | None:
        """The lowercased file extension (with leading dot), or ``None`` if unknown."""
        ref: str | None = None
        if self.path is not None:
            ref = self.path.name
        elif self.name is not None:
            ref = self.name
        if ref is None:
            return None
        return PurePath(ref).suffix.lower() or None

    def read_bytes(self) -> bytes:
        """Return the raw bytes."""
        return self.data

    def read_text(self, encoding: str = "utf-8") -> str:
        """Decode the raw bytes as text (UTF-8 by default)."""
        return self.data.decode(encoding)


def load_source(source: SourceInput, *, limit: int | None = None, retain: bool = False) -> Source:
    """Resolve ``source`` to a :class:`Source`.

    A ``str`` or :class:`os.PathLike` is read from disk; ``bytes`` / ``bytearray`` are
    taken as the content directly; a file-like object is read (and encoded to UTF-8 if it
    yields ``str``). ``limit``, when set, caps how many bytes are loaded — used so a
    detection-only pass over a large file reads just a prefix rather than the whole thing.
    ``retain`` is recorded on the result so a reader can choose to keep the raw bytes for a
    verbatim re-emit (see :class:`Source`); it is never set on a prefix-limited load.
    """
    if isinstance(source, (bytes, bytearray)):
        return Source(data=_truncate(bytes(source), limit), retain=retain)
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        with path.open("rb") as handle:
            data = handle.read() if limit is None else handle.read(limit)
        return Source(data=data, path=path, name=path.name, retain=retain)
    reader = getattr(source, "read", None)
    if callable(reader):
        raw = reader() if limit is None else reader(limit)
        data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        name = getattr(source, "name", None)
        return Source(data=data, name=name if isinstance(name, str) else None, retain=retain)
    raise TypeError(f"unsupported source type: {type(source).__name__!r}")


def _truncate(data: bytes, limit: int | None) -> bytes:
    return data if limit is None else data[:limit]
