"""CCSDS OEM reader — in-house parsing of the Orbit Ephemeris Message into a fidelity model.

The KVN reader is hand-written, extending gmat-run's proven OEM and AEM work; the XML form
is parsed through orbit-formats' own MIT xsdata bindings (see
:mod:`orbit_formats.adapters.oem_xml`). No GPL dependency is ever imported at runtime.

Both notations parse into the *same* faithful :class:`OemFile` fidelity model — every field
the format defines, across the header and one or more segments — which is then adapted into
a canonical :class:`~orbit_formats.canonical.ephemeris.Ephemeris`, with the fidelity model
retained as ``source_native`` so a same-format write stays byte-lossless. The notation a
file was read from is recorded on the model (``serialization``) so a write re-emits in the
same notation by default. A multi-segment file is concatenated into one canonical ephemeris;
the per-segment metadata is preserved on the fidelity model. :func:`read_oem` dispatches on
content: an XML document (whose first token is a tag) routes to the XML parser, everything
else to the hand-written KVN scanner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar, Literal

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import TIME_SCALES, Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["OemCovariance", "OemFile", "OemSegment", "OemSegmentMeta", "read_oem"]

# OEM block markers, each alone on its own line.
_META_START = "META_START"
_META_STOP = "META_STOP"
_COVARIANCE_START = "COVARIANCE_START"
_COVARIANCE_STOP = "COVARIANCE_STOP"

# A ``KEYWORD = value`` line: a leading identifier, then ``=``, then the (possibly empty)
# value. Whitespace around the ``=`` is free, so "odd whitespace" parses the same.
_KEYWORD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*)$")

# The seven mandatory OEM META keywords (CCSDS 502.0-B) and the full set the reader
# recognises; an unrecognised ``KEY = value`` line in META is kept verbatim in
# ``OemSegmentMeta.extra`` rather than dropped, so no field is lost.
_REQUIRED_META_KEYS = (
    "OBJECT_NAME",
    "OBJECT_ID",
    "CENTER_NAME",
    "REF_FRAME",
    "TIME_SYSTEM",
    "START_TIME",
    "STOP_TIME",
)
_KNOWN_META_KEYS = frozenset(_REQUIRED_META_KEYS) | {
    "REF_FRAME_EPOCH",
    "USEABLE_START_TIME",
    "USEABLE_STOP_TIME",
    "INTERPOLATION",
    "INTERPOLATION_DEGREE",
}

# A state line carries an epoch plus the position/velocity triplet, optionally followed by
# the acceleration triplet (km, km/s, km/s^2). The covariance matrix is the lower triangle
# of a symmetric 6x6 — 21 elements.
_STATE_COLUMNS_NO_ACCEL = 7
_STATE_COLUMNS_WITH_ACCEL = 10
_COVARIANCE_ELEMENTS = 21


@dataclass(frozen=True, slots=True)
class OemSegmentMeta:
    """The faithful META block of one OEM segment — every keyword the segment defines.

    The seven mandatory keywords are non-optional; the rest are present only when the file
    sets them. ``comments`` keeps the segment's META ``COMMENT`` lines in order, and
    ``extra`` keeps any non-standard ``KEYWORD = value`` line verbatim (original-case key)
    so a faithful round-trip loses nothing.
    """

    object_name: str
    object_id: str
    center_name: str
    ref_frame: str
    time_system: str
    start_time: str
    stop_time: str
    ref_frame_epoch: str | None = None
    useable_start_time: str | None = None
    useable_stop_time: str | None = None
    interpolation: str | None = None
    interpolation_degree: int | None = None
    comments: tuple[str, ...] = ()
    extra: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class OemCovariance:
    """One covariance matrix from an OEM ``COVARIANCE`` block.

    ``matrix`` holds the 21 lower-triangular elements of the symmetric 6x6 position /
    velocity covariance in row order, ``epoch`` the matrix epoch, and ``cov_ref_frame`` the
    frame it is expressed in when the block names one. The canonical ``Ephemeris`` has no
    covariance slot in v0.1, so covariance survives only here, on the fidelity model.
    """

    epoch: np.datetime64
    matrix: tuple[float, ...]
    cov_ref_frame: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class OemSegment:
    """One OEM segment: its META block, ephemeris records, and optional covariance.

    ``epochs`` is ``(n,)`` ``datetime64[ns]``; ``positions`` / ``velocities`` are ``(n, 3)``
    km / km·s⁻¹. ``accelerations`` is ``(n, 3)`` km·s⁻² when the segment's lines carry the
    acceleration triplet, else ``None`` — the canonical ``Ephemeris`` holds position and
    velocity only, so acceleration is preserved here and nowhere down-projected.
    """

    meta: OemSegmentMeta
    epochs: NDArray[np.datetime64]
    positions: NDArray[np.float64]
    velocities: NDArray[np.float64]
    accelerations: NDArray[np.float64] | None = None
    covariances: tuple[OemCovariance, ...] = ()
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class OemFile(FidelityModel):
    """The faithful OEM fidelity model: the header plus every segment, in file order.

    Holding every field a same-format OEM write reconstructs from, so an OEM → OEM
    round-trip stays content-lossless without polluting the canonical schema.
    ``ccsds_version`` is the ``CCSDS_OEM_VERS`` value; ``creation_date`` / ``originator``
    and the header ``comments`` are the file-level header fields.

    ``raw_bytes`` is the verbatim source, kept only when the read opted in via
    ``retain_source=True`` (otherwise ``None``); it is a reference to the already-loaded
    buffer, not a copy. The writer echoes it for a byte-identical same-format re-emit; with
    it absent, the writer re-serialises the structured model (content-lossless).

    ``serialization`` records the notation the file was read from — ``"kvn"`` or ``"xml"``,
    the two encodings of one OEM. Both parse into this same model; the writer re-emits in
    the recorded notation by default (the destination extension can override it), so a
    ``.xml`` source round-trips back to XML and a ``.oem`` source back to KVN.
    """

    format_name: ClassVar[str] = "ccsds-oem"

    ccsds_version: str
    segments: tuple[OemSegment, ...]
    creation_date: str | None = None
    originator: str | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_oem(source: Source) -> Ephemeris:
    """Read a CCSDS OEM (KVN or XML) into a canonical :class:`Ephemeris`.

    Parses the header and every segment into an :class:`OemFile` fidelity model, retained
    as ``source_native``, then concatenates the segments' state records into one canonical
    ephemeris tagged with the frame, central body, time scale, and object id from the OEM
    META. The notation is detected from the content — an XML document routes to the xsdata
    bindings (:mod:`orbit_formats.adapters.oem_xml`), everything else to the hand-written
    KVN scanner — and both produce the same :class:`OemFile`. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword, an
    unclosed block, a malformed state or covariance line, an unparseable epoch, malformed
    XML, or segments that disagree on frame / central body / time system (which cannot be
    concatenated into one canonical series without a frame/time transform).

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        # Imported lazily: the xsdata bindings are large, so the XML path stays free until
        # an OEM in XML is actually read.
        from orbit_formats.adapters.oem_xml import oemfile_from_xml

        oem = oemfile_from_xml(source.read_bytes())
    else:
        oem = _OemParser(text.splitlines()).parse()
    if source.retain:
        oem = replace(oem, raw_bytes=source.read_bytes())
    return _to_ephemeris(oem)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is an OEM in XML rather than KVN — its first content is an XML tag.

    An OEM XML document opens with ``<?xml`` or ``<oem`` (after an optional byte-order mark
    and leading whitespace); a KVN OEM opens with ``CCSDS_OEM_VERS`` or a ``COMMENT``. The
    first non-blank character is therefore a clean discriminator.
    """
    return text.lstrip("\ufeff \t\r\n").startswith("<")


class _OemParser:
    """A single-pass, blank-tolerant scanner over an OEM's KVN lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._i = 0

    def parse(self) -> OemFile:
        version, creation_date, originator, header_comments = self._parse_header()
        segments: list[OemSegment] = []
        while True:
            line = self._peek()
            if line is None:
                break
            if line.strip().upper() == _META_START:
                segments.append(self._parse_segment())
            else:
                raise MalformedSourceError(
                    f"unexpected content outside an OEM segment: {line.strip()!r}"
                )
        if not segments:
            raise MalformedSourceError("not a valid OEM: no META_START segment was found")
        return OemFile(
            ccsds_version=version,
            segments=tuple(segments),
            creation_date=creation_date,
            originator=originator,
            comments=tuple(header_comments),
        )

    def _parse_header(self) -> tuple[str, str | None, str | None, list[str]]:
        version: str | None = None
        creation_date: str | None = None
        originator: str | None = None
        comments: list[str] = []
        while True:
            line = self._peek()
            if line is None or line.strip().upper() == _META_START:
                break
            stripped = self._next_stripped()
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            key, value = self._require_keyword(stripped, "header")
            if key == "CCSDS_OEM_VERS":
                version = value
            elif key == "CREATION_DATE":
                creation_date = value
            elif key == "ORIGINATOR":
                originator = value
            else:
                raise MalformedSourceError(
                    f"unexpected keyword {key!r} in the OEM header before the first META_START"
                )
        if version is None:
            raise MalformedSourceError(
                "not a CCSDS OEM: the 'CCSDS_OEM_VERS' header keyword is missing"
            )
        return version, creation_date, originator, comments

    def _parse_segment(self) -> OemSegment:
        self._next()  # consume META_START (already confirmed by the caller)
        meta = self._parse_meta()
        epochs, positions, velocities, accelerations, comments = self._parse_data()
        covariances: list[OemCovariance] = []
        while True:
            line = self._peek()
            if line is None or line.strip().upper() != _COVARIANCE_START:
                break
            covariances.extend(self._parse_covariance())
        return OemSegment(
            meta=meta,
            epochs=epochs,
            positions=positions,
            velocities=velocities,
            accelerations=accelerations,
            covariances=tuple(covariances),
            comments=tuple(comments),
        )

    def _parse_meta(self) -> OemSegmentMeta:
        values: dict[str, str] = {}
        comments: list[str] = []
        extra: list[tuple[str, str]] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError("OEM META block was not closed with META_STOP")
            stripped = line.strip()
            if stripped.upper() == _META_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            match = _KEYWORD_RE.match(stripped)
            if match is None:
                raise MalformedSourceError(
                    f"expected 'KEYWORD = value' in the OEM META block, got {stripped!r}"
                )
            key = match.group(1).upper()
            value = match.group(2).strip()
            if key in _KNOWN_META_KEYS:
                if key in values:
                    raise MalformedSourceError(f"duplicate OEM META keyword {key!r}")
                values[key] = value
            else:
                extra.append((match.group(1), value))
        return _build_meta(values, comments, extra)

    def _parse_data(
        self,
    ) -> tuple[
        NDArray[np.datetime64],
        NDArray[np.float64],
        NDArray[np.float64],
        NDArray[np.float64] | None,
        list[str],
    ]:
        epochs: list[np.datetime64] = []
        positions: list[list[float]] = []
        velocities: list[list[float]] = []
        accelerations: list[list[float]] = []
        comments: list[str] = []
        saw_accel = False
        saw_no_accel = False
        while True:
            line = self._peek()
            if line is None:
                break
            stripped = line.strip()
            if stripped.upper() in (_META_START, _COVARIANCE_START):
                break
            self._next()
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            epoch, position, velocity, acceleration = _parse_state_line(stripped)
            epochs.append(epoch)
            positions.append(position)
            velocities.append(velocity)
            if acceleration is None:
                saw_no_accel = True
            else:
                saw_accel = True
                accelerations.append(acceleration)
        if saw_accel and saw_no_accel:
            raise MalformedSourceError("OEM segment mixes 6-column and 9-column ephemeris lines")
        return (
            _datetime_array(epochs),
            _float_matrix(positions),
            _float_matrix(velocities),
            _float_matrix(accelerations) if saw_accel else None,
            comments,
        )

    def _parse_covariance(self) -> list[OemCovariance]:
        self._next()  # consume COVARIANCE_START (already confirmed by the caller)
        covariances: list[OemCovariance] = []
        epoch: np.datetime64 | None = None
        frame: str | None = None
        comments: list[str] = []
        values: list[float] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError(
                    "OEM COVARIANCE block was not closed with COVARIANCE_STOP"
                )
            stripped = line.strip()
            if stripped.upper() == _COVARIANCE_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            match = _KEYWORD_RE.match(stripped)
            if match is not None:
                key = match.group(1).upper()
                value = match.group(2).strip()
                if key == "EPOCH":
                    if epoch is not None:
                        covariances.append(_build_covariance(epoch, frame, values, comments))
                        frame, comments, values = None, [], []
                    epoch = _parse_epoch(value)
                elif key == "COV_REF_FRAME":
                    frame = value
                else:
                    raise MalformedSourceError(
                        f"unexpected keyword {key!r} in the OEM COVARIANCE block"
                    )
                continue
            try:
                values.extend(float(token) for token in stripped.split())
            except ValueError as exc:
                raise MalformedSourceError(
                    f"non-numeric value in the OEM covariance matrix: {stripped!r}"
                ) from exc
        if epoch is not None:
            covariances.append(_build_covariance(epoch, frame, values, comments))
        elif values:
            raise MalformedSourceError("OEM covariance data has no preceding EPOCH")
        return covariances

    def _require_keyword(self, line: str, where: str) -> tuple[str, str]:
        match = _KEYWORD_RE.match(line)
        if match is None:
            raise MalformedSourceError(
                f"expected 'KEYWORD = value' in the OEM {where}, got {line!r}"
            )
        return match.group(1).upper(), match.group(2).strip()

    def _peek(self) -> str | None:
        """The next non-blank line without consuming it (blank lines are skipped)."""
        while self._i < len(self._lines) and not self._lines[self._i].strip():
            self._i += 1
        return self._lines[self._i] if self._i < len(self._lines) else None

    def _next(self) -> str | None:
        """The next non-blank line, consumed."""
        line = self._peek()
        if line is not None:
            self._i += 1
        return line

    def _next_stripped(self) -> str:
        line = self._next()
        assert line is not None  # callers guard EOF via _peek() before calling
        return line.strip()


def _is_comment(line: str) -> bool:
    """Whether a (stripped) line is a ``COMMENT`` line."""
    head = line.split(None, 1)[0] if line else ""
    return head.upper() == "COMMENT"


def _comment_text(line: str) -> str:
    """The text of a ``COMMENT`` line (everything after the keyword), possibly empty."""
    parts = line.split(None, 1)
    return parts[1] if len(parts) > 1 else ""


def _build_meta(
    values: dict[str, str], comments: list[str], extra: list[tuple[str, str]]
) -> OemSegmentMeta:
    missing = [key for key in _REQUIRED_META_KEYS if key not in values]
    if missing:
        raise MalformedSourceError(
            f"OEM META block is missing required keyword(s): {', '.join(missing)}"
        )
    degree_raw = values.get("INTERPOLATION_DEGREE")
    try:
        degree = int(degree_raw) if degree_raw is not None else None
    except ValueError as exc:
        raise MalformedSourceError(
            f"INTERPOLATION_DEGREE must be an integer, got {degree_raw!r}"
        ) from exc
    return OemSegmentMeta(
        object_name=values["OBJECT_NAME"],
        object_id=values["OBJECT_ID"],
        center_name=values["CENTER_NAME"],
        ref_frame=values["REF_FRAME"],
        time_system=values["TIME_SYSTEM"],
        start_time=values["START_TIME"],
        stop_time=values["STOP_TIME"],
        ref_frame_epoch=values.get("REF_FRAME_EPOCH"),
        useable_start_time=values.get("USEABLE_START_TIME"),
        useable_stop_time=values.get("USEABLE_STOP_TIME"),
        interpolation=values.get("INTERPOLATION"),
        interpolation_degree=degree,
        comments=tuple(comments),
        extra=tuple(extra),
    )


def _build_covariance(
    epoch: np.datetime64, frame: str | None, values: list[float], comments: list[str]
) -> OemCovariance:
    if len(values) != _COVARIANCE_ELEMENTS:
        raise MalformedSourceError(
            f"OEM covariance matrix must have {_COVARIANCE_ELEMENTS} lower-triangular values, "
            f"got {len(values)}"
        )
    return OemCovariance(
        epoch=epoch, matrix=tuple(values), cov_ref_frame=frame, comments=tuple(comments)
    )


def _parse_state_line(
    line: str,
) -> tuple[np.datetime64, list[float], list[float], list[float] | None]:
    """Parse one OEM ephemeris line: an epoch plus 6 (pos/vel) or 9 (with accel) values."""
    tokens = line.split()
    if len(tokens) not in (_STATE_COLUMNS_NO_ACCEL, _STATE_COLUMNS_WITH_ACCEL):
        raise MalformedSourceError(
            "OEM state line must be an epoch plus 6 or 9 numeric values, got "
            f"{len(tokens)} token(s): {line!r}"
        )
    epoch = _parse_epoch(tokens[0])
    try:
        numbers = [float(token) for token in tokens[1:]]
    except ValueError as exc:
        raise MalformedSourceError(f"non-numeric value in the OEM state line {line!r}") from exc
    acceleration = numbers[6:9] if len(numbers) == 9 else None
    return epoch, numbers[0:3], numbers[3:6], acceleration


def _parse_epoch(token: str) -> np.datetime64:
    """Parse a CCSDS ASCII epoch into ``datetime64[ns]``.

    Accepts both the calendar form (``YYYY-MM-DDThh:mm:ss[.fff]``) and the day-of-year form
    (``YYYY-DDDThh:mm:ss[.fff]``); a trailing ``Z`` is tolerated. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` if the epoch cannot be parsed.
    """
    text = token.strip().rstrip("Zz")
    date_part, sep, time_part = text.partition("T")
    if not sep:
        raise MalformedSourceError(f"could not parse the CCSDS epoch {token!r}: no date/time 'T'")
    try:
        if date_part.count("-") == 1:
            return _doy_epoch(date_part, time_part)
        return np.datetime64(text, "ns")
    except (ValueError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the CCSDS epoch {token!r}: {exc}") from exc


def _doy_epoch(date_part: str, time_part: str) -> np.datetime64:
    """Convert a ``YYYY-DDD`` date plus ``hh:mm:ss[.fff]`` time to ``datetime64[ns]``."""
    year_str, _, doy_str = date_part.partition("-")
    fields = time_part.split(":")
    if len(fields) != 3:
        raise ValueError(f"expected hh:mm:ss in the time-of-day, got {time_part!r}")
    year, doy = int(year_str), int(doy_str)
    hours, minutes, seconds = int(fields[0]), int(fields[1]), float(fields[2])
    base = np.datetime64(f"{year:04d}-01-01", "ns")
    offset_seconds = (doy - 1) * 86400 + hours * 3600 + minutes * 60 + seconds
    return base + np.timedelta64(round(offset_seconds * 1_000_000_000), "ns")


def _datetime_array(epochs: list[np.datetime64]) -> NDArray[np.datetime64]:
    return np.array(epochs, dtype="datetime64[ns]")


def _float_matrix(rows: list[list[float]]) -> NDArray[np.float64]:
    if not rows:
        return np.empty((0, 3), dtype=np.float64)
    return np.array(rows, dtype=np.float64)


def _to_ephemeris(oem: OemFile) -> Ephemeris:
    """Adapt an :class:`OemFile` into the canonical :class:`Ephemeris`.

    Concatenates every segment's states into one canonical series and tags it from the
    first segment's META, after asserting the segments share a frame, central body, and
    time system (see :func:`_require_consistent_segments`). The whole :class:`OemFile`
    rides along as ``source_native``.
    """
    _require_consistent_segments(oem.segments)
    first = oem.segments[0]
    if len(oem.segments) == 1:
        epochs = first.epochs
        positions = first.positions
        velocities = first.velocities
    else:
        epochs = np.concatenate([segment.epochs for segment in oem.segments])
        positions = np.concatenate([segment.positions for segment in oem.segments], axis=0)
        velocities = np.concatenate([segment.velocities for segment in oem.segments], axis=0)
    metadata = Metadata(
        object_name=first.meta.object_name,
        object_id=first.meta.object_id,
        originator=oem.originator,
        reference_frame=first.meta.ref_frame,
        central_body=first.meta.center_name,
        time_scale=_canonical_time_scale(first.meta.time_system),
        provenance=Provenance(source_format="ccsds-oem", creation_date=oem.creation_date),
    )
    return Ephemeris(
        metadata=metadata,
        source_native=oem,
        epochs=epochs,
        positions=positions,
        velocities=velocities,
        interpolation=first.meta.interpolation,
        interpolation_degree=first.meta.interpolation_degree,
    )


def _require_consistent_segments(segments: tuple[OemSegment, ...]) -> None:
    """Reject a multi-segment OEM whose segments cannot share one canonical series.

    The segments are concatenated into a single Cartesian ephemeris under one metadata
    spine, so they must agree on the reference frame, central body, and time system.
    Concatenating states tagged with different values would be physically meaningless (and
    would need a frame/time transform v0.1 does not perform), so a disagreement raises
    rather than silently producing a wrong ephemeris.
    """
    first = segments[0].meta
    for segment in segments[1:]:
        for label, expected, actual in (
            ("REF_FRAME", first.ref_frame, segment.meta.ref_frame),
            ("CENTER_NAME", first.center_name, segment.meta.center_name),
            ("TIME_SYSTEM", first.time_system, segment.meta.time_system),
        ):
            if expected != actual:
                raise MalformedSourceError(
                    f"OEM segments disagree on {label} ({expected!r} vs {actual!r}); "
                    "states across different values cannot be concatenated into one ephemeris"
                )


def _canonical_time_scale(time_system: str) -> str | None:
    """Map an OEM ``TIME_SYSTEM`` to a canonical time scale, or ``None`` if not one of them.

    The canonical spine recognises a fixed set of scales (see
    :data:`~orbit_formats.canonical.metadata.TIME_SCALES`). An OEM may name an exotic scale
    (e.g. ``TCB``) the spine cannot tag; the raw value stays on the fidelity model's META,
    so nothing is lost.
    """
    candidate = time_system.strip().upper()
    return candidate if candidate in TIME_SCALES else None


register_reader("ccsds-oem", read_oem)
