"""CCSDS TDM writer — KVN and XML serialisers for the Tracking Data Message.

Three tiers, picked automatically (as for the OEM/AEM writers):

1. A ``Tracking`` whose ``source_native`` is a
   :class:`~orbit_formats.readers.ccsds_tdm.TdmFile` with retained bytes → the verbatim bytes
   are echoed (**byte-identical**).
2. A ``TdmFile`` ``source_native`` without retained bytes → the structured fidelity model is
   re-serialised (**content-lossless** — every segment, the full META, every observation and
   comment preserved).
3. Any other ``Tracking`` → a TDM is built from the canonical tracking set, warning for each
   TDM-required META field the canonical form cannot supply.

The notation is chosen from the destination extension (``.tdm`` → KVN, ``.xml`` → XML), else
the source's own notation, else KVN. The XML half lives in
:mod:`orbit_formats.adapters.tdm_xml`, imported lazily.
"""

from __future__ import annotations

from typing import Literal

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.tracking import Tracking
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_tdm import (
    _META_FIELDS,
    MetaValue,
    TdmFile,
    TdmObservation,
    TdmSegment,
    TdmSegmentMeta,
    ordered_meta,
)
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _comment_lines, _format_epoch, _format_float

__all__ = ["write_tdm"]

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".tdm", ".kvn")

# The TDM version the synthesised / re-serialised KVN header declares, and the placeholder a
# synthesised file uses where the canonical tracking set cannot supply a required META value.
_TDM_VERSION = "1.0"
_PLACEHOLDER = "UNKNOWN"


def write_tdm(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`Tracking`) to CCSDS TDM bytes, in KVN or XML.

    Picks the byte-identical / content-lossless / synthesised path automatically, and the KVN
    or XML notation from ``suffix`` (the destination extension) else the source's own notation
    else KVN. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not
    a ``Tracking`` — TDM is a tracking format.
    """
    if not isinstance(obj, Tracking):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-tdm", "tracking")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, TdmFile):
        notation = requested or native.serialization
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_tdmfile(native, notation)
    return _serialize_tdmfile(_tdmfile_from_tracking(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_tdmfile(tdm: TdmFile, notation: Literal["kvn", "xml"]) -> bytes:
    if notation == "xml":
        from orbit_formats.adapters.tdm_xml import xml_bytes_from_tdm

        return xml_bytes_from_tdm(tdm)
    return _serialize_tdm_kvn(tdm)


# --- synthesised TDM from a canonical tracking set -------------------------------------


def _tdmfile_from_tracking(tracking: Tracking) -> TdmFile:
    """Build a :class:`TdmFile` from a canonical ``Tracking``, warning on missing fields.

    Each TDM-required META field the canonical form cannot supply is written as a placeholder
    and reported, so a synthesised TDM is structurally valid yet never silently incomplete.
    The whole tracking set becomes one segment.
    """
    md = tracking.metadata
    participant_1 = tracking.participants[0] if tracking.participants else None
    typed: dict[str, MetaValue] = {
        "TIME_SYSTEM": _resolve_required("TIME_SYSTEM", md.time_scale),
        "PARTICIPANT_1": _resolve_required("PARTICIPANT_1", participant_1),
    }
    for index, participant in enumerate(tracking.participants[1:], start=2):
        typed[f"PARTICIPANT_{index}"] = participant

    meta = TdmSegmentMeta(values=ordered_meta(typed))
    observations = tuple(
        TdmObservation(
            keyword=observation.observation_type,
            epoch=observation.epoch,
            value=observation.value,
        )
        for observation in tracking.observations
    )
    segment = TdmSegment(meta=meta, observations=observations)
    return TdmFile(
        ccsds_version=_TDM_VERSION,
        segments=(segment,),
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
    )


def _resolve_required(keyword: str, value: str | None) -> str:
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the tracking set does not supply the TDM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical tracking set did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


# --- KVN serialisation -----------------------------------------------------------------


def _serialize_tdm_kvn(tdm: TdmFile) -> bytes:
    """Serialise a :class:`TdmFile` to canonical TDM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_TDM_VERS = {tdm.ccsds_version}"]
    if tdm.creation_date is not None:
        lines.append(f"CREATION_DATE = {tdm.creation_date}")
    if tdm.originator is not None:
        lines.append(f"ORIGINATOR = {tdm.originator}")
    if tdm.message_id is not None:
        lines.append(f"MESSAGE_ID = {tdm.message_id}")
    lines.extend(_comment_lines(tdm.comments))
    for segment in tdm.segments:
        lines.append("")
        lines.extend(_serialize_segment(segment))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_segment(segment: TdmSegment) -> list[str]:
    out: list[str] = ["META_START"]
    out.extend(_comment_lines(segment.meta.comments))
    out.extend(_serialize_meta(segment.meta))
    out.append("META_STOP")
    out.append("")
    out.append("DATA_START")
    out.extend(_comment_lines(segment.comments))
    for observation in segment.observations:
        out.append(_serialize_observation(observation))
    out.append("DATA_STOP")
    return out


def _serialize_meta(meta: TdmSegmentMeta) -> list[str]:
    # CCSDS 503.0-B-2 META keyword order; only keywords the segment actually carries are emitted.
    present = dict(meta.values)
    out: list[str] = []
    for keyword, kind in _META_FIELDS:
        if keyword in present:
            out.append(f"{keyword} = {_format_meta_value(present[keyword], kind)}")
    return out


def _format_meta_value(value: MetaValue, kind: str) -> str:
    if kind == "float":
        return _format_float(float(value))
    return str(value)


def _serialize_observation(observation: TdmObservation) -> str:
    epoch = _format_epoch(observation.epoch)
    return f"{observation.keyword} = {epoch} {_format_float(observation.value)}"


register_writer("ccsds-tdm", write_tdm)
