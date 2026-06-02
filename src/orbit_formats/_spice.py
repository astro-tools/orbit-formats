"""Lazy SPICE (``spiceypy``) access for the optional ``[spk]`` extra, plus shared SPK helpers.

``spiceypy`` is an *optional* dependency: the SPK reader and writer live behind the ``[spk]``
extra so the heavy SPICE kernel path stays out of the base install. Neither the reader nor
the writer imports ``spiceypy`` at module load — they call :func:`require_spiceypy` inside
their functions, so ``import orbit_formats`` (and the minimal base install) never needs it.
When the extra is absent, :func:`require_spiceypy` raises the typed
:class:`~orbit_formats.errors.MissingOptionalDependencyError` pointing at
``pip install orbit-formats[spk]``.

SPK epochs are ephemeris time (ET) — TDB seconds past the J2000 epoch. The conversions here
stay in TDB by pure arithmetic against :data:`J2000_TDB`, so reading and writing the sampled
nodes needs no leapsecond / PCK kernel and never touches the SPICE kernel pool.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import numpy as np
from numpy.typing import NDArray

from orbit_formats.errors import MalformedSourceError, MissingOptionalDependencyError

__all__ = [
    "J2000_TDB",
    "datetime64_to_et",
    "et_to_datetime64",
    "require_spiceypy",
    "spice_read_guard",
]

# The J2000 epoch — 2000-01-01 12:00:00 TDB — the origin SPK ephemeris time (ET) counts
# seconds from. SPK epochs are TDB, so the canonical Ephemeris an SPK maps to is tagged TDB.
J2000_TDB = np.datetime64("2000-01-01T12:00:00", "ns")
_NS_PER_SECOND = 1_000_000_000


def require_spiceypy() -> Any:
    """Import and return ``spiceypy``, or raise the typed missing-extra error.

    The SPK reader / writer call this lazily so the base install never imports ``spiceypy``.
    Raises :class:`~orbit_formats.errors.MissingOptionalDependencyError` (naming the ``[spk]``
    extra) when ``spiceypy`` is not installed.
    """
    try:
        import spiceypy
    except ImportError as exc:
        raise MissingOptionalDependencyError("spiceypy", extra="spk") from exc
    return spiceypy


def et_to_datetime64(et: NDArray[np.float64]) -> NDArray[np.datetime64]:
    """Convert ET (TDB seconds past J2000) to ``datetime64[ns]`` on the TDB scale."""
    nanoseconds = np.rint(np.asarray(et, dtype=np.float64) * _NS_PER_SECOND).astype("int64")
    return (J2000_TDB + nanoseconds.astype("timedelta64[ns]")).astype("datetime64[ns]")


def datetime64_to_et(epochs: NDArray[np.datetime64]) -> NDArray[np.float64]:
    """Convert ``datetime64[ns]`` (already on the TDB scale) to ET seconds past J2000."""
    deltas = np.asarray(epochs, dtype="datetime64[ns]") - J2000_TDB
    return (deltas / np.timedelta64(1, "s")).astype(np.float64)


@contextmanager
def spice_read_guard(spice: Any, what: str) -> Iterator[None]:
    """Translate a SPICE-level failure inside the block into :class:`MalformedSourceError`.

    ``spiceypy`` raises a ``SpiceyError`` on a SPICE toolkit failure — a file that is not a
    DAF, a corrupt segment. Those mean "the format is settled, the content is broken", so we
    re-raise them as :class:`~orbit_formats.errors.MalformedSourceError` and call
    ``spice.reset()`` so the lingering SPICE error state does not block a later call. Errors
    we raise ourselves (a :class:`MalformedSourceError` for an unsupported segment type) are
    not ``SpiceyError`` and propagate unchanged.
    """
    from spiceypy.utils.exceptions import SpiceyError

    try:
        yield
    except SpiceyError as exc:
        spice.reset()
        raise MalformedSourceError(f"{what}: {exc}") from exc
