"""The reader/writer registry — where format readers and writers plug into the surface.

The public :func:`~orbit_formats.api.read` / :func:`~orbit_formats.api.write` functions
detect or resolve a format id, then look the matching reader/writer up here. Each format
module registers itself with :func:`register_reader` / :func:`register_writer`; the
registry imports the ``readers`` and ``writers`` packages once, lazily, on first lookup,
so registration is a one-time import side effect and the public surface stays decoupled
from which formats happen to be implemented.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

from orbit_formats.canonical.base import Canonical
from orbit_formats.errors import UnknownFormatError, UnsupportedFormatError
from orbit_formats.formats import is_known_format, is_writable
from orbit_formats.source import Source

__all__ = [
    "Reader",
    "Writer",
    "get_reader",
    "get_writer",
    "register_reader",
    "register_writer",
]

# A reader turns a resolved source into a canonical object; a writer serialises a
# canonical object to the format's bytes. A writer also receives the destination's
# extension (lowercased, with the dot, or ``None`` for a destination-less call) so a format
# with more than one notation — CCSDS OEM in KVN vs XML — can pick from it.
Reader = Callable[[Source], Canonical]
Writer = Callable[[Canonical, "str | None"], bytes]

_READERS: dict[str, Reader] = {}
_WRITERS: dict[str, Writer] = {}
_plugins_loaded = False


def register_reader(format_id: str, reader: Reader) -> None:
    """Register ``reader`` as the reader for ``format_id`` (must be a catalogued format)."""
    if not is_known_format(format_id):
        raise UnknownFormatError(f"cannot register a reader for unknown format {format_id!r}")
    _READERS[format_id] = reader


def register_writer(format_id: str, writer: Writer) -> None:
    """Register ``writer`` for ``format_id`` (must be a catalogued, writable format)."""
    if not is_known_format(format_id):
        raise UnknownFormatError(f"cannot register a writer for unknown format {format_id!r}")
    if not is_writable(format_id):
        raise UnsupportedFormatError(
            f"{format_id!r} is a read-only format; it cannot have a writer"
        )
    _WRITERS[format_id] = writer


def get_reader(format_id: str) -> Reader | None:
    """The registered reader for ``format_id``, or ``None`` if none is registered."""
    _ensure_plugins_loaded()
    return _READERS.get(format_id)


def get_writer(format_id: str) -> Writer | None:
    """The registered writer for ``format_id``, or ``None`` if none is registered."""
    _ensure_plugins_loaded()
    return _WRITERS.get(format_id)


def _ensure_plugins_loaded() -> None:
    """Import the reader/writer packages once so their registrations take effect."""
    global _plugins_loaded
    if _plugins_loaded:
        return
    # Set the flag before importing so a registration done during import does not recurse.
    # The imports run for their side effect: each package imports its format modules,
    # which register themselves against this registry.
    _plugins_loaded = True
    importlib.import_module("orbit_formats.readers")
    importlib.import_module("orbit_formats.writers")
