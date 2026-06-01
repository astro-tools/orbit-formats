"""CCSDS OCM writer — KVN and XML serialisers for the Orbit Comprehensive Message.

Three tiers, picked automatically (as for the OEM / TDM writers):

1. An ``Ephemeris`` whose ``source_native`` is an
   :class:`~orbit_formats.readers.ccsds_ocm.OcmFile` with retained bytes → the verbatim bytes
   are echoed (**byte-identical**).
2. An ``OcmFile`` ``source_native`` without retained bytes → the structured fidelity model is
   re-serialised (**content-lossless** — every block, keyword, data line, and comment
   preserved, canonically formatted).
3. Any other ``Ephemeris`` → an OCM is synthesised from the canonical ephemeris (one Cartesian
   trajectory block), warning for each OCM-required field the canonical form cannot supply.

The notation is chosen from the destination extension (``.ocm`` → KVN, ``.xml`` → XML), else
the source's own notation, else KVN. The XML half lives in
:mod:`orbit_formats.adapters.ocm_xml`, imported lazily so a KVN-only write never touches the
xsdata bindings.
"""

from __future__ import annotations

from typing import Literal

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_ocm import (
    _COV_FIELDS,
    _MAN_FIELDS,
    _METADATA_FIELDS,
    _OD_FIELDS,
    _PERT_FIELDS,
    _PHYS_FIELDS,
    _TRAJ_FIELDS,
    FieldValue,
    OcmFile,
    OcmKeywordBlock,
    OcmTrajectoryBlock,
    OcmUserDefined,
    _FieldTable,
    _ordered,
    format_field,
)
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _comment_lines, _format_epoch, _format_float

__all__ = ["write_ocm"]

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".ocm", ".kvn")

# The OCM version the synthesised / re-serialised KVN header declares (fixed at 3.0 by the
# schema), and the placeholder a synthesised file uses where the ephemeris cannot supply a
# required value.
_OCM_VERSION = "3.0"
_PLACEHOLDER = "UNKNOWN"


def write_ocm(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (an :class:`Ephemeris`) to CCSDS OCM bytes, in KVN or XML.

    Picks the byte-identical / content-lossless / synthesised path automatically, and the KVN
    or XML notation from ``suffix`` (the destination extension) else the source's own notation
    else KVN. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not
    an ``Ephemeris`` — OCM is an ephemeris format, and converting another canonical form to it
    is the conversion layer's job, not the writer's.
    """
    if not isinstance(obj, Ephemeris):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-ocm", "ephemeris")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, OcmFile):
        notation = requested or native.serialization
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_ocmfile(native, notation)
    return _serialize_ocmfile(_ocmfile_from_ephemeris(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_ocmfile(ocm: OcmFile, notation: Literal["kvn", "xml"]) -> bytes:
    if notation == "xml":
        from orbit_formats.adapters.ocm_xml import xml_bytes_from_ocm

        return xml_bytes_from_ocm(ocm)
    return _serialize_ocm_kvn(ocm)


# --- synthesised OCM from a canonical ephemeris ----------------------------------------


def _ocmfile_from_ephemeris(eph: Ephemeris) -> OcmFile:
    """Build an :class:`OcmFile` from a canonical ``Ephemeris``, warning on missing fields.

    The ephemeris becomes one Cartesian (``CARTPV``) trajectory block timed against
    ``EPOCH_TZERO`` (the first epoch). Each OCM-required field the canonical form cannot supply
    is written as a placeholder and reported, so a synthesised OCM is structurally valid yet
    never silently incomplete.
    """
    md = eph.metadata
    count = len(eph)
    tzero = _format_epoch(eph.epochs[0]) if count else None

    meta_values: dict[str, FieldValue] = {
        "TIME_SYSTEM": _resolve_required("TIME_SYSTEM", md.time_scale),
        "EPOCH_TZERO": _resolve_required("EPOCH_TZERO", tzero),
    }
    if md.object_name is not None:
        meta_values["OBJECT_NAME"] = md.object_name
    if md.object_id is not None:
        meta_values["INTERNATIONAL_DESIGNATOR"] = md.object_id
    metadata = OcmKeywordBlock(fields=_ordered(meta_values, _METADATA_FIELDS))

    traj_values: dict[str, FieldValue] = {
        "CENTER_NAME": _resolve_required("CENTER_NAME", md.central_body),
        "TRAJ_REF_FRAME": _resolve_required("TRAJ_REF_FRAME", md.reference_frame),
        "TRAJ_TYPE": "CARTPV",
    }
    if eph.interpolation is not None:
        traj_values["INTERPOLATION"] = eph.interpolation
    if eph.interpolation_degree is not None:
        traj_values["INTERPOLATION_DEGREE"] = eph.interpolation_degree
    lines = tuple(_synth_traj_line(eph, index) for index in range(count))
    trajectory = OcmTrajectoryBlock(fields=_ordered(traj_values, _TRAJ_FIELDS), lines=lines)

    return OcmFile(
        ccsds_version=_OCM_VERSION,
        metadata=metadata,
        trajectories=(trajectory,),
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
    )


def _synth_traj_line(eph: Ephemeris, index: int) -> str:
    parts = [_format_epoch(eph.epochs[index])]
    parts.extend(_format_float(value) for value in eph.positions[index])
    parts.extend(_format_float(value) for value in eph.velocities[index])
    return " ".join(parts)


def _resolve_required(keyword: str, value: str | None) -> str:
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the ephemeris does not supply the OCM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical ephemeris did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


# --- KVN serialisation -----------------------------------------------------------------


def _serialize_ocm_kvn(ocm: OcmFile) -> bytes:
    """Serialise an :class:`OcmFile` to canonical OCM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_OCM_VERS = {ocm.ccsds_version}"]
    if ocm.classification is not None:
        lines.append(f"CLASSIFICATION = {ocm.classification}")
    if ocm.creation_date is not None:
        lines.append(f"CREATION_DATE = {ocm.creation_date}")
    if ocm.originator is not None:
        lines.append(f"ORIGINATOR = {ocm.originator}")
    if ocm.message_id is not None:
        lines.append(f"MESSAGE_ID = {ocm.message_id}")
    lines.extend(_comment_lines(ocm.comments))

    lines.append("")
    lines.extend(
        _serialize_keyword_block("META_START", "META_STOP", ocm.metadata, _METADATA_FIELDS)
    )
    for trajectory in ocm.trajectories:
        lines.append("")
        lines.extend(
            _serialize_data_block(
                "TRAJ_START",
                "TRAJ_STOP",
                trajectory.fields,
                trajectory.lines,
                trajectory.comments,
                _TRAJ_FIELDS,
            )
        )
    if ocm.physical is not None:
        lines.append("")
        lines.extend(
            _serialize_keyword_block("PHYS_START", "PHYS_STOP", ocm.physical, _PHYS_FIELDS)
        )
    for covariance in ocm.covariances:
        lines.append("")
        lines.extend(
            _serialize_data_block(
                "COV_START",
                "COV_STOP",
                covariance.fields,
                covariance.lines,
                covariance.comments,
                _COV_FIELDS,
            )
        )
    for maneuver in ocm.maneuvers:
        lines.append("")
        lines.extend(
            _serialize_data_block(
                "MAN_START",
                "MAN_STOP",
                maneuver.fields,
                maneuver.lines,
                maneuver.comments,
                _MAN_FIELDS,
            )
        )
    if ocm.perturbations is not None:
        lines.append("")
        lines.extend(
            _serialize_keyword_block("PERT_START", "PERT_STOP", ocm.perturbations, _PERT_FIELDS)
        )
    if ocm.orbit_determination is not None:
        lines.append("")
        lines.extend(
            _serialize_keyword_block("OD_START", "OD_STOP", ocm.orbit_determination, _OD_FIELDS)
        )
    if ocm.user_defined is not None:
        lines.append("")
        lines.extend(_serialize_user(ocm.user_defined))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_keyword_block(
    start: str, stop: str, block: OcmKeywordBlock, table: _FieldTable
) -> list[str]:
    kinds = dict(table)
    out: list[str] = [start]
    out.extend(_comment_lines(block.comments))
    out.extend(
        f"{keyword} = {format_field(kinds[keyword], value)}" for keyword, value in block.fields
    )
    out.append(stop)
    return out


def _serialize_data_block(
    start: str,
    stop: str,
    fields: tuple[tuple[str, FieldValue], ...],
    data_lines: tuple[str, ...],
    comments: tuple[str, ...],
    table: _FieldTable,
) -> list[str]:
    kinds = dict(table)
    out: list[str] = [start]
    out.extend(_comment_lines(comments))
    out.extend(f"{keyword} = {format_field(kinds[keyword], value)}" for keyword, value in fields)
    out.extend(data_lines)
    out.append(stop)
    return out


def _serialize_user(user: OcmUserDefined) -> list[str]:
    out: list[str] = ["USER_START"]
    out.extend(_comment_lines(user.comments))
    out.extend(f"USER_DEFINED_{key} = {value}" for key, value in user.parameters)
    out.append("USER_STOP")
    return out


register_writer("ccsds-ocm", write_ocm)
