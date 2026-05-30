"""The format-fidelity layer — one faithful model per format, every field it defines.

Same-format round-trips (OEM to OEM) stay at this layer and are byte-lossless: a
fidelity model never down-projects. An adapter maps a fidelity model to and from the
canonical metamodel; a canonical object holds an optional ``source_native`` handle back
to the fidelity model it came from.
"""

from __future__ import annotations

from abc import ABC
from typing import ClassVar

__all__ = ["FidelityModel"]


class FidelityModel(ABC):
    """Base for a one-faithful-model-per-format representation.

    A fidelity model holds *every* field a format defines, so a same-format write can
    recover full fidelity from it and stay byte-lossless — it never down-projects.
    Per-format models (the in-house KVN OEM record, the thin sgp4 element set, the GMAT
    report table) live in their reader modules; this base only fixes the contract that
    every model declares the ``format_name`` the lossy-conversion and writer layers key
    their same-format-lossless logic off.
    """

    #: The canonical format id this model is faithful to (e.g. ``"ccsds-oem"``,
    #: ``"tle"``, ``"gmat-report"``). Every concrete subclass must declare it.
    format_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "format_name"):
            raise TypeError(
                f"{cls.__name__} must declare a class-level 'format_name' before it can "
                "represent a format"
            )
