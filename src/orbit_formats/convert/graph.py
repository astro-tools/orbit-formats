"""The conversion graph — routing a canonical object toward a target's preferred form and frame.

Each format declares its preferred canonical form; the graph routes a conversion through
those forms rather than enumerating every format pair. A **same-form** conversion needs no
transform — the object is already in the form the target wants, and a later same-format
write recovers full fidelity from its ``source_native`` handle, so the round-trip stays
byte-lossless. A **cross-form** conversion runs a registered edge from ``_TRANSFORMS``: the
propagator-free single <-> series bridges (a single state embeds as a length-1 ephemeris; an
ephemeris collapses to the state at its first epoch). Cross-form pairs that would need a model
step (a propagation or an orbit fit) register no edge, so :func:`route` returns ``None`` and the
caller reports the conversion as unsupported.

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
from orbit_formats.errors import FrameRotationUnsupportedError, UnsupportedConversionError
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy

__all__ = ["apply_frame", "conversion_edges", "route"]

# Cross-form transforms keyed by (source_form, target_form), populated at the bottom of the
# module once the edge functions are defined. The propagator-free single <-> series bridges
# live here — embedding a single state as a length-1 ephemeris, and collapsing an ephemeris to
# the state at its first epoch — and :func:`route` picks them up. Cross-form conversions that
# would need a model step (a mean-element set to a state or series, or the reverse) register no
# edge and fall through to the unsupported path.
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
            # The maneuvers name their own reference frame and are not rotated (that would be
            # maneuver modelling, out of scope); they ride along verbatim.
            maneuvers=obj.maneuvers,
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
            maneuvers=obj.maneuvers,  # the burns name their own frame; carried verbatim
            source_native=None,
        )
    # A form with no Cartesian state to rotate (mean elements would need a propagation).
    raise FrameRotationUnsupportedError(source_id, target_id)


def _state_to_ephemeris(obj: Canonical) -> Canonical:
    """Embed a single :class:`StateVector` as a length-1 :class:`Ephemeris` (lossless).

    The one Cartesian state becomes the single sample of an ephemeris in the same frame and
    units; a single point carries no interpolation hint, and ``source_native`` is dropped
    because the source bytes describe a state message, not an ephemeris series. The Keplerian
    cache (if any) is a derived view of the same position and velocity, so nothing is lost and
    the embedding emits no warning.
    """
    assert isinstance(obj, StateVector)  # route() dispatches here only for the state form
    return Ephemeris(
        metadata=obj.metadata,
        epochs=np.array([obj.epoch], dtype="datetime64[ns]"),
        positions=obj.position[None, :],
        velocities=obj.velocity[None, :],
        interpolation=None,
        interpolation_degree=None,
        maneuvers=obj.maneuvers,  # the burns belong to the body; carried across the embedding
        source_native=None,
    )


def _ephemeris_to_state(obj: Canonical) -> Canonical:
    """Collapse an :class:`Ephemeris` to a single :class:`StateVector` at its first epoch.

    Lossless when the ephemeris holds exactly one sample; for a longer series it keeps the
    first state and reports the dropped later epochs (and any interpolation hint) through
    :func:`~orbit_formats.warnings.warn_lossy`, so the collapse is never a silent loss. An
    empty ephemeris has no state to take and raises
    :class:`~orbit_formats.errors.UnsupportedConversionError`. ``source_native`` is dropped:
    the source bytes describe a series, not a single state.
    """
    assert isinstance(obj, Ephemeris)  # route() dispatches here only for the ephemeris form
    count = len(obj)
    if count == 0:
        raise UnsupportedConversionError("empty ephemeris", "state", "state")
    if count > 1:
        dropped = [
            DroppedField(
                "epochs",
                f"an ephemeris of {count} states collapses to a single state; kept the first "
                f"epoch and dropped the other {count - 1}",
            )
        ]
        if obj.interpolation is not None:
            dropped.append(
                DroppedField("interpolation", "a single state carries no interpolation hint")
            )
        warn_lossy(
            LossyConversionWarning(
                f"collapsed an ephemeris of {count} states to the state at its first epoch",
                dropped=tuple(dropped),
            ),
            stacklevel=2,
        )
    return StateVector(
        metadata=obj.metadata,
        epoch=obj.epochs[0],
        position=obj.positions[0],
        velocity=obj.velocities[0],
        keplerian=None,
        maneuvers=obj.maneuvers,  # the burns belong to the body; carried across the collapse
        source_native=None,
    )


# The propagator-free single <-> series bridges (see the _TRANSFORMS comment above).
_TRANSFORMS[("state", "ephemeris")] = _state_to_ephemeris
_TRANSFORMS[("ephemeris", "state")] = _ephemeris_to_state


def conversion_edges() -> frozenset[tuple[str, str]]:
    """The registered cross-form ``(source_form, target_form)`` edges.

    The single source of truth for which form pairs a transform bridges, so capability
    introspection (:mod:`orbit_formats.convert.capabilities`) reports exactly what
    :func:`route` will act on rather than a hand-maintained copy.
    """
    return frozenset(_TRANSFORMS)
