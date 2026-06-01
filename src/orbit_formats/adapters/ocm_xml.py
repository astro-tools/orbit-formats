"""The OCM-XML mapping: the xsdata ``Ocm`` binding ↔ the :class:`OcmFile` fidelity model.

This is the OCM-specific half of the CCSDS-XML seam. The generic plumbing — NDM/XML bytes ↔ a
populated binding — lives in :mod:`orbit_formats.adapters.ccsds_xml`; here we map the populated
:class:`~orbit_formats._ccsds_xsd.Ocm` binding to and from the *same*
:class:`~orbit_formats.readers.ccsds_ocm.OcmFile` the hand-written KVN reader produces.

OCM has the widest keyword surface of any NDM member, so rather than hand-map every field the
adapter derives a :class:`_FieldSpec` per keyword by introspecting each block binding once:
the XML element name (the KVN keyword), the binding attribute, and the value's kind (plain
text, integer, float, an enum token, a dimensioned value, or a numeric vector). Those specs
drive a single generic conversion both ways, so a new OCM keyword needs no adapter change — it
travels as soon as the vendored bindings carry it. The kinds match the declarative tables the
KVN reader uses (:mod:`orbit_formats.readers.ccsds_ocm`), the precondition for KVN ↔ XML parity.

The module imports the large generated binding module, so it is imported lazily (only when an
OCM in XML is actually read or written), never at package import time.
"""

from __future__ import annotations

import dataclasses
import enum
import types
import typing
from typing import Any, Union

from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    Ocm,
    OcmBody,
    OcmCovarianceMatrixType,
    OcmData,
    OcmManeuverParametersType,
    OcmMetadata,
    OcmOdParametersType,
    OcmPerturbationsType,
    OcmPhysicalDescriptionType,
    OcmSegment,
    OcmTrajStateType,
    OdmHeader,
    UserDefinedParameterType,
    UserDefinedType,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.adapters.oem_xml import _require_for_xml
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds_ocm import (
    FieldValue,
    OcmCovarianceBlock,
    OcmFile,
    OcmKeywordBlock,
    OcmManeuverBlock,
    OcmTrajectoryBlock,
    OcmUserDefined,
    Quantity,
)

__all__ = ["ocmfile_from_xml", "xml_bytes_from_ocm"]


# --- per-block field specs, derived from the bindings ----------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class _FieldSpec:
    """How one OCM keyword maps between the binding and the fidelity model's typed value."""

    keyword: str  # the XML element name == the KVN keyword
    attr: str  # the binding's Python attribute
    kind: str  # "str" | "int" | "float" | "enum" | "quantity" | "vec3"
    concrete: Any  # the enum / dimensioned-value binding class (else None)
    units_enum: Any  # the units enum for a dimensioned value (else None)


def _unwrap_optional(annotation: Any) -> Any:
    """Strip ``Optional[X]`` / ``X | None`` down to ``X`` (other unions pass through)."""
    if typing.get_origin(annotation) in (Union, types.UnionType):
        args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _classify(annotation: Any) -> tuple[str, Any, Any]:
    """Classify a binding field's resolved type into a (kind, concrete, units_enum) triple."""
    resolved = _unwrap_optional(annotation)
    if typing.get_origin(resolved) is list:
        (inner,) = typing.get_args(resolved)
        if inner is float:
            return "vec3", None, None
        raise TypeError(f"unexpected OCM list field type {resolved!r}")
    if resolved is str:
        return "str", None, None
    if resolved is int:
        return "int", None, None
    if resolved is float:
        return "float", None, None
    if isinstance(resolved, type) and issubclass(resolved, enum.Enum):
        return "enum", resolved, None
    if dataclasses.is_dataclass(resolved):
        hints = typing.get_type_hints(resolved)
        units_enum = _unwrap_optional(hints["units"]) if "units" in hints else None
        return "quantity", resolved, units_enum
    raise TypeError(f"unhandled OCM binding field type {resolved!r}")


def _specs(binding_cls: type) -> tuple[_FieldSpec, ...]:
    """The ordered keyword specs of a block binding, excluding comments and free-form lines."""
    hints = typing.get_type_hints(binding_cls)
    specs: list[_FieldSpec] = []
    for f in dataclasses.fields(binding_cls):
        metadata = f.metadata
        if metadata.get("type") == "Attribute":
            continue
        keyword = str(metadata.get("name") or f.name.upper())
        if f.name == "comment" or keyword in ("trajLine", "covLine", "manLine"):
            continue
        kind, concrete, units_enum = _classify(hints[f.name])
        specs.append(_FieldSpec(keyword, f.name, kind, concrete, units_enum))
    return tuple(specs)


_META_SPECS = _specs(OcmMetadata)
_TRAJ_SPECS = _specs(OcmTrajStateType)
_COV_SPECS = _specs(OcmCovarianceMatrixType)
_MAN_SPECS = _specs(OcmManeuverParametersType)
_PHYS_SPECS = _specs(OcmPhysicalDescriptionType)
_PERT_SPECS = _specs(OcmPerturbationsType)
_OD_SPECS = _specs(OcmOdParametersType)


# --- value conversion ------------------------------------------------------------------


def _to_value(spec: _FieldSpec, obj: Any) -> FieldValue:
    """Convert a populated binding field to the fidelity model's typed value."""
    if spec.kind == "enum":
        return str(obj.value)
    if spec.kind == "quantity":
        units = None if obj.units is None else str(obj.units.value)
        return Quantity(float(obj.value), units)
    if spec.kind == "vec3":
        return tuple(float(component) for component in obj)
    if spec.kind == "int":
        return int(obj)
    if spec.kind == "float":
        return float(obj)
    return str(obj)


def _to_binding(spec: _FieldSpec, value: FieldValue) -> Any:
    """Build the binding field a typed fidelity value serialises to."""
    if spec.kind == "enum":
        return _enum_member(spec.concrete, str(value))
    if spec.kind == "quantity":
        assert isinstance(value, Quantity)
        units = None if value.units is None else _enum_member(spec.units_enum, value.units)
        return spec.concrete(value=value.value, units=units)
    if spec.kind == "vec3":
        assert isinstance(value, tuple)
        return [float(component) for component in value]
    return value


def _enum_member(enum_cls: Any, token: str) -> Any:
    """The enum member whose value renders as ``token`` (handles string- and int-valued enums)."""
    for member in enum_cls:
        if str(member.value) == token:
            return member
    raise MalformedSourceError(f"OCM XML value {token!r} is not a valid {enum_cls.__name__}")


def _fields_from_binding(
    binding: Any, specs: tuple[_FieldSpec, ...]
) -> tuple[tuple[str, FieldValue], ...]:
    out: list[tuple[str, FieldValue]] = []
    for spec in specs:
        value = getattr(binding, spec.attr)
        # A vector field (DC_REF_DIR / DC_BODY_TRIGGER) is a list xsdata defaults to empty
        # rather than None; an empty one means the keyword is absent, like a None scalar.
        if value is None or (spec.kind == "vec3" and not value):
            continue
        out.append((spec.keyword, _to_value(spec, value)))
    return tuple(out)


def _kwargs_to_binding(
    fields: tuple[tuple[str, FieldValue], ...], specs: tuple[_FieldSpec, ...]
) -> dict[str, Any]:
    spec_by_keyword = {spec.keyword: spec for spec in specs}
    return {
        spec_by_keyword[keyword].attr: _to_binding(spec_by_keyword[keyword], value)
        for keyword, value in fields
    }


# --- XML -> OcmFile --------------------------------------------------------------------


def ocmfile_from_xml(data: bytes) -> OcmFile:
    """Parse OCM XML ``data`` into an :class:`OcmFile`, tagged ``serialization="xml"``.

    The whole document is bound by the xsdata parser, then mapped block-for-block into the
    fidelity model the KVN reader also produces, so an OCM read from XML is indistinguishable in
    content from the same OCM read from KVN. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for XML that is not well-formed or does
    not match the OCM schema.
    """
    try:
        ocm = parse_ndm_xml(data, Ocm)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the OCM XML: {exc}") from exc
    if ocm.body is None or ocm.body.segment is None:
        raise MalformedSourceError("not a valid OCM: the XML body has no segment")

    segment = ocm.body.segment
    data_section = segment.data
    metadata = OcmKeywordBlock(
        fields=_fields_from_binding(segment.metadata, _META_SPECS),
        comments=tuple(segment.metadata.comment),
    )
    physical = _keyword_block_from_xml(data_section.phys, _PHYS_SPECS)
    perturbations = _keyword_block_from_xml(data_section.pert, _PERT_SPECS)
    orbit_determination = _keyword_block_from_xml(data_section.od, _OD_SPECS)
    header = ocm.header
    return OcmFile(
        ccsds_version=ocm.version,
        metadata=metadata,
        trajectories=tuple(_traj_from_xml(traj) for traj in data_section.traj),
        physical=physical,
        covariances=tuple(_cov_from_xml(cov) for cov in data_section.cov),
        maneuvers=tuple(_man_from_xml(man) for man in data_section.man),
        perturbations=perturbations,
        orbit_determination=orbit_determination,
        user_defined=_user_from_xml(data_section.user),
        creation_date=header.creation_date,
        originator=header.originator,
        message_id=header.message_id,
        classification=header.classification,
        comments=tuple(header.comment),
        serialization="xml",
    )


def _keyword_block_from_xml(binding: Any, specs: tuple[_FieldSpec, ...]) -> OcmKeywordBlock | None:
    if binding is None:
        return None
    return OcmKeywordBlock(
        fields=_fields_from_binding(binding, specs), comments=tuple(binding.comment)
    )


def _traj_from_xml(traj: Any) -> OcmTrajectoryBlock:
    return OcmTrajectoryBlock(
        fields=_fields_from_binding(traj, _TRAJ_SPECS),
        lines=tuple(traj.traj_line),
        comments=tuple(traj.comment),
    )


def _cov_from_xml(cov: Any) -> OcmCovarianceBlock:
    return OcmCovarianceBlock(
        fields=_fields_from_binding(cov, _COV_SPECS),
        lines=tuple(cov.cov_line),
        comments=tuple(cov.comment),
    )


def _man_from_xml(man: Any) -> OcmManeuverBlock:
    return OcmManeuverBlock(
        fields=_fields_from_binding(man, _MAN_SPECS),
        lines=tuple(man.man_line),
        comments=tuple(man.comment),
    )


def _user_from_xml(user: Any) -> OcmUserDefined | None:
    if user is None:
        return None
    parameters = tuple((param.parameter, param.value) for param in user.user_defined)
    return OcmUserDefined(parameters=parameters, comments=tuple(user.comment))


# --- OcmFile -> XML --------------------------------------------------------------------


def xml_bytes_from_ocm(ocm: OcmFile) -> bytes:
    """Serialise an :class:`OcmFile` to schema-valid OCM XML bytes.

    The mirror of :func:`ocmfile_from_xml`. OCM/XML requires the header ``CREATION_DATE`` and
    ``ORIGINATOR`` that KVN treats as optional; when the model does not carry one (a synthesised
    or KVN-sourced OCM), a placeholder is written and the loss reported through the
    lossy-conversion framework, never dropped silently.
    """
    header = OdmHeader(
        comment=list(ocm.comments),
        classification=ocm.classification,
        creation_date=_require_for_xml("CREATION_DATE", ocm.creation_date),
        originator=_require_for_xml("ORIGINATOR", ocm.originator),
        message_id=ocm.message_id,
    )
    data = OcmData(
        traj=[_traj_to_xml(traj) for traj in ocm.trajectories],
        phys=_keyword_block_to_xml(OcmPhysicalDescriptionType, ocm.physical, _PHYS_SPECS),
        cov=[_cov_to_xml(cov) for cov in ocm.covariances],
        man=[_man_to_xml(man) for man in ocm.maneuvers],
        pert=_keyword_block_to_xml(OcmPerturbationsType, ocm.perturbations, _PERT_SPECS),
        od=_keyword_block_to_xml(OcmOdParametersType, ocm.orbit_determination, _OD_SPECS),
        user=_user_to_xml(ocm.user_defined),
    )
    segment = OcmSegment(metadata=_metadata_to_xml(ocm.metadata), data=data)
    return serialize_ndm_xml(Ocm(header=header, body=OcmBody(segment=segment)))


def _metadata_to_xml(metadata: OcmKeywordBlock) -> Any:
    return OcmMetadata(
        comment=list(metadata.comments), **_kwargs_to_binding(metadata.fields, _META_SPECS)
    )


def _keyword_block_to_xml(
    binding_cls: type, block: OcmKeywordBlock | None, specs: tuple[_FieldSpec, ...]
) -> Any:
    if block is None:
        return None
    return binding_cls(comment=list(block.comments), **_kwargs_to_binding(block.fields, specs))


def _traj_to_xml(traj: OcmTrajectoryBlock) -> Any:
    return OcmTrajStateType(
        comment=list(traj.comments),
        traj_line=list(traj.lines),
        **_kwargs_to_binding(traj.fields, _TRAJ_SPECS),
    )


def _cov_to_xml(cov: OcmCovarianceBlock) -> Any:
    return OcmCovarianceMatrixType(
        comment=list(cov.comments),
        cov_line=list(cov.lines),
        **_kwargs_to_binding(cov.fields, _COV_SPECS),
    )


def _man_to_xml(man: OcmManeuverBlock) -> Any:
    return OcmManeuverParametersType(
        comment=list(man.comments),
        man_line=list(man.lines),
        **_kwargs_to_binding(man.fields, _MAN_SPECS),
    )


def _user_to_xml(user: OcmUserDefined | None) -> Any:
    if user is None:
        return None
    return UserDefinedType(
        comment=list(user.comments),
        user_defined=[
            UserDefinedParameterType(parameter=key, value=value) for key, value in user.parameters
        ],
    )
