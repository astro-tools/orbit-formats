"""The conversion graph — routing a canonical object toward a target's preferred form and frame.

Each format declares its preferred canonical form; the graph routes a conversion through
those forms rather than enumerating every format pair. A **same-form** conversion needs no
transform — the object is already in the form the target wants, and a later same-format
write recovers full fidelity from its ``source_native`` handle, so the round-trip stays
byte-lossless.

Orthogonal to the form is the **reference frame**. :func:`apply_frame` resolves a requested
target frame: it leaves the object untouched when no frame is requested or it is already in
that frame (so the byte-lossless ``source_native`` path survives), rotates the Cartesian
state when a supported rotation is needed (:mod:`orbit_formats.convert.frames`, astropy
internally), and raises a typed error only for a genuinely unsupported pair. The element
edge (Cartesian <-> Keplerian) and the time-scale edge live in sibling modules
(:mod:`orbit_formats.convert.elements`, :mod:`orbit_formats.convert.time`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import numpy as np

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.state import StateVector
from orbit_formats.convert import frames
from orbit_formats.errors import FrameRotationUnsupportedError

__all__ = ["apply_frame", "route"]

# Cross-form transforms keyed by (source_form, target_form). Empty for now — propagator-free
# cross-form edges register here as they land, and :func:`route` picks them up unchanged.
_TRANSFORMS: dict[tuple[str, str], Callable[[Canonical], Canonical]] = {}


def route(
    obj: Canonical, source_form: str, target_form: str, target_frame: str | None = None
) -> Canonical | None:
    """Route ``obj`` (in ``source_form``) toward ``target_form`` and, if given, ``target_frame``.

    Resolves the reference frame first (:func:`apply_frame` — a no-op unless a rotation is
    actually required), then the form: returns the frame-resolved object unchanged when it is
    already in the target form — the same-form pass-through that keeps a subsequent
    same-format write byte-lossless via ``source_native`` when no rotation happened. Returns
    the transformed object when a cross-form edge exists, or ``None`` when no route does,
    leaving the caller to report the conversion as unsupported (it owns the target format id
    the error needs). A genuinely unsupported frame rotation raises
    :class:`~orbit_formats.errors.FrameRotationUnsupportedError`.
    """
    obj = apply_frame(obj, target_frame)
    if source_form == target_form:
        return obj
    transform = _TRANSFORMS.get((source_form, target_form))
    if transform is None:
        return None
    return transform(obj)


def apply_frame(obj: Canonical, target_frame: str | None) -> Canonical:
    """Resolve ``obj`` into ``target_frame``, rotating its Cartesian state when needed.

    Returns ``obj`` unchanged when no frame is requested (``target_frame is None``) or it is
    already in that frame (case-insensitively, J2000 / EME2000 treated as one) — preserving
    the byte-lossless ``source_native`` handle. When both frames are known and differ, rotates
    the state (:func:`orbit_formats.convert.frames.rotate_state`) and returns a **new** object
    tagged with the target frame and with ``source_native`` dropped, since the original bytes
    no longer describe the rotated state. Raises
    :class:`~orbit_formats.errors.FrameRotationUnsupportedError` for a genuinely unsupported
    pair — an unknown frame on either side, or a form with no Cartesian state to rotate.
    """
    if target_frame is None:
        return obj
    source_frame = obj.metadata.reference_frame
    source_id = None if source_frame is None else frames.normalize_frame(source_frame)
    target_id = frames.normalize_frame(target_frame)
    if source_id is not None and target_id is not None and source_id == target_id:
        return obj  # already in the requested frame — no rotation, source_native preserved
    if source_id is None or target_id is None:
        raise FrameRotationUnsupportedError(source_frame or "<unknown>", target_frame)
    return _rotate(obj, source_id, target_id)


def _rotate(obj: Canonical, source_id: str, target_id: str) -> Canonical:
    """Rotate a Cartesian canonical object from ``source_id`` to ``target_id`` (both known)."""
    time_scale = obj.metadata.time_scale
    if time_scale is None:
        raise ValueError(
            "a frame rotation needs the epoch time scale, but metadata.time_scale is None"
        )
    metadata = replace(obj.metadata, reference_frame=target_id)
    if isinstance(obj, Ephemeris):
        positions, velocities = frames.rotate_state(
            obj.positions,
            obj.velocities,
            obj.epochs,
            time_scale=time_scale,
            from_frame=source_id,
            to_frame=target_id,
        )
        return Ephemeris(
            metadata=metadata,
            epochs=obj.epochs,
            positions=positions,
            velocities=velocities,
            interpolation=obj.interpolation,
            interpolation_degree=obj.interpolation_degree,
            source_native=None,
        )
    if isinstance(obj, StateVector):
        epochs = np.array([obj.epoch], dtype="datetime64[ns]")
        positions, velocities = frames.rotate_state(
            obj.position[None, :],
            obj.velocity[None, :],
            epochs,
            time_scale=time_scale,
            from_frame=source_id,
            to_frame=target_id,
        )
        return StateVector(
            metadata=metadata,
            epoch=obj.epoch,
            position=positions[0],
            velocity=velocities[0],
            keplerian=None,  # the cached Keplerian set was frame-relative; drop it
            source_native=None,
        )
    # A form with no Cartesian state to rotate (mean elements would need a propagation).
    raise FrameRotationUnsupportedError(source_id, target_id)
