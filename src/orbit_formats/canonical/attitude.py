"""``Attitude`` — attitude history / parameters (CCSDS AEM / APM). Reserved for v0.2.

Declared now so the canonical package layout matches the charter's federated family; the
v0.1 milestone ships :class:`~orbit_formats.canonical.ephemeris.Ephemeris`,
:class:`~orbit_formats.canonical.state.StateVector`, and
:class:`~orbit_formats.canonical.elements.MeanElementSet` only.
"""

from __future__ import annotations

__all__ = ["Attitude"]


class Attitude:
    """Attitude ephemeris / parameters category — lands in orbit-formats v0.2."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Attitude lands in orbit-formats v0.2")
