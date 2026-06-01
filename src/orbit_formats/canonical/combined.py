"""``Combined`` — an ordered collection of canonical messages (CCSDS combined NDM).

Where every other category type describes a *single* navigation product, a ``Combined``
holds *several*: the children of a combined NDM — the ``<ndm>`` XML wrapper (and its de-facto
KVN concatenation) that carries an OPM plus a CDM, several OEMs, or any mix of the individual
messages in one file. It is what :func:`~orbit_formats.read` returns when it detects an
aggregate, so a multi-message read stays uniform with a single-message one (both return a
:class:`~orbit_formats.canonical.base.Canonical`) and :func:`~orbit_formats.write` round-trips
it back.

The aggregate is a *container*, not a navigation record of its own: it carries no orbit state,
so the metadata spine names only its provenance (``source_format="ccsds-ndm"``). The wrapper's
own content — the optional ``MESSAGE_ID`` and the wrapper-level comments — sits in the
``message_id`` / ``comments`` fields; each child keeps its full identity, payload, and
``source_native`` fidelity model, so a child pulled out of a ``Combined`` is exactly the object
reading that message alone would yield. The NDM message type each child serialises back to is
taken from its own ``source_native`` (e.g. an ``Ephemeris`` whose native is an
``ccsds-oem`` model writes as an ``<oem>``), so the children must be objects read from — or
otherwise tagged with — an NDM message.

CCSDS standardises the combined instantiation only in NDM/XML; the KVN form is the individual
KVN messages concatenated. The wrapper ``MESSAGE_ID`` has no KVN home, so a KVN write reports
it as a loss. The conversion graph does not route an aggregate (there is no single form to
convert it to or from); :func:`~orbit_formats.convert` raises on one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orbit_formats.canonical.base import Canonical

__all__ = ["Combined"]


@dataclass(kw_only=True, eq=False)
class Combined(Canonical):
    """A combined NDM: an ordered tuple of child canonical messages plus the wrapper header.

    ``messages`` is the children in document order (within a message type; the XML wrapper
    groups children by type, so a mixed aggregate is normalised to that grouping on write).
    ``message_id`` and ``comments`` are the wrapper-level ``MESSAGE_ID`` and comments. Each
    child carries its own metadata and ``source_native``; the aggregate's metadata spine names
    only the provenance. Equality is by wrapper header plus the child sequence (each compared by
    its own canonical content), ignoring ``source_native`` like every other category type.
    """

    messages: tuple[Canonical, ...]
    message_id: str | None = None
    comments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # Accept any iterable of children but pin the stored value to a tuple, so equality and
        # ordering are stable and the container cannot be mutated after construction.
        self.messages = tuple(self.messages)
        self.comments = tuple(self.comments)

    def __len__(self) -> int:
        """The number of child messages."""
        return len(self.messages)

    def _eq_payload(self) -> tuple[Any, ...]:
        return (self.message_id, self.comments, self.messages)
