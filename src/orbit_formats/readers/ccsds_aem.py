"""CCSDS AEM reader — in-house parsing of the Attitude Ephemeris Message into a fidelity model.

The KVN reader is hand-written; the XML form is parsed through orbit-formats' own MIT xsdata
bindings (see :mod:`orbit_formats.adapters.aem_xml`). No GPL dependency is ever imported at
runtime. Both notations parse into the *same* faithful :class:`AemFile` fidelity model — the
header plus one or more segments, each a META block and a ``DATA_START`` / ``DATA_STOP`` block
of attitude records — which is adapted into a canonical
:class:`~orbit_formats.canonical.attitude.Attitude`, with the fidelity model retained as
``source_native`` so a same-format write stays byte-lossless.

AEM is the attitude analogue of OEM: a time series, multi-segment, concatenated into one
canonical object. The attitude per epoch is a quaternion (``Q1 Q2 Q3 QC``), three Euler
angles, or a spin state — the columns governed by the segment's ``ATTITUDE_TYPE``. The KVN
the wider tooling ecosystem emits is version 1.0 (with the ``ATTITUDE_DIR`` and
``QUATERNION_TYPE`` tags the version-2 XML schema dropped); both are recorded on the fidelity
model so a faithful round-trip loses nothing, while the canonical record stores quaternions in
the fixed ``Q1 Q2 Q3 QC`` scalar-last order regardless of the ``QUATERNION_TYPE`` a source used.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar, Literal

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.attitude import ATTITUDE_TYPES, Attitude
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import (
    _KEYWORD_RE,
    _canonical_time_scale,
    _comment_text,
    _datetime_array,
    _is_comment,
    _parse_epoch,
)
from orbit_formats.readers.ccsds_omm import _kvn_float
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["AemFile", "AemSegment", "AemSegmentMeta", "read_aem"]

# AEM block markers, each alone on its own line.
_META_START = "META_START"
_META_STOP = "META_STOP"
_DATA_START = "DATA_START"
_DATA_STOP = "DATA_STOP"

# The mandatory AEM META keywords (CCSDS 504.0-B) and the full set the reader recognises.
# CENTER_NAME, the useable-window bounds, the notation tags, and the interpolation block are
# optional; an unrecognised keyword is rejected (AEM META is a closed vocabulary).
_REQUIRED_META_KEYS = (
    "OBJECT_NAME",
    "OBJECT_ID",
    "REF_FRAME_A",
    "REF_FRAME_B",
    "TIME_SYSTEM",
    "START_TIME",
    "STOP_TIME",
    "ATTITUDE_TYPE",
)
_KNOWN_META_KEYS = frozenset(_REQUIRED_META_KEYS) | {
    "CENTER_NAME",
    "ATTITUDE_DIR",
    "USEABLE_START_TIME",
    "USEABLE_STOP_TIME",
    "QUATERNION_TYPE",
    "EULER_ROT_SEQ",
    "INTERPOLATION_METHOD",
    "INTERPOLATION_DEGREE",
}


@dataclass(frozen=True, slots=True)
class AemSegmentMeta:
    """The faithful META block of one AEM segment — every keyword the segment defines.

    The mandatory keywords are non-optional; the rest are present only when the file sets
    them. ``attitude_type`` is one of the canonical :data:`ATTITUDE_TYPES` keys
    (``QUATERNION`` / ``EULER_ANGLE`` / ``SPIN``). ``attitude_dir`` (``A2B`` / ``B2A``) and
    ``quaternion_type`` (``FIRST`` / ``LAST``) are version-1 KVN notation tags the version-2
    XML schema has no field for; they ride here so a KVN round-trip is faithful.
    ``comments`` keeps the segment's META ``COMMENT`` lines in order.
    """

    object_name: str
    object_id: str
    ref_frame_a: str
    ref_frame_b: str
    time_system: str
    start_time: str
    stop_time: str
    attitude_type: str
    center_name: str | None = None
    attitude_dir: str | None = None
    useable_start_time: str | None = None
    useable_stop_time: str | None = None
    quaternion_type: str | None = None
    euler_rot_seq: str | None = None
    interpolation_method: str | None = None
    interpolation_degree: int | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class AemSegment:
    """One AEM segment: its META block and the attitude records of its DATA block.

    ``epochs`` is ``(n,)`` ``datetime64[ns]``; ``records`` is ``(n, k)`` with ``k`` fixed by
    ``meta.attitude_type`` (4 for a quaternion, 3 for Euler angles, 4 for a spin state), the
    components in the canonical column order (quaternions scalar-last). ``comments`` keeps the
    DATA block's ``COMMENT`` lines.
    """

    meta: AemSegmentMeta
    epochs: NDArray[np.datetime64]
    records: NDArray[np.float64]
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class AemFile(FidelityModel):
    """The faithful AEM fidelity model: the header plus every segment, in file order.

    Holds every field a same-format AEM write reconstructs from. ``raw_bytes`` is the
    verbatim source kept only when the read opted in via ``retain_source=True``;
    ``serialization`` records the notation it was read from (``"kvn"`` or ``"xml"``) so a
    write re-emits in the same notation by default.
    """

    format_name: ClassVar[str] = "ccsds-aem"

    ccsds_version: str
    segments: tuple[AemSegment, ...]
    creation_date: str | None = None
    originator: str | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_aem(source: Source) -> Attitude:
    """Read a CCSDS AEM (KVN or XML) into a canonical :class:`Attitude`.

    Parses the header and every segment into an :class:`AemFile` fidelity model, retained as
    ``source_native``, then concatenates the segments' attitude records into one canonical
    attitude tagged with the two frames, central body, time scale, and object id from the AEM
    META. The notation is detected from the content — an XML document routes to the xsdata
    bindings (:mod:`orbit_formats.adapters.aem_xml`), everything else to the hand-written KVN
    scanner — and both produce the same :class:`AemFile`. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword, an
    unclosed block, a malformed or wrong-width data line, an unparseable epoch, an unsupported
    ``ATTITUDE_TYPE``, malformed XML, or segments that disagree on the frames / time system /
    attitude type (which cannot be concatenated into one canonical series).
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.aem_xml import aemfile_from_xml

        aem = aemfile_from_xml(source.read_bytes())
    else:
        aem = _AemParser(text.splitlines()).parse()
    if source.retain:
        aem = replace(aem, raw_bytes=source.read_bytes())
    return _to_attitude(aem)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is an AEM in XML rather than KVN — its first content is an XML tag."""
    return text.lstrip("﻿ \t\r\n").startswith("<")


class _AemParser:
    """A single-pass, blank-tolerant scanner over an AEM's KVN lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._i = 0

    def parse(self) -> AemFile:
        version, creation_date, originator, header_comments = self._parse_header()
        segments: list[AemSegment] = []
        while True:
            line = self._peek()
            if line is None:
                break
            if line.strip().upper() == _META_START:
                segments.append(self._parse_segment())
            else:
                raise MalformedSourceError(
                    f"unexpected content outside an AEM segment: {line.strip()!r}"
                )
        if not segments:
            raise MalformedSourceError("not a valid AEM: no META_START segment was found")
        return AemFile(
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
            if key == "CCSDS_AEM_VERS":
                version = value
            elif key == "CREATION_DATE":
                creation_date = value
            elif key == "ORIGINATOR":
                originator = value
            else:
                raise MalformedSourceError(
                    f"unexpected keyword {key!r} in the AEM header before the first META_START"
                )
        if version is None:
            raise MalformedSourceError(
                "not a CCSDS AEM: the 'CCSDS_AEM_VERS' header keyword is missing"
            )
        return version, creation_date, originator, comments

    def _parse_segment(self) -> AemSegment:
        self._next()  # consume META_START (already confirmed by the caller)
        meta = self._parse_meta()
        epochs, records, comments = self._parse_data(meta)
        return AemSegment(meta=meta, epochs=epochs, records=records, comments=tuple(comments))

    def _parse_meta(self) -> AemSegmentMeta:
        values: dict[str, str] = {}
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError("AEM META block was not closed with META_STOP")
            stripped = line.strip()
            if stripped.upper() == _META_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            match = _KEYWORD_RE.match(stripped)
            if match is None:
                raise MalformedSourceError(
                    f"expected 'KEYWORD = value' in the AEM META block, got {stripped!r}"
                )
            key = match.group(1).upper()
            value = match.group(2).strip()
            if key not in _KNOWN_META_KEYS:
                raise MalformedSourceError(f"unexpected AEM META keyword {key!r}")
            if key in values:
                raise MalformedSourceError(f"duplicate AEM META keyword {key!r}")
            values[key] = value
        return _build_meta(values, comments)

    def _parse_data(
        self, meta: AemSegmentMeta
    ) -> tuple[NDArray[np.datetime64], NDArray[np.float64], list[str]]:
        line = self._next()
        if line is None or line.strip().upper() != _DATA_START:
            got = "end of file" if line is None else repr(line.strip())
            raise MalformedSourceError(f"expected DATA_START after the AEM META block, got {got}")
        width = len(ATTITUDE_TYPES[meta.attitude_type])
        epochs: list[np.datetime64] = []
        rows: list[list[float]] = []
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError("AEM DATA block was not closed with DATA_STOP")
            stripped = line.strip()
            if stripped.upper() == _DATA_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            epoch, components = _parse_attitude_line(stripped, meta, width)
            epochs.append(epoch)
            rows.append(components)
        return _datetime_array(epochs), _records_matrix(rows, width), comments

    def _require_keyword(self, line: str, where: str) -> tuple[str, str]:
        match = _KEYWORD_RE.match(line)
        if match is None:
            raise MalformedSourceError(
                f"expected 'KEYWORD = value' in the AEM {where}, got {line!r}"
            )
        return match.group(1).upper(), match.group(2).strip()

    def _peek(self) -> str | None:
        while self._i < len(self._lines) and not self._lines[self._i].strip():
            self._i += 1
        return self._lines[self._i] if self._i < len(self._lines) else None

    def _next(self) -> str | None:
        line = self._peek()
        if line is not None:
            self._i += 1
        return line

    def _next_stripped(self) -> str:
        line = self._next()
        assert line is not None  # callers guard EOF via _peek() before calling
        return line.strip()


def _build_meta(values: dict[str, str], comments: list[str]) -> AemSegmentMeta:
    missing = [key for key in _REQUIRED_META_KEYS if key not in values]
    if missing:
        raise MalformedSourceError(
            f"AEM META block is missing required keyword(s): {', '.join(missing)}"
        )
    attitude_type = values["ATTITUDE_TYPE"].strip().upper()
    if attitude_type not in ATTITUDE_TYPES:
        raise MalformedSourceError(
            f"unsupported AEM ATTITUDE_TYPE {values['ATTITUDE_TYPE']!r}; "
            f"orbit-formats supports {', '.join(sorted(ATTITUDE_TYPES))}"
        )
    quaternion_type = values.get("QUATERNION_TYPE")
    if quaternion_type is not None:
        quaternion_type = quaternion_type.strip().upper()
        if quaternion_type not in ("FIRST", "LAST"):
            raise MalformedSourceError(
                f"AEM QUATERNION_TYPE must be FIRST or LAST, got {values['QUATERNION_TYPE']!r}"
            )
    degree_raw = values.get("INTERPOLATION_DEGREE")
    try:
        degree = int(degree_raw) if degree_raw is not None else None
    except ValueError as exc:
        raise MalformedSourceError(
            f"AEM INTERPOLATION_DEGREE must be an integer, got {degree_raw!r}"
        ) from exc
    return AemSegmentMeta(
        object_name=values["OBJECT_NAME"],
        object_id=values["OBJECT_ID"],
        ref_frame_a=values["REF_FRAME_A"],
        ref_frame_b=values["REF_FRAME_B"],
        time_system=values["TIME_SYSTEM"],
        start_time=values["START_TIME"],
        stop_time=values["STOP_TIME"],
        attitude_type=attitude_type,
        center_name=values.get("CENTER_NAME"),
        attitude_dir=values.get("ATTITUDE_DIR"),
        useable_start_time=values.get("USEABLE_START_TIME"),
        useable_stop_time=values.get("USEABLE_STOP_TIME"),
        quaternion_type=quaternion_type,
        euler_rot_seq=values.get("EULER_ROT_SEQ"),
        interpolation_method=values.get("INTERPOLATION_METHOD"),
        interpolation_degree=degree,
        comments=tuple(comments),
    )


def _parse_attitude_line(
    line: str, meta: AemSegmentMeta, width: int
) -> tuple[np.datetime64, list[float]]:
    """Parse one AEM data line: an epoch plus the attitude components for the segment's type."""
    tokens = line.split()
    if len(tokens) != width + 1:
        raise MalformedSourceError(
            f"AEM {meta.attitude_type} data line must be an epoch plus {width} value(s), "
            f"got {len(tokens) - 1}: {line!r}"
        )
    epoch = _parse_epoch(tokens[0])
    values = [_kvn_float(token, meta.attitude_type) for token in tokens[1:]]
    if meta.attitude_type == "QUATERNION" and meta.quaternion_type == "FIRST":
        # The file writes the scalar first (QC Q1 Q2 Q3); store the canonical scalar-last order.
        values = [values[1], values[2], values[3], values[0]]
    return epoch, values


def _records_matrix(rows: list[list[float]], width: int) -> NDArray[np.float64]:
    if not rows:
        return np.empty((0, width), dtype=np.float64)
    return np.array(rows, dtype=np.float64)


def _to_attitude(aem: AemFile) -> Attitude:
    """Adapt an :class:`AemFile` into the canonical :class:`Attitude`.

    Concatenates every segment's attitude records into one canonical series and tags it from
    the first segment's META, after asserting the segments share their frames, time system,
    attitude type, and Euler sequence (see :func:`_require_consistent_segments`). The whole
    :class:`AemFile` rides along as ``source_native``.
    """
    _require_consistent_segments(aem.segments)
    first = aem.segments[0]
    if len(aem.segments) == 1:
        epochs = first.epochs
        records = first.records
    else:
        epochs = np.concatenate([segment.epochs for segment in aem.segments])
        records = np.concatenate([segment.records for segment in aem.segments], axis=0)
    metadata = Metadata(
        object_name=first.meta.object_name,
        object_id=first.meta.object_id,
        originator=aem.originator,
        central_body=first.meta.center_name,
        time_scale=_canonical_time_scale(first.meta.time_system),
        provenance=Provenance(source_format="ccsds-aem", creation_date=aem.creation_date),
    )
    return Attitude(
        metadata=metadata,
        source_native=aem,
        attitude_type=first.meta.attitude_type,
        epochs=epochs,
        records=records,
        frame_a=first.meta.ref_frame_a,
        frame_b=first.meta.ref_frame_b,
        euler_rot_seq=first.meta.euler_rot_seq,
    )


def _require_consistent_segments(segments: tuple[AemSegment, ...]) -> None:
    """Reject a multi-segment AEM whose segments cannot share one canonical attitude series."""
    first = segments[0].meta
    for segment in segments[1:]:
        for label, expected, actual in (
            ("REF_FRAME_A", first.ref_frame_a, segment.meta.ref_frame_a),
            ("REF_FRAME_B", first.ref_frame_b, segment.meta.ref_frame_b),
            ("TIME_SYSTEM", first.time_system, segment.meta.time_system),
            ("ATTITUDE_TYPE", first.attitude_type, segment.meta.attitude_type),
            ("EULER_ROT_SEQ", first.euler_rot_seq, segment.meta.euler_rot_seq),
        ):
            if expected != actual:
                raise MalformedSourceError(
                    f"AEM segments disagree on {label} ({expected!r} vs {actual!r}); "
                    "attitudes across different values cannot be concatenated into one series"
                )


register_reader("ccsds-aem", read_aem)
