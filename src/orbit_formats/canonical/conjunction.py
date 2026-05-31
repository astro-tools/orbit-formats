"""``Conjunction`` — a conjunction record (CCSDS CDM). Not yet implemented.

Declared now so the canonical package layout matches the charter's federated family,
alongside the implemented :class:`~orbit_formats.canonical.ephemeris.Ephemeris`,
:class:`~orbit_formats.canonical.state.StateVector`, and
:class:`~orbit_formats.canonical.elements.MeanElementSet`.
"""

from __future__ import annotations

__all__ = ["Conjunction"]


class Conjunction:
    """Conjunction data message category — not yet implemented."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("the Conjunction category is not yet implemented")
