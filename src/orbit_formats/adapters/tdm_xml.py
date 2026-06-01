"""The TDM-XML mapping: the xsdata ``Tdm`` binding ↔ the :class:`TdmFile` fidelity model.

The TDM-specific half of the CCSDS-XML seam (the generic plumbing lives in
:mod:`orbit_formats.adapters.ccsds_xml`). Maps the populated
:class:`~orbit_formats._ccsds_xsd.Tdm` binding to and from the *same*
:class:`~orbit_formats.readers.ccsds_tdm.TdmFile` the hand-written KVN reader produces, so a
TDM read from either notation is the same model — the precondition for the KVN↔XML parity
assertion. Imported lazily (only when a TDM in XML is read or written), never at package
import time.

TDM is version 2.0 (CCSDS 503.0-B-2) in both notations — the ndmxml 2.0 bindings and the KVN
orbit-formats writes share that version — so there is no version-skew carve-out: the two
notations carry identical content, shaped only by the XML schema's typed elements (enum tokens,
the ``ANGLE_1`` / ``ANGLE_2`` / ``RHUMIDITY`` value+units wrappers) vs KVN's plain
keyword-value text. The META and observation vocabularies are driven by the same
:data:`~orbit_formats.readers.ccsds_tdm._META_FIELDS` and
:data:`~orbit_formats.readers.ccsds_tdm.OBSERVATION_KEYWORDS` tables the KVN reader uses, so the
mapping stays symmetric by construction.
"""

from __future__ import annotations

from typing import Any

from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    AngleType,
    AngleTypeType,
    DataQualityType,
    IntegrationRefType,
    ModeType,
    PercentageTypeUo,
    RangemodeType,
    RangeUnitsType,
    RefFrameType,
    Tdm,
    TdmBody,
    TdmData,
    TdmHeader,
    TdmMetadata,
    TimetagRefType,
    TrackingDataObservationType,
    YesNoType,
)
from orbit_formats._ccsds_xsd import (
    TdmSegment as XmlTdmSegment,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.adapters.oem_xml import _require_for_xml
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import _parse_epoch
from orbit_formats.readers.ccsds_tdm import (
    _META_FIELDS,
    OBSERVATION_KEYWORDS,
    MetaValue,
    TdmFile,
    TdmObservation,
    TdmSegment,
    TdmSegmentMeta,
    ordered_meta,
)
from orbit_formats.writers.oem import _format_epoch

__all__ = ["tdmfile_from_xml", "xml_bytes_from_tdm"]

# The TDM META enum keywords mapped to their binding enum type, so a KVN-stored token
# round-trips through the schema's typed element. Every other META keyword is a plain
# string / int / float and maps verbatim.
_META_ENUMS: dict[str, Any] = {
    "MODE": ModeType,
    "TIMETAG_REF": TimetagRefType,
    "INTEGRATION_REF": IntegrationRefType,
    "RANGE_MODE": RangemodeType,
    "RANGE_UNITS": RangeUnitsType,
    "ANGLE_TYPE": AngleTypeType,
    "REFERENCE_FRAME": RefFrameType,
    "DOPPLER_COUNT_ROLLOVER": YesNoType,
    "DATA_QUALITY": DataQualityType,
    "CORRECTIONS_APPLIED": YesNoType,
}

# The observation keywords whose XML element is a value+units wrapper rather than a bare float.
_OBS_WRAPPED: dict[str, Any] = {
    "ANGLE_1": AngleType,
    "ANGLE_2": AngleType,
    "RHUMIDITY": PercentageTypeUo,
}


# --- XML -> TdmFile --------------------------------------------------------------------


def tdmfile_from_xml(data: bytes) -> TdmFile:
    """Parse TDM XML ``data`` into a :class:`TdmFile`, tagged ``serialization="xml"``."""
    try:
        tdm = parse_ndm_xml(data, Tdm)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the TDM XML: {exc}") from exc

    segments = tuple(_segment_from_xml(segment) for segment in tdm.body.segment)
    if not segments:
        raise MalformedSourceError("not a valid TDM: the XML body has no segment")
    return TdmFile(
        ccsds_version=tdm.version,
        segments=segments,
        creation_date=tdm.header.creation_date,
        originator=tdm.header.originator,
        message_id=tdm.header.message_id,
        comments=tuple(tdm.header.comment),
        serialization="xml",
    )


def _segment_from_xml(segment: Any) -> TdmSegment:
    return TdmSegment(
        meta=_meta_from_xml(segment.metadata),
        observations=_observations_from_xml(segment.data),
        comments=tuple(segment.data.comment),
    )


def _meta_from_xml(meta: Any) -> TdmSegmentMeta:
    typed: dict[str, MetaValue] = {}
    for keyword, _kind in _META_FIELDS:
        value = getattr(meta, keyword.lower(), None)
        if value is None:
            continue
        typed[keyword] = str(value.value) if keyword in _META_ENUMS else value
    return TdmSegmentMeta(values=ordered_meta(typed), comments=tuple(meta.comment))


def _observations_from_xml(data: Any) -> tuple[TdmObservation, ...]:
    observations: list[TdmObservation] = []
    for entry in data.observation:
        epoch = _parse_epoch(entry.epoch)
        found = False
        for keyword in OBSERVATION_KEYWORDS:
            value = getattr(entry, keyword.lower(), None)
            if value is None:
                continue
            scalar = float(value.value) if keyword in _OBS_WRAPPED else float(value)
            observations.append(TdmObservation(keyword=keyword, epoch=epoch, value=scalar))
            found = True
        if not found:
            raise MalformedSourceError(
                "a TDM XML observation carries no recognised measurement value"
            )
    return tuple(observations)


# --- TdmFile -> XML --------------------------------------------------------------------


def xml_bytes_from_tdm(tdm: TdmFile) -> bytes:
    """Serialise a :class:`TdmFile` to schema-valid TDM XML bytes.

    The mirror of :func:`tdmfile_from_xml`. TDM XML requires the header ``CREATION_DATE`` and
    ``ORIGINATOR`` that KVN treats as optional on the model; when one is absent a placeholder is
    written and reported, never dropped silently.
    """
    header = TdmHeader(
        comment=list(tdm.comments),
        creation_date=_require_for_xml("CREATION_DATE", tdm.creation_date),
        originator=_require_for_xml("ORIGINATOR", tdm.originator),
        message_id=tdm.message_id,
    )
    body = TdmBody(segment=[_segment_to_xml(segment) for segment in tdm.segments])
    return serialize_ndm_xml(Tdm(header=header, body=body))


def _segment_to_xml(segment: TdmSegment) -> Any:
    return XmlTdmSegment(metadata=_meta_to_xml(segment.meta), data=_data_to_xml(segment))


def _meta_to_xml(meta: TdmSegmentMeta) -> Any:
    kwargs: dict[str, Any] = {"comment": list(meta.comments)}
    for keyword, value in meta.values:
        attribute = keyword.lower()
        kwargs[attribute] = _META_ENUMS[keyword](str(value)) if keyword in _META_ENUMS else value
    return TdmMetadata(**kwargs)


def _data_to_xml(segment: TdmSegment) -> Any:
    return TdmData(
        comment=list(segment.comments),
        observation=[_observation_to_xml(observation) for observation in segment.observations],
    )


def _observation_to_xml(observation: TdmObservation) -> Any:
    attribute = observation.keyword.lower()
    wrapper = _OBS_WRAPPED.get(observation.keyword)
    value = wrapper(value=observation.value) if wrapper is not None else observation.value
    return TrackingDataObservationType(epoch=_format_epoch(observation.epoch), **{attribute: value})
