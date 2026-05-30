"""The conversion graph — routing a canonical object toward a target's preferred form.

Each format declares its preferred canonical form; the graph routes a conversion through
those forms rather than enumerating every format pair. A **same-form** conversion needs no
transform — the object is already in the form the target wants, and a later same-format
write recovers full fidelity from its ``source_native`` handle, so the round-trip stays
byte-lossless.

For v0.1 the cross-form edge table is empty: every cross-form conversion among the
readable formats either needs a propagator (a mean-element set to a state — the caller's
job) or a format that does not exist yet, so the full conversion matrix is deferred. The
element edge (Cartesian <-> Keplerian) and the time-scale edge live in sibling modules
(:mod:`orbit_formats.convert.elements`, :mod:`orbit_formats.convert.time`); this module
holds the routing decision and the frame guard.
"""

from __future__ import annotations

from collections.abc import Callable

from orbit_formats.canonical.base import Canonical
from orbit_formats.errors import FrameRotationUnsupportedError

__all__ = ["require_same_frame", "route"]

# Cross-form transforms keyed by (source_form, target_form). Empty in v0.1 — see the
# module docstring. As propagator-free cross-form edges land they register here, and
# :func:`route` picks them up with no change to its callers.
_TRANSFORMS: dict[tuple[str, str], Callable[[Canonical], Canonical]] = {}


def route(obj: Canonical, source_form: str, target_form: str) -> Canonical | None:
    """Route ``obj`` (in ``source_form``) toward ``target_form``.

    Returns the object unchanged when it is already in the target form — the same-form
    pass-through that keeps a subsequent same-format write byte-lossless via
    ``source_native``. Returns the transformed object when a cross-form edge exists, or
    ``None`` when no route does, leaving the caller to report the conversion as
    unsupported (it owns the target format id the error needs).
    """
    if source_form == target_form:
        return obj
    transform = _TRANSFORMS.get((source_form, target_form))
    if transform is None:
        return None
    return transform(obj)


def require_same_frame(source_frame: str | None, target_frame: str | None) -> None:
    """Guard a conversion against an unsupported cross-frame rotation.

    v0.1 only tags and preserves reference frames; rotating between two distinct named
    frames is deferred. When both frames are known and differ (case-insensitively), this
    raises :class:`~orbit_formats.errors.FrameRotationUnsupportedError` rather than letting
    a naive, un-rotated state slip through. An unknown frame on either side (``None``) is
    not enough to assert a mismatch, so it passes.
    """
    if source_frame is None or target_frame is None:
        return
    if source_frame.strip().upper() != target_frame.strip().upper():
        raise FrameRotationUnsupportedError(source_frame, target_frame)
