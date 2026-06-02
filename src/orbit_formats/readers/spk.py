"""SPK reader — NASA SPICE binary kernels (``.bsp`` / ``.spk``) into a canonical Ephemeris.

Behind the optional ``[spk]`` extra (``spiceypy``); the heavy SPICE kernel path stays out of
the base install.

An SPK is a DAF (Double-precision Array File) holding one or more *segments*, each a body's
ephemeris over a time span, in a reference frame, relative to a centre body. This reader
parses the **sampled-state segment types — type 9 (Lagrange, unequal steps) and type 13
(Hermite, unequal steps)** — whose stored data is exactly the state nodes the segment was
built from, so reading recovers them losslessly. The nodes are read straight from the DAF via
``dafgda`` (no interpolation, no kernel pool, no ``furnsh``): each segment's descriptor gives
the centre, body, frame, and data type, and the segment data is ``N`` six-component states
(km, km·s⁻¹) followed by ``N`` epochs (ET = TDB seconds past J2000).

Each segment is held faithfully on an :class:`SpkFile` fidelity model (one :class:`SpkSegment`
per segment); the public :func:`~orbit_formats.read` returns the **first** segment as the
canonical :class:`~orbit_formats.canonical.ephemeris.Ephemeris` (the whole :class:`SpkFile`
rides along as ``source_native``), and :meth:`SpkFile.segment_ephemerides` materialises every
segment's ``Ephemeris``. The canonical frame is the segment's SPICE frame name (``J2000`` …),
the central body the centre's SPICE name (its NAIF id as a string when SPICE has no name for
it), and the time scale **TDB** — SPK ephemeris time is TDB by definition.

Detection is by the ``DAF/SPK`` / ``NAIF/DAF`` binary magic (already catalogued) or the
``.bsp`` / ``.spk`` extension. A file that is not a readable DAF/SPK, or a segment whose type
is not 9 or 13, raises :class:`~orbit_formats.errors.MalformedSourceError`; an absent
``spiceypy`` raises the typed
:class:`~orbit_formats.errors.MissingOptionalDependencyError`.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from orbit_formats._spice import et_to_datetime64, require_spiceypy, spice_read_guard
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["SpkFile", "SpkSegment", "read_spk"]

# An SPK is a DAF with ND=2 summary doubles (segment start / stop ET) and NI=6 summary ints
# (target body, centre body, frame id, segment data type, and the segment's first / last data
# addresses).
_SPK_ND = 2
_SPK_NI = 6

# The sampled-state segment types this reader parses: 9 (Lagrange, unequal steps) and 13
# (Hermite, unequal steps). Their stored data is exactly the state nodes the segment was built
# from, so reading the nodes straight from the DAF is lossless. The interpolating types
# (Chebyshev 2/3, two-body 5, equal-step Lagrange 8, …) are out of scope this milestone.
_SUPPORTED_TYPES = frozenset({9, 13})
_INTERPOLATION = {9: "Lagrange", 13: "Hermite"}

# SPK ephemeris time is TDB. The canonical Ephemeris an SPK maps to is tagged TDB; epochs are
# ET seconds past J2000 turned into datetime64 by pure arithmetic (no leapsecond kernel).
_TIME_SCALE = "TDB"


@dataclass(frozen=True, eq=False)
class SpkSegment:
    """One faithful SPK segment: its descriptor and the state nodes it stores.

    ``body_id`` / ``center_id`` / ``frame_id`` are the NAIF integer codes from the segment
    descriptor; ``body_name`` / ``center_name`` / ``frame`` are their resolved SPICE names (the
    integer as a string when SPICE has no name for it). ``segment_type`` is 9 or 13 and
    ``degree`` the interpolation degree used for a faithful re-emit (the Lagrange degree
    recovered from the segment for type 9; a valid odd Hermite degree for type 13 — either way
    the stored nodes round-trip exactly, the degree only drives interpolation between them).
    ``segment_id`` is the DAF array name. ``epochs_et`` is the ``(N,)`` node epochs in ET (TDB
    seconds past J2000) and ``states`` the ``(N, 6)`` position+velocity nodes in km / km·s⁻¹.
    """

    body_id: int
    body_name: str
    center_id: int
    center_name: str
    frame: str
    frame_id: int
    segment_type: int
    degree: int
    segment_id: str
    epochs_et: NDArray[np.float64]
    states: NDArray[np.float64]


@dataclass(frozen=True, eq=False)
class SpkFile(FidelityModel):
    """The faithful SPK fidelity model: every type-9 / type-13 segment the kernel holds.

    ``segments`` is the file's segments in DAF order; :meth:`segment_ephemerides` materialises
    each as a canonical :class:`Ephemeris`. ``raw_bytes`` is the verbatim source, kept only
    when the read opted in via ``retain_source=True`` (otherwise ``None``) so the writer can
    echo a byte-identical kernel; it is a reference to the already-loaded buffer, not a copy.
    """

    format_name: ClassVar[str] = "spk"

    segments: tuple[SpkSegment, ...]
    raw_bytes: bytes | None = None

    def segment_ephemerides(self) -> list[Ephemeris]:
        """Every segment's canonical :class:`Ephemeris`, in DAF order.

        Each is tagged with its frame, centre body, and TDB, carries this whole
        :class:`SpkFile` as ``source_native``, and uses the target body's name (or its NAIF id
        as a string) as ``object_name``.
        """
        return [self._segment_ephemeris(segment) for segment in self.segments]

    def _segment_ephemeris(self, segment: SpkSegment) -> Ephemeris:
        metadata = Metadata(
            object_name=segment.body_name,
            reference_frame=segment.frame,
            central_body=segment.center_name,
            time_scale=_TIME_SCALE,
            provenance=Provenance(source_format="spk"),
        )
        return Ephemeris(
            metadata=metadata,
            source_native=self,
            epochs=et_to_datetime64(segment.epochs_et),
            positions=segment.states[:, 0:3],
            velocities=segment.states[:, 3:6],
            interpolation=_INTERPOLATION[segment.segment_type],
            interpolation_degree=segment.degree,
        )


def read_spk(source: Source) -> Ephemeris:
    """Read a SPICE SPK kernel (``.bsp`` / ``.spk``) into a canonical :class:`Ephemeris`.

    Requires the ``[spk]`` extra (``spiceypy``); without it raises
    :class:`~orbit_formats.errors.MissingOptionalDependencyError`. Parses every type-9 /
    type-13 segment into an :class:`SpkFile` fidelity model (retained as ``source_native``) and
    returns the **first** segment as the canonical ephemeris — tagged with its SPICE frame,
    centre body, and TDB. The full per-segment set is available via
    :meth:`SpkFile.segment_ephemerides`.

    Raises :class:`~orbit_formats.errors.MalformedSourceError` for a file that is not a
    readable DAF/SPK, a segment whose type is not 9 or 13, or a segment with a truncated or
    invalid node block. When the source opted into retention (``read(..., retain_source=True)``),
    the verbatim bytes are kept on the fidelity model for a byte-identical re-emit.
    """
    spice = require_spiceypy()
    spk = _parse(spice, source)
    if source.retain:
        spk = replace(spk, raw_bytes=source.read_bytes())
    return spk._segment_ephemeris(spk.segments[0])


def _parse(spice: Any, source: Source) -> SpkFile:
    """Open the SPK via SPICE — from its path, or a temp spill of an in-memory buffer."""
    if source.path is not None:
        return _parse_path(spice, str(source.path))
    handle_fd, tmp_path = tempfile.mkstemp(suffix=".bsp")
    try:
        with os.fdopen(handle_fd, "wb") as tmp:
            tmp.write(source.read_bytes())
        return _parse_path(spice, tmp_path)
    finally:
        os.unlink(tmp_path)


def _parse_path(spice: Any, path: str) -> SpkFile:
    handle: int | None = None
    try:
        with spice_read_guard(spice, "could not read the SPK file"):
            handle = int(spice.dafopr(path))
            segments = _read_segments(spice, handle)
    finally:
        if handle is not None:
            _close_daf(spice, handle)
    if not segments:
        raise MalformedSourceError("the SPK file contains no segments")
    return SpkFile(segments=tuple(segments))


def _read_segments(spice: Any, handle: int) -> list[SpkSegment]:
    """Walk the DAF segments forward, reading each type-9 / type-13 node block faithfully."""
    segments: list[SpkSegment] = []
    spice.dafbfs(handle)  # begin forward search
    found = spice.daffna()  # find next array
    while found:
        summary = spice.dafgs()
        segment_id = str(spice.dafgn()).strip()
        _doubles, ints = spice.dafus(summary, _SPK_ND, _SPK_NI)
        body_id, center_id, frame_id, seg_type, begin, end = (int(value) for value in ints)
        if seg_type not in _SUPPORTED_TYPES:
            raise MalformedSourceError(
                f"SPK segment type {seg_type} is not supported; this reader handles the "
                "sampled-state types 9 (Lagrange) and 13 (Hermite)"
            )
        states, epochs_et, degree = _read_nodes(spice, handle, begin, end, seg_type)
        segments.append(
            SpkSegment(
                body_id=body_id,
                body_name=_body_name(spice, body_id),
                center_id=center_id,
                center_name=_body_name(spice, center_id),
                frame=_frame_name(spice, frame_id),
                frame_id=frame_id,
                segment_type=seg_type,
                degree=degree,
                segment_id=segment_id,
                epochs_et=epochs_et,
                states=states,
            )
        )
        found = spice.daffna()
    return segments


def _read_nodes(
    spice: Any, handle: int, begin: int, end: int, seg_type: int
) -> tuple[NDArray[np.float64], NDArray[np.float64], int]:
    """Read a type-9 / type-13 segment's ``(N, 6)`` state nodes and ``(N,)`` epochs.

    The segment's last two doubles are ``(interpolation parameter, node count N)``; the ``6N``
    state components and ``N`` epochs precede them. The trailing parameter is the Lagrange
    degree for type 9 (recovered for a faithful re-emit) and is not the recoverable degree for
    type 13 — see :func:`_segment_degree`.
    """
    trailing = np.asarray(spice.dafgda(handle, end - 1, end), dtype=np.float64)
    n = round(float(trailing[1]))
    if n < 1:
        raise MalformedSourceError(f"SPK segment declares an invalid node count {n}")
    states_flat = np.asarray(spice.dafgda(handle, begin, begin + 6 * n - 1), dtype=np.float64)
    epochs = np.asarray(spice.dafgda(handle, begin + 6 * n, begin + 7 * n - 1), dtype=np.float64)
    if states_flat.size != 6 * n or epochs.size != n:
        raise MalformedSourceError(
            f"SPK segment data is truncated: expected {6 * n} state and {n} epoch values, "
            f"got {states_flat.size} and {epochs.size}"
        )
    degree = _segment_degree(seg_type, float(trailing[0]), n)
    return states_flat.reshape(n, 6), epochs, degree


def _segment_degree(seg_type: int, directory_value: float, n: int) -> int:
    """The interpolation degree to re-emit a segment with.

    Type 9 (Lagrange) stores its polynomial degree in the segment's penultimate double, so it
    is recovered directly. Type 13 (Hermite) does not store a recoverable degree there, so a
    valid odd degree bounded by the node count is used. Either way the stored *nodes* round-trip
    exactly — the degree only governs interpolation *between* them.
    """
    if seg_type == 9:
        return max(1, min(round(directory_value), n - 1)) if n > 1 else 1
    degree = n - 1
    if degree % 2 == 0:
        degree -= 1
    return max(1, degree)


def _body_name(spice: Any, code: int) -> str:
    """The body's SPICE name, or its NAIF id as a string when SPICE has no name for it."""
    from spiceypy.utils.exceptions import NotFoundError

    try:
        return str(spice.bodc2n(code))
    except NotFoundError:
        return str(code)


def _frame_name(spice: Any, frame_id: int) -> str:
    """The frame's SPICE name, or its id as a string when SPICE has no name for it."""
    name = str(spice.frmnam(frame_id))
    return name if name else str(frame_id)


def _close_daf(spice: Any, handle: int) -> None:
    # Best-effort cleanup; reset SPICE on any close failure so a later call is not blocked.
    try:
        spice.dafcls(handle)
    except Exception:
        spice.reset()


register_reader("spk", read_spk)
