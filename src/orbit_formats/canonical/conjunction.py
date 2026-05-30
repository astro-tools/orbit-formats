"""``Conjunction`` — a conjunction record (CCSDS CDM). Reserved for v0.2.

Declared now so the canonical package layout matches the charter's federated family; the
v0.1 milestone ships :class:`~orbit_formats.canonical.ephemeris.Ephemeris`,
:class:`~orbit_formats.canonical.state.StateVector`, and
:class:`~orbit_formats.canonical.elements.MeanElementSet` only.
"""

from __future__ import annotations

__all__ = ["Conjunction"]


class Conjunction:
    """Conjunction data message category — lands in orbit-formats v0.2."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Conjunction lands in orbit-formats v0.2")
