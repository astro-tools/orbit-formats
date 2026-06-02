"""SPK writer — byte-lossless (opt-in), content-lossless, and synthesised paths.

Behind the optional ``[spk]`` extra (``spiceypy``). Mirrors the OEM / STK writers' three tiers,
picked automatically from what the canonical object carries:

1. An ``Ephemeris`` whose ``source_native`` is an
   :class:`~orbit_formats.readers.spk.SpkFile` **with retained bytes** (read with
   ``retain_source=True``) → the verbatim kernel bytes are echoed: the same-format round trip
   is **byte-identical** by construction.
2. An ``Ephemeris`` with an ``SpkFile`` ``source_native`` **without** retained bytes → every
   stored segment is re-emitted via ``spiceypy`` from the faithful node set: **content-
   lossless** (the exact state nodes, epochs, bodies, frame, and segment type preserved).
3. Any other ``Ephemeris`` (synthesised or cross-format, no SPK ``source_native``) → a single
   type-9 segment is built from the canonical fields, warning (via the lossy-warning framework)
   for each SPK-required field the canonical form cannot supply.

SPK has a single binary encoding, so the destination extension only selects the format; the
``suffix`` argument is accepted (for the writer protocol) and ignored. ``spiceypy`` writes a
kernel to a file, so the writer serialises to a temporary kernel and returns its bytes.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from orbit_formats._spice import datetime64_to_et, require_spiceypy
from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.convert.time import convert_time_scale
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.spk import SpkFile, SpkSegment
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy

__all__ = ["write_spk"]

# A synthesised segment's defaults, written only when the canonical form cannot supply the real
# value — and every such fallback is reported through the lossy-warning framework, never a
# silent default. A spacecraft-style NAIF id for the target, Earth (399) as the centre, and the
# J2000 inertial frame.
_DEFAULT_BODY_ID = -999
_DEFAULT_CENTER_ID = 399
_DEFAULT_FRAME = "J2000"
# The Lagrange degree a synthesised segment declares, capped to the node count (a degree-d
# Lagrange segment needs d+1 nodes).
_DEFAULT_DEGREE = 7
_SYNTHESISED_SEGMENT_ID = "orbit-formats synthesised SPK segment"
_INTERNAL_FILE_NAME = "orbit-formats SPK"

# Canonical inertial-frame labels SPICE does not know by name but which are, to the precision an
# SPK records, the J2000 inertial frame: EME2000 is J2000 exactly; ICRF / GCRF differ only at
# the milliarcsecond bias level, below SPK's labelling resolution.
_FRAME_ALIASES = {"J2000": "J2000", "EME2000": "J2000", "ICRF": "J2000", "GCRF": "J2000"}


def write_spk(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (an :class:`Ephemeris`) to SPK (``.bsp``) bytes.

    Requires the ``[spk]`` extra (``spiceypy``); without it raises
    :class:`~orbit_formats.errors.MissingOptionalDependencyError`. Picks the byte-identical,
    content-lossless, or synthesised path automatically — see the module docstring. ``suffix``
    (the destination extension) is ignored: SPK has a single binary encoding. Raises
    :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not an
    ``Ephemeris`` — SPK is an ephemeris format, and converting another canonical form to it is
    the conversion layer's job, not the writer's.
    """
    if not isinstance(obj, Ephemeris):
        raise UnsupportedConversionError(type(obj).__name__, "spk", "ephemeris")
    spice = require_spiceypy()
    native = obj.source_native
    if isinstance(native, SpkFile):
        if native.raw_bytes is not None:
            return native.raw_bytes
        return _serialize(spice, native.segments)
    return _serialize(spice, (_segment_from_ephemeris(spice, obj),))


def _serialize(spice: Any, segments: tuple[SpkSegment, ...]) -> bytes:
    """Write ``segments`` to a temporary SPK kernel via spiceypy and return its bytes."""
    workdir = tempfile.mkdtemp(prefix="orbit_formats_spk_")
    path = os.path.join(workdir, "out.bsp")
    handle: int | None = None
    try:
        handle = int(spice.spkopn(path, _INTERNAL_FILE_NAME, 0))
        for segment in segments:
            _write_segment(spice, handle, segment)
        spice.spkcls(handle)
        handle = None
        return Path(path).read_bytes()
    finally:
        if handle is not None:
            # An error left the kernel open and SPICE in an error state: close and reset so a
            # later call is not blocked, then let the original exception propagate.
            _close_spk(spice, handle)
            spice.reset()
        shutil.rmtree(workdir, ignore_errors=True)


def _write_segment(spice: Any, handle: int, segment: SpkSegment) -> None:
    epochs = segment.epochs_et.astype(np.float64)
    states = segment.states.astype(np.float64)
    n = int(epochs.shape[0])
    write = spice.spkw13 if segment.segment_type == 13 else spice.spkw09
    write(
        handle,
        segment.body_id,
        segment.center_id,
        segment.frame,
        float(epochs[0]),
        float(epochs[-1]),
        segment.segment_id,
        segment.degree,
        n,
        states.tolist(),
        epochs.tolist(),
    )


def _segment_from_ephemeris(spice: Any, eph: Ephemeris) -> SpkSegment:
    """Build a type-9 :class:`SpkSegment` from a canonical ``Ephemeris``, warning on gaps.

    Each SPK-required field the canonical form cannot supply — the target / centre NAIF ids, a
    SPICE-representable frame, the time scale — is filled with a placeholder and reported
    through :func:`~orbit_formats.warnings.warn_lossy`, so a synthesised SPK is structurally
    valid yet never silently incomplete.
    """
    n = len(eph)
    if n < 2:
        # An SPK segment is an interpolatable trajectory (a Lagrange segment needs at least two
        # nodes); a single state — e.g. one embedded from an OPM — is not a trajectory and cannot
        # be expressed as SPK. Refuse with a typed error rather than letting SPICE raise.
        raise UnsupportedConversionError(f"{n}-state ephemeris", "spk", "ephemeris of >= 2 states")
    body_id = _resolve_body(spice, eph.metadata.object_name, "object_name", _DEFAULT_BODY_ID)
    center_id = _resolve_body(spice, eph.metadata.central_body, "central_body", _DEFAULT_CENTER_ID)
    frame = _resolve_frame(spice, eph.metadata.reference_frame)
    epochs_et = _epochs_to_et(eph)
    states = np.hstack([eph.positions, eph.velocities]).astype(np.float64)
    degree = max(1, min(_DEFAULT_DEGREE, n - 1)) if n > 1 else 1
    return SpkSegment(
        body_id=body_id,
        body_name=eph.metadata.object_name or str(body_id),
        center_id=center_id,
        center_name=eph.metadata.central_body or str(center_id),
        frame=frame,
        frame_id=0,
        segment_type=9,
        degree=degree,
        segment_id=_SYNTHESISED_SEGMENT_ID,
        epochs_et=epochs_et,
        states=states,
    )


def _epochs_to_et(eph: Ephemeris) -> NDArray[np.float64]:
    """The ephemeris epochs as ET — converted to TDB from their declared scale, then to ET."""
    scale = eph.metadata.time_scale
    epochs = eph.epochs
    if scale is None:
        _warn_missing("time_scale", "the canonical ephemeris did not carry it; assumed TDB")
    elif scale != "TDB":
        epochs = convert_time_scale(epochs, scale, "TDB")
    return datetime64_to_et(epochs)


def _resolve_body(spice: Any, name: str | None, field: str, default: int) -> int:
    """The NAIF id for ``name``, or the placeholder ``default`` (warned) when it cannot resolve."""
    from spiceypy.utils.exceptions import NotFoundError

    if name is not None:
        try:
            return int(spice.bods2c(name))
        except NotFoundError:
            _warn_missing(
                field, f"SPICE has no NAIF id for {name!r}; wrote the placeholder {default}"
            )
            return default
    _warn_missing(
        field, f"the canonical ephemeris did not carry it; wrote the placeholder {default}"
    )
    return default


def _resolve_frame(spice: Any, name: str | None) -> str:
    """A SPICE-representable frame name for ``name``, or the default ``J2000`` (warned)."""
    if name is None:
        _warn_missing(
            "reference_frame", f"the canonical ephemeris did not carry it; wrote {_DEFAULT_FRAME}"
        )
        return _DEFAULT_FRAME
    candidate = _FRAME_ALIASES.get(name.upper(), name)
    if int(spice.namfrm(candidate)) != 0:
        return candidate
    _warn_missing(
        "reference_frame", f"SPICE cannot represent the frame {name!r}; wrote {_DEFAULT_FRAME}"
    )
    return _DEFAULT_FRAME


def _warn_missing(field: str, reason: str) -> None:
    warn_lossy(
        LossyConversionWarning(
            f"the ephemeris does not supply the SPK-required {field}; {reason}",
            dropped=(DroppedField(field, reason),),
        ),
        stacklevel=4,
    )


def _close_spk(spice: Any, handle: int) -> None:
    # Best-effort cleanup on an already-failing write; reset SPICE so a later call is clean.
    try:
        spice.spkcls(handle)
    except Exception:
        spice.reset()


register_writer("spk", write_spk)
