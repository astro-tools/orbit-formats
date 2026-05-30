"""The adapter protocol — the typed fidelity-model ↔ canonical-metamodel contract.

A reader produces a format-fidelity model, then an adapter's :meth:`Adapter.to_canonical`
maps it into the federated canonical metamodel; a writer takes a canonical object and an
adapter's :meth:`Adapter.from_canonical` maps it back to the format's fidelity model.
Keeping this step explicit is what lets same-format round-trips stay byte-lossless (via
``source_native``) while cross-format conversion routes through the canonical metamodel
and warns on every field a target cannot hold.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.fidelity import FidelityModel

__all__ = ["Adapter"]

F = TypeVar("F", bound=FidelityModel)
C = TypeVar("C", bound=Canonical)


class Adapter(Protocol[F, C]):
    """Maps one format's fidelity model to and from the canonical metamodel.

    Generic over the format's fidelity model ``F`` and the canonical category type ``C``
    it adapts to. Implementations live next to their reader/writer; this protocol is the
    structural contract the public surface registers them against.
    """

    def to_canonical(self, fidelity: F) -> C:
        """Map a parsed fidelity model into its canonical metamodel object."""
        ...

    def from_canonical(self, canonical: C) -> F:
        """Map a canonical object back to this format's fidelity model."""
        ...
