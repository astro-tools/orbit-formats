"""CCSDS TDM reader — in-house parsing of the Tracking Data Message into a fidelity model.

The KVN reader is hand-written; the XML form is parsed through orbit-formats' own MIT xsdata
bindings (see :mod:`orbit_formats.adapters.tdm_xml`). No GPL dependency is ever imported at
runtime. Both notations parse into the *same* faithful :class:`TdmFile` fidelity model — the
header plus one or more segments, each a META block and a ``DATA_START`` / ``DATA_STOP`` block
of tracking observations — which is adapted into a canonical
:class:`~orbit_formats.canonical.tracking.Tracking`, with the fidelity model retained as
``source_native`` so a same-format write stays byte-lossless.

A TDM is structurally the tracking analogue of AEM: ``META_START`` / ``META_STOP`` and
``DATA_START`` / ``DATA_STOP`` markers, one or more segments. Where it differs is the DATA
block — not a fixed-width record per epoch but a sequence of ``KEYWORD = epoch value``
observation lines (``RANGE = 2005-159T17:41:00 9.0e10``), each a single ``(type, epoch,
value)`` triple, with a large closed vocabulary of observation keywords. The META block has a
correspondingly large closed vocabulary (~60 keywords); both are modelled by declarative
keyword tables (:data:`_META_FIELDS`, :data:`OBSERVATION_KEYWORDS`) that drive the KVN parser,
the KVN writer, and the XML adapter from one source of truth, so the two notations stay
symmetric by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar, Literal

import numpy as np

from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.canonical.tracking import Tracking, TrackingObservation
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import (
    _KEYWORD_RE,
    _canonical_time_scale,
    _comment_text,
    _is_comment,
    _parse_epoch,
)
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = [
    "OBSERVATION_KEYWORDS",
    "TdmFile",
    "TdmObservation",
    "TdmSegment",
    "TdmSegmentMeta",
    "read_tdm",
]

# TDM block markers, each alone on its own line.
_META_START = "META_START"
_META_STOP = "META_STOP"
_DATA_START = "DATA_START"
_DATA_STOP = "DATA_STOP"

# A metadata value's scalar type once parsed: a string (or enum token), an integer, or a float.
MetaValue = str | int | float

# The TDM META keyword vocabulary (CCSDS 503.0-B-2), in schema order, each paired with the
# scalar kind its value parses to (``"str"`` covers plain strings *and* enum tokens, which are
# stored as their string value). The order is the canonical write order and the order both
# readers build the metadata tuple in, so a KVN-read and an XML-read model compare equal. An
# unrecognised META keyword is rejected — TDM META is a closed vocabulary.
_META_FIELDS: tuple[tuple[str, str], ...] = (
    ("TRACK_ID", "str"),
    ("DATA_TYPES", "str"),
    ("TIME_SYSTEM", "str"),
    ("START_TIME", "str"),
    ("STOP_TIME", "str"),
    ("PARTICIPANT_1", "str"),
    ("PARTICIPANT_2", "str"),
    ("PARTICIPANT_3", "str"),
    ("PARTICIPANT_4", "str"),
    ("PARTICIPANT_5", "str"),
    ("MODE", "str"),
    ("PATH", "str"),
    ("PATH_1", "str"),
    ("PATH_2", "str"),
    ("EPHEMERIS_NAME_1", "str"),
    ("EPHEMERIS_NAME_2", "str"),
    ("EPHEMERIS_NAME_3", "str"),
    ("EPHEMERIS_NAME_4", "str"),
    ("EPHEMERIS_NAME_5", "str"),
    ("TRANSMIT_BAND", "str"),
    ("RECEIVE_BAND", "str"),
    ("TURNAROUND_NUMERATOR", "int"),
    ("TURNAROUND_DENOMINATOR", "int"),
    ("TIMETAG_REF", "str"),
    ("INTEGRATION_INTERVAL", "float"),
    ("INTEGRATION_REF", "str"),
    ("FREQ_OFFSET", "float"),
    ("RANGE_MODE", "str"),
    ("RANGE_MODULUS", "float"),
    ("RANGE_UNITS", "str"),
    ("ANGLE_TYPE", "str"),
    ("REFERENCE_FRAME", "str"),
    ("INTERPOLATION", "str"),
    ("INTERPOLATION_DEGREE", "int"),
    ("DOPPLER_COUNT_BIAS", "float"),
    ("DOPPLER_COUNT_SCALE", "int"),
    ("DOPPLER_COUNT_ROLLOVER", "str"),
    ("TRANSMIT_DELAY_1", "float"),
    ("TRANSMIT_DELAY_2", "float"),
    ("TRANSMIT_DELAY_3", "float"),
    ("TRANSMIT_DELAY_4", "float"),
    ("TRANSMIT_DELAY_5", "float"),
    ("RECEIVE_DELAY_1", "float"),
    ("RECEIVE_DELAY_2", "float"),
    ("RECEIVE_DELAY_3", "float"),
    ("RECEIVE_DELAY_4", "float"),
    ("RECEIVE_DELAY_5", "float"),
    ("DATA_QUALITY", "str"),
    ("CORRECTION_ANGLE_1", "float"),
    ("CORRECTION_ANGLE_2", "float"),
    ("CORRECTION_DOPPLER", "float"),
    ("CORRECTION_MAG", "float"),
    ("CORRECTION_RANGE", "float"),
    ("CORRECTION_RCS", "float"),
    ("CORRECTION_RECEIVE", "float"),
    ("CORRECTION_TRANSMIT", "float"),
    ("CORRECTION_ABERRATION_YEARLY", "float"),
    ("CORRECTION_ABERRATION_DIURNAL", "float"),
    ("CORRECTIONS_APPLIED", "str"),
)
_META_FIELD_KINDS: dict[str, str] = dict(_META_FIELDS)
_META_FIELD_KEYS = frozenset(_META_FIELD_KINDS)

# The two META keywords every TDM segment must carry (CCSDS 503.0-B-2).
_REQUIRED_META_KEYS = ("TIME_SYSTEM", "PARTICIPANT_1")

#: The TDM DATA observation keyword vocabulary, in schema order — one of these tags every
#: ``KEYWORD = epoch value`` data line (and exactly one populated element of an XML
#: ``<observation>``). A closed set; an unrecognised observation keyword is rejected.
OBSERVATION_KEYWORDS: tuple[str, ...] = (
    "ANGLE_1",
    "ANGLE_2",
    "CARRIER_POWER",
    "CLOCK_BIAS",
    "CLOCK_DRIFT",
    "DOPPLER_COUNT",
    "DOPPLER_INSTANTANEOUS",
    "DOPPLER_INTEGRATED",
    "DOR",
    "MAG",
    "PC_N0",
    "PR_N0",
    "PRESSURE",
    "RANGE",
    "RCS",
    "RECEIVE_FREQ",
    "RECEIVE_FREQ_1",
    "RECEIVE_FREQ_2",
    "RECEIVE_FREQ_3",
    "RECEIVE_FREQ_4",
    "RECEIVE_FREQ_5",
    "RECEIVE_PHASE_CT_1",
    "RECEIVE_PHASE_CT_2",
    "RECEIVE_PHASE_CT_3",
    "RECEIVE_PHASE_CT_4",
    "RECEIVE_PHASE_CT_5",
    "RHUMIDITY",
    "STEC",
    "TEMPERATURE",
    "TRANSMIT_FREQ_1",
    "TRANSMIT_FREQ_2",
    "TRANSMIT_FREQ_3",
    "TRANSMIT_FREQ_4",
    "TRANSMIT_FREQ_5",
    "TRANSMIT_FREQ_RATE_1",
    "TRANSMIT_FREQ_RATE_2",
    "TRANSMIT_FREQ_RATE_3",
    "TRANSMIT_FREQ_RATE_4",
    "TRANSMIT_FREQ_RATE_5",
    "TRANSMIT_PHASE_CT_1",
    "TRANSMIT_PHASE_CT_2",
    "TRANSMIT_PHASE_CT_3",
    "TRANSMIT_PHASE_CT_4",
    "TRANSMIT_PHASE_CT_5",
    "TROPO_DRY",
    "TROPO_WET",
    "VLBI_DELAY",
)
_OBSERVATION_KEYWORD_SET = frozenset(OBSERVATION_KEYWORDS)


# --- fidelity model --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TdmObservation:
    """One TDM observation line: an observation keyword, its epoch, and the scalar value."""

    keyword: str
    epoch: np.datetime64
    value: float


@dataclass(frozen=True, slots=True)
class TdmSegmentMeta:
    """The faithful META block of one TDM segment — every keyword the segment defines.

    ``values`` keeps the segment's ``(keyword, value)`` pairs in canonical (schema) order, the
    values typed per :data:`_META_FIELDS` (enum tokens stored as their string value), so a
    KVN-read and an XML-read META compare equal regardless of source ordering. ``comments``
    keeps the META block's ``COMMENT`` lines in order.
    """

    values: tuple[tuple[str, MetaValue], ...]
    comments: tuple[str, ...] = ()

    def get(self, keyword: str) -> MetaValue | None:
        """The value for ``keyword`` if the segment carries it, else ``None``."""
        for key, value in self.values:
            if key == keyword:
                return value
        return None


@dataclass(frozen=True, slots=True)
class TdmSegment:
    """One TDM segment: its META block and the tracking observations of its DATA block.

    ``observations`` is the DATA block's observation lines in file order; ``comments`` keeps the
    DATA block's ``COMMENT`` lines.
    """

    meta: TdmSegmentMeta
    observations: tuple[TdmObservation, ...]
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class TdmFile(FidelityModel):
    """The faithful TDM fidelity model: the header plus every segment, in file order.

    Holds every field a same-format TDM write reconstructs from. ``raw_bytes`` is the verbatim
    source kept only when the read opted in via ``retain_source=True``; ``serialization``
    records the notation it was read from (``"kvn"`` or ``"xml"``) so a write re-emits in the
    same notation by default.
    """

    format_name: ClassVar[str] = "ccsds-tdm"

    ccsds_version: str
    segments: tuple[TdmSegment, ...]
    creation_date: str | None = None
    originator: str | None = None
    message_id: str | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_tdm(source: Source) -> Tracking:
    """Read a CCSDS TDM (KVN or XML) into a canonical :class:`Tracking`.

    Parses the header and every segment into a :class:`TdmFile` fidelity model, retained as
    ``source_native``, then flattens the segments' observations into one canonical tracking set
    tagged with the originator and time scale from the first segment. The notation is detected
    from the content — an XML document routes to the xsdata bindings
    (:mod:`orbit_formats.adapters.tdm_xml`), everything else to the hand-written KVN scanner —
    and both produce the same :class:`TdmFile`. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword, an
    unclosed block, an unrecognised META or observation keyword, a malformed observation line or
    epoch, or malformed XML.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim bytes
    are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.tdm_xml import tdmfile_from_xml

        tdm = tdmfile_from_xml(source.read_bytes())
    else:
        tdm = _TdmParser(text.splitlines()).parse()
    if source.retain:
        tdm = replace(tdm, raw_bytes=source.read_bytes())
    return _to_tracking(tdm)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is a TDM in XML rather than KVN — its first content is an XML tag."""
    return text.lstrip("﻿ \t\r\n").startswith("<")


class _TdmParser:
    """A single-pass, blank-tolerant scanner over a TDM's KVN lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._i = 0

    def parse(self) -> TdmFile:
        version, creation_date, originator, message_id, header_comments = self._parse_header()
        segments: list[TdmSegment] = []
        while True:
            line = self._peek()
            if line is None:
                break
            if line.strip().upper() == _META_START:
                segments.append(self._parse_segment())
            else:
                raise MalformedSourceError(
                    f"unexpected content outside a TDM segment: {line.strip()!r}"
                )
        if not segments:
            raise MalformedSourceError("not a valid TDM: no META_START segment was found")
        return TdmFile(
            ccsds_version=version,
            segments=tuple(segments),
            creation_date=creation_date,
            originator=originator,
            message_id=message_id,
            comments=tuple(header_comments),
        )

    def _parse_header(self) -> tuple[str, str | None, str | None, str | None, list[str]]:
        version: str | None = None
        creation_date: str | None = None
        originator: str | None = None
        message_id: str | None = None
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
            if key == "CCSDS_TDM_VERS":
                version = value
            elif key == "CREATION_DATE":
                creation_date = value
            elif key == "ORIGINATOR":
                originator = value
            elif key == "MESSAGE_ID":
                message_id = value
            else:
                raise MalformedSourceError(
                    f"unexpected keyword {key!r} in the TDM header before the first META_START"
                )
        if version is None:
            raise MalformedSourceError(
                "not a CCSDS TDM: the 'CCSDS_TDM_VERS' header keyword is missing"
            )
        return version, creation_date, originator, message_id, comments

    def _parse_segment(self) -> TdmSegment:
        self._next()  # consume META_START (already confirmed by the caller)
        meta = self._parse_meta()
        observations, comments = self._parse_data()
        return TdmSegment(meta=meta, observations=tuple(observations), comments=tuple(comments))

    def _parse_meta(self) -> TdmSegmentMeta:
        raw: dict[str, str] = {}
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError("TDM META block was not closed with META_STOP")
            stripped = line.strip()
            if stripped.upper() == _META_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            match = _KEYWORD_RE.match(stripped)
            if match is None:
                raise MalformedSourceError(
                    f"expected 'KEYWORD = value' in the TDM META block, got {stripped!r}"
                )
            key = match.group(1).upper()
            value = match.group(2).strip()
            if key not in _META_FIELD_KEYS:
                raise MalformedSourceError(f"unexpected TDM META keyword {key!r}")
            if key in raw:
                raise MalformedSourceError(f"duplicate TDM META keyword {key!r}")
            raw[key] = value
        return _build_meta(raw, comments)

    def _parse_data(self) -> tuple[list[TdmObservation], list[str]]:
        line = self._next()
        if line is None or line.strip().upper() != _DATA_START:
            got = "end of file" if line is None else repr(line.strip())
            raise MalformedSourceError(f"expected DATA_START after the TDM META block, got {got}")
        observations: list[TdmObservation] = []
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError("TDM DATA block was not closed with DATA_STOP")
            stripped = line.strip()
            if stripped.upper() == _DATA_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            observations.append(_parse_observation_line(stripped))
        return observations, comments

    def _require_keyword(self, line: str, where: str) -> tuple[str, str]:
        match = _KEYWORD_RE.match(line)
        if match is None:
            raise MalformedSourceError(
                f"expected 'KEYWORD = value' in the TDM {where}, got {line!r}"
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


def _build_meta(raw: dict[str, str], comments: list[str]) -> TdmSegmentMeta:
    """Build a typed, canonically-ordered :class:`TdmSegmentMeta` from raw KVN keyword values."""
    missing = [key for key in _REQUIRED_META_KEYS if key not in raw]
    if missing:
        raise MalformedSourceError(
            f"TDM META block is missing required keyword(s): {', '.join(missing)}"
        )
    typed = {key: _coerce_meta_value(key, value) for key, value in raw.items()}
    return TdmSegmentMeta(values=ordered_meta(typed), comments=tuple(comments))


def _coerce_meta_value(keyword: str, raw: str) -> MetaValue:
    """Coerce a raw KVN META value to the scalar kind :data:`_META_FIELDS` declares for it."""
    kind = _META_FIELD_KINDS[keyword]
    if kind == "int":
        try:
            return int(raw)
        except ValueError as exc:
            raise MalformedSourceError(f"TDM {keyword} must be an integer, got {raw!r}") from exc
    if kind == "float":
        try:
            return float(raw)
        except ValueError as exc:
            raise MalformedSourceError(f"TDM {keyword} must be a number, got {raw!r}") from exc
    return raw


def ordered_meta(typed: dict[str, MetaValue]) -> tuple[tuple[str, MetaValue], ...]:
    """Order an already-typed META mapping into the canonical :data:`_META_FIELDS` sequence.

    Shared by the KVN reader, the XML adapter, and the writer's synthesiser so every path
    builds the metadata tuple in the same order — the precondition for KVN ↔ XML model parity.
    """
    return tuple((key, typed[key]) for key, _kind in _META_FIELDS if key in typed)


def _parse_observation_line(line: str) -> TdmObservation:
    """Parse one TDM DATA line: ``KEYWORD = epoch value``."""
    match = _KEYWORD_RE.match(line)
    if match is None:
        raise MalformedSourceError(
            f"expected 'KEYWORD = epoch value' in the TDM DATA block, got {line!r}"
        )
    keyword = match.group(1).upper()
    if keyword not in _OBSERVATION_KEYWORD_SET:
        raise MalformedSourceError(f"unknown TDM observation keyword {keyword!r}")
    tokens = match.group(2).split()
    if len(tokens) != 2:
        raise MalformedSourceError(
            f"TDM observation {keyword!r} must be an epoch plus one value, got {line!r}"
        )
    try:
        value = float(tokens[1])
    except ValueError as exc:
        raise MalformedSourceError(
            f"TDM observation {keyword!r} value must be a number, got {tokens[1]!r}"
        ) from exc
    return TdmObservation(keyword=keyword, epoch=_parse_epoch(tokens[0]), value=value)


def _to_tracking(tdm: TdmFile) -> Tracking:
    """Adapt a :class:`TdmFile` into the canonical :class:`Tracking`.

    Flattens every segment's observations into one canonical sequence and tags the spine from
    the first segment's META (participants, time scale) and the header (originator). The whole
    :class:`TdmFile` rides along as ``source_native``, so the full per-segment metadata survives.
    """
    first = tdm.segments[0].meta
    observations = tuple(
        TrackingObservation(
            observation_type=observation.keyword,
            epoch=observation.epoch,
            value=observation.value,
        )
        for segment in tdm.segments
        for observation in segment.observations
    )
    time_system = first.get("TIME_SYSTEM")
    metadata = Metadata(
        originator=tdm.originator,
        time_scale=_canonical_time_scale(str(time_system)) if time_system is not None else None,
        provenance=Provenance(source_format="ccsds-tdm", creation_date=tdm.creation_date),
    )
    return Tracking(
        metadata=metadata,
        source_native=tdm,
        participants=_participants_of(first),
        observations=observations,
    )


def _participants_of(meta: TdmSegmentMeta) -> tuple[str, ...]:
    """The ordered ``PARTICIPANT_1`` … ``PARTICIPANT_5`` the segment carries, as strings."""
    participants: list[str] = []
    for index in range(1, 6):
        value = meta.get(f"PARTICIPANT_{index}")
        if value is not None:
            participants.append(str(value))
    return tuple(participants)


register_reader("ccsds-tdm", read_tdm)
