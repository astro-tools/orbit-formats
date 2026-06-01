"""CCSDS AEM writer — KVN and XML serialisers for the Attitude Ephemeris Message.

Three tiers, picked automatically (as for the OEM writer):

1. An ``Attitude`` whose ``source_native`` is an
   :class:`~orbit_formats.readers.ccsds_aem.AemFile` with retained bytes → the verbatim bytes
   are echoed (**byte-identical**).
2. An ``AemFile`` ``source_native`` without retained bytes → the structured fidelity model is
   re-serialised (**content-lossless** — every segment, the full META, comments preserved).
3. Any other ``Attitude`` → an AEM is built from the canonical attitude, warning for each
   AEM-required META field the canonical form cannot supply.

The notation is chosen from the destination extension (``.aem`` → KVN, ``.xml`` → XML), else
the source's own notation, else KVN. The KVN it emits is version 1.0 (with the ``ATTITUDE_DIR``
and ``QUATERNION_TYPE`` notation tags); the XML half lives in
:mod:`orbit_formats.adapters.aem_xml`, imported lazily.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from orbit_formats.canonical.attitude import Attitude
from orbit_formats.canonical.base import Canonical
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_aem import AemFile, AemSegment, AemSegmentMeta
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _comment_lines, _format_epoch, _format_float

__all__ = ["write_aem"]

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".aem", ".kvn")

# The AEM version the synthesised / re-serialised KVN header declares, and the placeholder a
# synthesised file uses where the canonical attitude cannot supply a required META value.
_AEM_VERSION = "1.0"
_PLACEHOLDER = "UNKNOWN"

# The mandatory META keywords sourced from the canonical attitude / its metadata spine when
# synthesising an AEM (START_TIME / STOP_TIME come from the epochs, ATTITUDE_TYPE / the frames
# from the attitude itself).
_REQUIRED_FROM_METADATA = (
    ("OBJECT_NAME", "object_name"),
    ("OBJECT_ID", "object_id"),
    ("TIME_SYSTEM", "time_scale"),
)


def write_aem(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (an :class:`Attitude`) to CCSDS AEM bytes, in KVN or XML.

    Picks the byte-identical / content-lossless / synthesised path automatically, and the KVN
    or XML notation from ``suffix`` (the destination extension) else the source's own notation
    else KVN. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is
    not an ``Attitude`` — AEM is an attitude format.
    """
    if not isinstance(obj, Attitude):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-aem", "attitude")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, AemFile):
        notation = requested or native.serialization
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_aemfile(native, notation)
    return _serialize_aemfile(_aemfile_from_attitude(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_aemfile(aem: AemFile, notation: Literal["kvn", "xml"]) -> bytes:
    if notation == "xml":
        from orbit_formats.adapters.aem_xml import xml_bytes_from_aemfile

        return xml_bytes_from_aemfile(aem)
    return _serialize_aem_kvn(aem)


# --- synthesised AEM from a canonical attitude -----------------------------------------


def _aemfile_from_attitude(attitude: Attitude) -> AemFile:
    """Build an :class:`AemFile` from a canonical ``Attitude``, warning on missing fields.

    Each AEM-required META field the canonical form cannot supply is written as a placeholder
    and reported, so a synthesised AEM is structurally valid yet never silently incomplete.
    A quaternion attitude defaults to the ``LAST`` (scalar-last) notation — the order the
    canonical records already use — so no quaternion is reordered.
    """
    md = attitude.metadata
    count = len(attitude)
    start_time = _format_epoch(attitude.epochs[0]) if count else None
    stop_time = _format_epoch(attitude.epochs[-1]) if count else None

    resolved: dict[str, str] = {}
    for keyword, attribute in _REQUIRED_FROM_METADATA:
        resolved[keyword] = _resolve_required(keyword, getattr(md, attribute))
    resolved["REF_FRAME_A"] = _resolve_required("REF_FRAME_A", attitude.frame_a)
    resolved["REF_FRAME_B"] = _resolve_required("REF_FRAME_B", attitude.frame_b)
    resolved["START_TIME"] = _resolve_required("START_TIME", start_time)
    resolved["STOP_TIME"] = _resolve_required("STOP_TIME", stop_time)

    meta = AemSegmentMeta(
        object_name=resolved["OBJECT_NAME"],
        object_id=resolved["OBJECT_ID"],
        ref_frame_a=resolved["REF_FRAME_A"],
        ref_frame_b=resolved["REF_FRAME_B"],
        time_system=resolved["TIME_SYSTEM"],
        start_time=resolved["START_TIME"],
        stop_time=resolved["STOP_TIME"],
        attitude_type=attitude.attitude_type,
        center_name=md.central_body,
        quaternion_type="LAST" if attitude.attitude_type == "QUATERNION" else None,
        euler_rot_seq=attitude.euler_rot_seq,
    )
    segment = AemSegment(meta=meta, epochs=attitude.epochs, records=attitude.records)
    return AemFile(
        ccsds_version=_AEM_VERSION,
        segments=(segment,),
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
    )


def _resolve_required(keyword: str, value: str | None) -> str:
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the attitude does not supply the AEM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical attitude did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


# --- KVN serialisation -----------------------------------------------------------------


def _serialize_aem_kvn(aem: AemFile) -> bytes:
    """Serialise an :class:`AemFile` to canonical AEM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_AEM_VERS = {aem.ccsds_version}"]
    if aem.creation_date is not None:
        lines.append(f"CREATION_DATE = {aem.creation_date}")
    if aem.originator is not None:
        lines.append(f"ORIGINATOR = {aem.originator}")
    lines.extend(_comment_lines(aem.comments))
    for segment in aem.segments:
        lines.append("")
        lines.extend(_serialize_segment(segment))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_segment(segment: AemSegment) -> list[str]:
    out: list[str] = ["META_START"]
    out.extend(_comment_lines(segment.meta.comments))
    out.extend(_serialize_meta(segment.meta))
    out.append("META_STOP")
    out.append("")
    out.append("DATA_START")
    out.extend(_comment_lines(segment.comments))
    for index in range(len(segment.epochs)):
        out.append(_serialize_record(segment, index))
    out.append("DATA_STOP")
    return out


def _serialize_meta(meta: AemSegmentMeta) -> list[str]:
    # CCSDS 504.0-B META keyword order; only keywords the segment actually carries are emitted.
    degree = None if meta.interpolation_degree is None else str(meta.interpolation_degree)
    ordered: tuple[tuple[str, str | None], ...] = (
        ("OBJECT_NAME", meta.object_name),
        ("OBJECT_ID", meta.object_id),
        ("CENTER_NAME", meta.center_name),
        ("REF_FRAME_A", meta.ref_frame_a),
        ("REF_FRAME_B", meta.ref_frame_b),
        ("ATTITUDE_DIR", meta.attitude_dir),
        ("TIME_SYSTEM", meta.time_system),
        ("START_TIME", meta.start_time),
        ("USEABLE_START_TIME", meta.useable_start_time),
        ("USEABLE_STOP_TIME", meta.useable_stop_time),
        ("STOP_TIME", meta.stop_time),
        ("ATTITUDE_TYPE", meta.attitude_type),
        ("QUATERNION_TYPE", meta.quaternion_type),
        ("EULER_ROT_SEQ", meta.euler_rot_seq),
        ("INTERPOLATION_METHOD", meta.interpolation_method),
        ("INTERPOLATION_DEGREE", degree),
    )
    return [f"{key} = {value}" for key, value in ordered if value is not None]


def _serialize_record(segment: AemSegment, index: int) -> str:
    components = segment.records[index]
    if segment.meta.attitude_type == "QUATERNION" and segment.meta.quaternion_type == "FIRST":
        # The canonical record is scalar-last (Q1 Q2 Q3 QC); FIRST writes the scalar first.
        components = np.array(
            [components[3], components[0], components[1], components[2]], dtype=np.float64
        )
    parts = [_format_epoch(segment.epochs[index])]
    parts.extend(_format_float(value) for value in components)
    return " ".join(parts)


register_writer("ccsds-aem", write_aem)
