"""CCSDS APM reader — in-house parsing of the Attitude Parameter Message into a fidelity model.

The KVN reader is hand-written; the XML form is parsed through orbit-formats' own MIT xsdata
bindings (see :mod:`orbit_formats.adapters.apm_xml`). No GPL dependency is ever imported at
runtime. Both notations parse into the *same* faithful :class:`ApmFile` fidelity model — the
header, the metadata block, and the single attitude (a quaternion at one epoch, between two
reference frames, with optional rate) — which is adapted into a canonical
:class:`~orbit_formats.canonical.attitude.Attitude` of one row.

APM is the attitude analogue of OPM: a single record rather than a time series. This release
covers the quaternion attitude — the mandatory, dominant case (the Euler-angle, spin,
spacecraft-inertia, and maneuver blocks an APM may also carry are rejected with a clear error
rather than silently dropped); the AEM time series exercises the Euler and spin representations
of the shared :class:`Attitude` category. The KVN the wider ecosystem emits is version 1.0
(``Q_FRAME_A`` / ``Q_FRAME_B`` / ``Q_DIR`` in the quaternion block); the version-2 XML schema
expresses the same content with the frames on the quaternion state and the epoch at the data
level, so both notations parse into this one model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar, Literal

import numpy as np

from orbit_formats.canonical.attitude import Attitude
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import (
    _KEYWORD_RE,
    _canonical_time_scale,
    _comment_text,
    _is_comment,
    _parse_epoch,
)
from orbit_formats.readers.ccsds_omm import _kvn_float, _require
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["ApmFile", "ApmMetadata", "ApmQuaternion", "read_apm"]

_META_START = "META_START"
_META_STOP = "META_STOP"

# The data-section keywords the quaternion block defines. The four ``*_DOT`` rate keywords are
# optional (all-or-none). Any other data keyword — a Euler / spin / inertia / maneuver block —
# is unsupported in this release and rejected, never silently dropped.
_QUATERNION_KEYS = frozenset({"EPOCH", "Q_FRAME_A", "Q_FRAME_B", "Q_DIR", "Q1", "Q2", "Q3", "QC"})
_QUATERNION_RATE_KEYS = ("Q1_DOT", "Q2_DOT", "Q3_DOT", "QC_DOT")
_DATA_KEYS = _QUATERNION_KEYS | set(_QUATERNION_RATE_KEYS)


@dataclass(frozen=True, slots=True)
class ApmMetadata:
    """The APM metadata block — the object and time system the attitude is tagged with."""

    object_name: str
    object_id: str
    time_system: str
    center_name: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApmQuaternion:
    """The mandatory APM quaternion attitude — the rotation between two frames at one epoch.

    ``q_frame_a`` / ``q_frame_b`` are the frames the quaternion maps between and ``q_dir``
    (``A2B`` / ``B2A``) its direction; ``q1`` … ``qc`` are the components (scalar last). The
    four ``*_dot`` rate components are present together or not at all.
    """

    epoch: np.datetime64
    q_frame_a: str
    q_frame_b: str
    q1: float
    q2: float
    q3: float
    qc: float
    q_dir: str | None = None
    q1_dot: float | None = None
    q2_dot: float | None = None
    q3_dot: float | None = None
    qc_dot: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class ApmFile(FidelityModel):
    """The faithful APM fidelity model: the header, metadata, and the quaternion attitude.

    Holds every field a same-format APM write reconstructs from. ``raw_bytes`` is the verbatim
    source kept only when the read opted in via ``retain_source=True``; ``serialization``
    records the notation it was read from (``"kvn"`` or ``"xml"``) so a write re-emits in the
    same notation by default.
    """

    format_name: ClassVar[str] = "ccsds-apm"

    ccsds_version: str
    metadata: ApmMetadata
    quaternion: ApmQuaternion
    creation_date: str | None = None
    originator: str | None = None
    message_id: str | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_apm(source: Source) -> Attitude:
    """Read a CCSDS APM (KVN or XML) into a single-row canonical :class:`Attitude`.

    Parses the header, metadata, and quaternion block into an :class:`ApmFile` fidelity model,
    retained as ``source_native``, then adapts the quaternion into a one-row canonical
    attitude tagged with the two frames, time scale, and object id from the APM. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword, a
    malformed value or epoch, malformed XML, a partial quaternion-rate block, or an
    unsupported attitude block (Euler / spin / inertia / maneuver).

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.apm_xml import apmfile_from_xml

        apm = apmfile_from_xml(source.read_bytes())
    else:
        apm = _ApmKvnParser(text.splitlines()).parse()
    if source.retain:
        apm = replace(apm, raw_bytes=source.read_bytes())
    return _to_attitude(apm)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is an APM in XML rather than KVN — its first content is an XML tag."""
    return text.lstrip("﻿ \t\r\n").startswith("<")


class _ApmKvnParser:
    """A scanner over an APM's KVN lines: a header, a META block, then the quaternion block."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._i = 0

    def parse(self) -> ApmFile:
        header, header_comments = self._parse_header()
        meta, meta_comments = self._parse_meta()
        quaternion = self._parse_data()
        if "CCSDS_APM_VERS" not in header:
            raise MalformedSourceError(
                "not a CCSDS APM: the 'CCSDS_APM_VERS' header keyword is missing"
            )
        metadata = ApmMetadata(
            object_name=_require(meta, "OBJECT_NAME", "metadata"),
            object_id=_require(meta, "OBJECT_ID", "metadata"),
            time_system=_require(meta, "TIME_SYSTEM", "metadata"),
            center_name=meta.get("CENTER_NAME"),
            comments=tuple(meta_comments),
        )
        return ApmFile(
            ccsds_version=header["CCSDS_APM_VERS"],
            metadata=metadata,
            quaternion=quaternion,
            creation_date=header.get("CREATION_DATE"),
            originator=header.get("ORIGINATOR"),
            message_id=header.get("MESSAGE_ID"),
            comments=tuple(header_comments),
        )

    def _parse_header(self) -> tuple[dict[str, str], list[str]]:
        header: dict[str, str] = {}
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
            if key not in ("CCSDS_APM_VERS", "CREATION_DATE", "ORIGINATOR", "MESSAGE_ID"):
                raise MalformedSourceError(
                    f"unexpected keyword {key!r} in the APM header before META_START"
                )
            header[key] = value
        return header, comments

    def _parse_meta(self) -> tuple[dict[str, str], list[str]]:
        line = self._next()
        if line is None or line.strip().upper() != _META_START:
            got = "end of file" if line is None else repr(line.strip())
            raise MalformedSourceError(f"expected META_START in the APM, got {got}")
        meta: dict[str, str] = {}
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError("APM META block was not closed with META_STOP")
            stripped = line.strip()
            if stripped.upper() == _META_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            key, value = self._require_keyword(stripped, "metadata")
            if key not in ("OBJECT_NAME", "OBJECT_ID", "CENTER_NAME", "TIME_SYSTEM"):
                raise MalformedSourceError(f"unexpected APM META keyword {key!r}")
            meta[key] = value
        return meta, comments

    def _parse_data(self) -> ApmQuaternion:
        values: dict[str, str] = {}
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                break
            stripped = line.strip()
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            key, value = self._require_keyword(stripped, "quaternion block")
            if key not in _DATA_KEYS:
                raise MalformedSourceError(
                    f"unsupported APM data keyword {key!r}; this release supports the quaternion "
                    "attitude block only (Euler / spin / inertia / maneuver blocks are not yet "
                    "supported)"
                )
            values[key] = value
        return _build_quaternion(values, tuple(comments))

    def _require_keyword(self, line: str, where: str) -> tuple[str, str]:
        match = _KEYWORD_RE.match(line)
        if match is None:
            raise MalformedSourceError(
                f"expected 'KEYWORD = value' in the APM {where}, got {line!r}"
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


def _build_quaternion(values: dict[str, str], comments: tuple[str, ...]) -> ApmQuaternion:
    rates = _quaternion_rates(values)
    return ApmQuaternion(
        epoch=_parse_epoch(_require(values, "EPOCH", "quaternion block")),
        q_frame_a=_require(values, "Q_FRAME_A", "quaternion block"),
        q_frame_b=_require(values, "Q_FRAME_B", "quaternion block"),
        q1=_kvn_float(_require(values, "Q1", "quaternion block"), "Q1"),
        q2=_kvn_float(_require(values, "Q2", "quaternion block"), "Q2"),
        q3=_kvn_float(_require(values, "Q3", "quaternion block"), "Q3"),
        qc=_kvn_float(_require(values, "QC", "quaternion block"), "QC"),
        q_dir=values.get("Q_DIR"),
        q1_dot=rates[0],
        q2_dot=rates[1],
        q3_dot=rates[2],
        qc_dot=rates[3],
        comments=comments,
    )


def _quaternion_rates(
    values: dict[str, str],
) -> tuple[float | None, float | None, float | None, float | None]:
    present = [key for key in _QUATERNION_RATE_KEYS if key in values]
    if not present:
        return (None, None, None, None)
    if len(present) != len(_QUATERNION_RATE_KEYS):
        missing = [key for key in _QUATERNION_RATE_KEYS if key not in values]
        raise MalformedSourceError(
            f"APM quaternion rate is incomplete; missing {', '.join(missing)}"
        )
    return tuple(_kvn_float(values[key], key) for key in _QUATERNION_RATE_KEYS)  # type: ignore[return-value]


def _to_attitude(apm: ApmFile) -> Attitude:
    """Adapt an :class:`ApmFile` into a one-row canonical :class:`Attitude`.

    The quaternion becomes a single canonical record (scalar last); the frames, time scale,
    and object id tag the spine. The optional quaternion rate and the ``Q_DIR`` direction live
    on the fidelity model (``source_native``), so a same-format write recovers them.
    """
    q = apm.quaternion
    metadata = Metadata(
        object_name=apm.metadata.object_name,
        object_id=apm.metadata.object_id,
        originator=apm.originator,
        central_body=apm.metadata.center_name,
        time_scale=_canonical_time_scale(apm.metadata.time_system),
        provenance=Provenance(source_format="ccsds-apm", creation_date=apm.creation_date),
    )
    return Attitude(
        metadata=metadata,
        source_native=apm,
        attitude_type="QUATERNION",
        epochs=np.array([q.epoch], dtype="datetime64[ns]"),
        records=np.array([[q.q1, q.q2, q.q3, q.qc]], dtype=np.float64),
        frame_a=q.q_frame_a,
        frame_b=q.q_frame_b,
    )


register_reader("ccsds-apm", read_apm)
