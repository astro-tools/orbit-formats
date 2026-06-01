"""CCSDS APM writer — KVN and XML serialisers for the Attitude Parameter Message.

Three tiers, picked automatically (as for the OPM writer):

1. An ``Attitude`` whose ``source_native`` is an
   :class:`~orbit_formats.readers.ccsds_apm.ApmFile` with retained bytes → the verbatim bytes
   are echoed (**byte-identical**).
2. An ``ApmFile`` ``source_native`` without retained bytes → the structured fidelity model is
   re-serialised (**content-lossless** — the quaternion, its rate, and the comments preserved).
3. Any other single-row quaternion ``Attitude`` → an APM is built from the canonical attitude,
   warning for each APM-required field the canonical form cannot supply.

APM holds one quaternion attitude, so a multi-row attitude (an AEM time series) or a non-
quaternion representation cannot be written as an APM — the writer raises rather than dropping
rows or guessing. The notation is chosen from the destination extension (``.apm`` → KVN,
``.xml`` → XML), else the source's own notation, else KVN. The XML half lives in
:mod:`orbit_formats.adapters.apm_xml`, imported lazily.
"""

from __future__ import annotations

from typing import Literal

from orbit_formats.canonical.attitude import Attitude
from orbit_formats.canonical.base import Canonical
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_apm import ApmFile, ApmMetadata, ApmQuaternion
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _comment_lines, _format_epoch, _format_float

__all__ = ["write_apm"]

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".apm", ".kvn")

_APM_VERSION = "1.0"
_PLACEHOLDER = "UNKNOWN"


def write_apm(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a single quaternion :class:`Attitude`) to CCSDS APM bytes (KVN/XML).

    Picks the byte-identical / content-lossless / synthesised path automatically, and the KVN
    or XML notation from ``suffix`` else the source's own notation else KVN. Raises
    :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not an ``Attitude``,
    is not a single-row attitude, or is not a quaternion — APM holds one quaternion attitude.
    """
    if not isinstance(obj, Attitude):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-apm", "attitude")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, ApmFile):
        notation = requested or native.serialization
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_apmfile(native, notation)
    return _serialize_apmfile(_apmfile_from_attitude(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_apmfile(apm: ApmFile, notation: Literal["kvn", "xml"]) -> bytes:
    if notation == "xml":
        from orbit_formats.adapters.apm_xml import xml_bytes_from_apmfile

        return xml_bytes_from_apmfile(apm)
    return _serialize_apm_kvn(apm)


# --- synthesised APM from a canonical attitude -----------------------------------------


def _apmfile_from_attitude(attitude: Attitude) -> ApmFile:
    """Build an :class:`ApmFile` from a single quaternion ``Attitude``, warning on missing fields.

    Raises :class:`~orbit_formats.errors.UnsupportedConversionError` for a non-quaternion or
    multi-row attitude — APM holds one quaternion (an attitude time series is an AEM).
    """
    if attitude.attitude_type != "QUATERNION":
        raise UnsupportedConversionError(
            f"{attitude.attitude_type} attitude", "ccsds-apm", "attitude"
        )
    if len(attitude) != 1:
        raise UnsupportedConversionError(f"{len(attitude)}-state attitude", "ccsds-apm", "attitude")
    md = attitude.metadata
    metadata = ApmMetadata(
        object_name=_required("OBJECT_NAME", md.object_name),
        object_id=_required("OBJECT_ID", md.object_id),
        time_system=_required("TIME_SYSTEM", md.time_scale),
        center_name=md.central_body,
    )
    components = attitude.records[0]
    quaternion = ApmQuaternion(
        epoch=attitude.epochs[0],
        q_frame_a=_required("Q_FRAME_A", attitude.frame_a),
        q_frame_b=_required("Q_FRAME_B", attitude.frame_b),
        q1=float(components[0]),
        q2=float(components[1]),
        q3=float(components[2]),
        qc=float(components[3]),
    )
    return ApmFile(
        ccsds_version=_APM_VERSION,
        metadata=metadata,
        quaternion=quaternion,
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
    )


def _required(keyword: str, value: str | None) -> str:
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the attitude does not supply the APM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical attitude did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


# --- KVN serialisation -----------------------------------------------------------------


def _serialize_apm_kvn(apm: ApmFile) -> bytes:
    """Serialise an :class:`ApmFile` to canonical APM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_APM_VERS = {apm.ccsds_version}"]
    lines.extend(_comment_lines(apm.comments))
    if apm.creation_date is not None:
        lines.append(f"CREATION_DATE = {apm.creation_date}")
    if apm.originator is not None:
        lines.append(f"ORIGINATOR = {apm.originator}")
    if apm.message_id is not None:
        lines.append(f"MESSAGE_ID = {apm.message_id}")

    lines.append("")
    lines.append("META_START")
    lines.extend(_comment_lines(apm.metadata.comments))
    lines.extend(_serialize_metadata(apm.metadata))
    lines.append("META_STOP")

    lines.append("")
    lines.extend(_comment_lines(apm.quaternion.comments))
    lines.extend(_serialize_quaternion(apm.quaternion))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_metadata(meta: ApmMetadata) -> list[str]:
    ordered: tuple[tuple[str, str | None], ...] = (
        ("OBJECT_NAME", meta.object_name),
        ("OBJECT_ID", meta.object_id),
        ("CENTER_NAME", meta.center_name),
        ("TIME_SYSTEM", meta.time_system),
    )
    return [f"{key} = {value}" for key, value in ordered if value is not None]


def _serialize_quaternion(quaternion: ApmQuaternion) -> list[str]:
    out = [f"EPOCH = {_format_epoch(quaternion.epoch)}"]
    out.append(f"Q_FRAME_A = {quaternion.q_frame_a}")
    out.append(f"Q_FRAME_B = {quaternion.q_frame_b}")
    if quaternion.q_dir is not None:
        out.append(f"Q_DIR = {quaternion.q_dir}")
    out.extend(
        f"{key} = {_format_float(value)}"
        for key, value in (
            ("Q1", quaternion.q1),
            ("Q2", quaternion.q2),
            ("Q3", quaternion.q3),
            ("QC", quaternion.qc),
        )
    )
    rates = (
        ("Q1_DOT", quaternion.q1_dot),
        ("Q2_DOT", quaternion.q2_dot),
        ("Q3_DOT", quaternion.q3_dot),
        ("QC_DOT", quaternion.qc_dot),
    )
    out.extend(f"{key} = {_format_float(value)}" for key, value in rates if value is not None)
    return out


register_writer("ccsds-apm", write_apm)
