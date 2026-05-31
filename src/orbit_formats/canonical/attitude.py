"""``Attitude`` — attitude history / parameters (CCSDS AEM / APM). Not yet implemented.

Declared now so the canonical package layout matches the charter's federated family,
alongside the implemented :class:`~orbit_formats.canonical.ephemeris.Ephemeris`,
:class:`~orbit_formats.canonical.state.StateVector`, and
:class:`~orbit_formats.canonical.elements.MeanElementSet`.
"""

from __future__ import annotations

__all__ = ["Attitude"]


class Attitude:
    """Attitude ephemeris / parameters category — not yet implemented."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("the Attitude category is not yet implemented")
