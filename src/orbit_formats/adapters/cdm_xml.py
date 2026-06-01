"""The CDM-XML mapping: the xsdata ``Cdm`` binding ↔ the :class:`CdmFile` fidelity model.

The CDM-specific half of the CCSDS-XML seam (the generic plumbing lives in
:mod:`orbit_formats.adapters.ccsds_xml`). Maps the populated
:class:`~orbit_formats._ccsds_xsd.Cdm` binding to and from the *same*
:class:`~orbit_formats.readers.ccsds_cdm.CdmFile` the hand-written KVN reader produces, so a
CDM read from either notation is the same model — the precondition for the KVN↔XML parity
assertion. Imported lazily (only when a CDM in XML is read or written), never at package
import time.

Unlike APM (KVN v1 vs XML v2) the CDM has a single message version (1.0) shared by both
notations, so there is no version-skew carve-out: the two notations carry identical content,
shaped only by the XML schema's typed value+units elements vs KVN's bracketed unit suffixes.
"""

from __future__ import annotations

from typing import Any

from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    AdditionalParametersType,
    AreaType,
    AreaUnits,
    Cdm,
    CdmBody,
    CdmCovarianceMatrixType,
    CdmData,
    CdmHeader,
    CdmMetadata,
    CdmSegment,
    CdmStateVectorType,
    CovarianceMethodType,
    DayIntervalTypeUo,
    DayIntervalUnits,
    DvType,
    DvUnits,
    LengthTypeUo,
    LengthUnits,
    M2KgType,
    M2KgUnits,
    M2S2Type,
    M2S2Units,
    M2S3Type,
    M2S3Units,
    M2S4Type,
    M2S4Units,
    M2SType,
    M2SUnits,
    M2Type,
    M2Units,
    M3Kgs2Type,
    M3Kgs2Units,
    M3KgsType,
    M3KgsUnits,
    M3KgType,
    M3KgUnits,
    M4Kg2Type,
    M4Kg2Units,
    ManeuverableType,
    MassType,
    MassUnits,
    Ms2Type,
    Ms2Units,
    ObjectDescriptionType,
    ObjectType,
    OdParametersType,
    PercentageTypeUo,
    PercentageUnits,
    PositionTypeUr,
    PositionUnits,
    ReferenceFrameType,
    RelativeMetadataData,
    RelativeStateVectorType,
    ScreenVolumeFrameType,
    ScreenVolumeShapeType,
    VelocityTypeUr,
    VelocityUnits,
    WkgType,
    WkgUnits,
    YesNoType,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.adapters.oem_xml import _require_for_xml
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import _parse_epoch
from orbit_formats.readers.ccsds_cdm import (
    _COV_EXTENDED_KEYS,
    _COV_MANDATORY,
    _COV_MANDATORY_KEYS,
    COV_UNITS,
    CdmAdditionalParameters,
    CdmCovariance,
    CdmFile,
    CdmObject,
    CdmObjectMetadata,
    CdmOdParameters,
    CdmRelativeMetadata,
    CdmStateVector,
)
from orbit_formats.writers.oem import _format_epoch

__all__ = ["cdmfile_from_xml", "xml_bytes_from_cdm"]

# The CCSDS covariance unit string mapped to its (binding value-type, units enum member),
# so any covariance element constructs to the right typed binding.
_COV_BINDING: dict[str, tuple[type[Any], object]] = {
    "m**2": (M2Type, M2Units.M_2),
    "m**2/s": (M2SType, M2SUnits.M_2_S),
    "m**2/s**2": (M2S2Type, M2S2Units.M_2_S_2),
    "m**3/kg": (M3KgType, M3KgUnits.M_3_KG),
    "m**3/(kg*s)": (M3KgsType, M3KgsUnits.M_3_KG_S),
    "m**4/kg**2": (M4Kg2Type, M4Kg2Units.M_4_KG_2),
    "m**2/s**3": (M2S3Type, M2S3Units.M_2_S_3),
    "m**3/(kg*s**2)": (M3Kgs2Type, M3Kgs2Units.M_3_KG_S_2),
    "m**2/s**4": (M2S4Type, M2S4Units.M_2_S_4),
}


# --- XML -> CdmFile --------------------------------------------------------------------


def cdmfile_from_xml(data: bytes) -> CdmFile:
    """Parse CDM XML ``data`` into a :class:`CdmFile`, tagged ``serialization="xml"``."""
    try:
        cdm = parse_ndm_xml(data, Cdm)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the CDM XML: {exc}") from exc

    body = cdm.body
    if len(body.segment) != 2:
        raise MalformedSourceError(f"a CDM must carry exactly two objects, got {len(body.segment)}")
    return CdmFile(
        ccsds_version=cdm.version,
        relative=_relative_from_xml(body.relative_metadata_data),
        objects=(_object_from_xml(body.segment[0]), _object_from_xml(body.segment[1])),
        creation_date=cdm.header.creation_date,
        originator=cdm.header.originator,
        message_for=cdm.header.message_for,
        message_id=cdm.header.message_id,
        comments=tuple(cdm.header.comment),
        serialization="xml",
    )


def _relative_from_xml(rel: RelativeMetadataData) -> CdmRelativeMetadata:
    return CdmRelativeMetadata(
        tca=_parse_epoch(rel.tca),
        miss_distance=float(rel.miss_distance.value),
        relative_speed=_optval(rel.relative_speed),
        relative_position=_relative_triplet_from_xml(rel.relative_state_vector, position=True),
        relative_velocity=_relative_triplet_from_xml(rel.relative_state_vector, position=False),
        start_screen_period=rel.start_screen_period,
        stop_screen_period=rel.stop_screen_period,
        screen_volume_frame=_optenum(rel.screen_volume_frame),
        screen_volume_shape=_optenum(rel.screen_volume_shape),
        screen_volume_x=_optval(rel.screen_volume_x),
        screen_volume_y=_optval(rel.screen_volume_y),
        screen_volume_z=_optval(rel.screen_volume_z),
        screen_entry_time=rel.screen_entry_time,
        screen_exit_time=rel.screen_exit_time,
        collision_probability=rel.collision_probability,
        collision_probability_method=rel.collision_probability_method,
        comments=tuple(rel.comment),
    )


def _relative_triplet_from_xml(
    state: RelativeStateVectorType | None, *, position: bool
) -> tuple[float, float, float] | None:
    if state is None:
        return None
    if position:
        return (
            float(state.relative_position_r.value),
            float(state.relative_position_t.value),
            float(state.relative_position_n.value),
        )
    return (
        float(state.relative_velocity_r.value),
        float(state.relative_velocity_t.value),
        float(state.relative_velocity_n.value),
    )


def _object_from_xml(segment: CdmSegment) -> CdmObject:
    meta = segment.metadata
    data = segment.data
    return CdmObject(
        metadata=_object_meta_from_xml(meta),
        state=_state_from_xml(data.state_vector),
        covariance=_covariance_from_xml(data.covariance_matrix),
        od_parameters=(
            _od_from_xml(data.od_parameters) if data.od_parameters is not None else None
        ),
        additional_parameters=(
            _add_from_xml(data.additional_parameters)
            if data.additional_parameters is not None
            else None
        ),
        data_comments=tuple(data.comment),
    )


def _object_meta_from_xml(meta: CdmMetadata) -> CdmObjectMetadata:
    return CdmObjectMetadata(
        object_value=meta.object_value.value,
        object_designator=meta.object_designator,
        catalog_name=meta.catalog_name,
        object_name=meta.object_name,
        international_designator=meta.international_designator,
        ephemeris_name=meta.ephemeris_name,
        covariance_method=meta.covariance_method.value,
        maneuverable=meta.maneuverable.value,
        ref_frame=meta.ref_frame.value,
        object_type=_optenum(meta.object_type),
        operator_contact_position=meta.operator_contact_position,
        operator_organization=meta.operator_organization,
        operator_phone=meta.operator_phone,
        operator_email=meta.operator_email,
        orbit_center=meta.orbit_center,
        gravity_model=meta.gravity_model,
        atmospheric_model=meta.atmospheric_model,
        n_body_perturbations=meta.n_body_perturbations,
        solar_rad_pressure=_optenum(meta.solar_rad_pressure),
        earth_tides=_optenum(meta.earth_tides),
        intrack_thrust=_optenum(meta.intrack_thrust),
        comments=tuple(meta.comment),
    )


def _state_from_xml(state: CdmStateVectorType) -> CdmStateVector:
    return CdmStateVector(
        x=float(state.x.value),
        y=float(state.y.value),
        z=float(state.z.value),
        x_dot=float(state.x_dot.value),
        y_dot=float(state.y_dot.value),
        z_dot=float(state.z_dot.value),
        comments=tuple(state.comment),
    )


def _covariance_from_xml(cov: CdmCovarianceMatrixType) -> CdmCovariance:
    matrix = tuple(float(getattr(cov, key.lower()).value) for key in _COV_MANDATORY_KEYS)
    extended = tuple(
        (key, float(getattr(cov, key.lower()).value))
        for key in _COV_EXTENDED_KEYS
        if getattr(cov, key.lower(), None) is not None
    )
    return CdmCovariance(matrix=matrix, extended=extended, comments=tuple(cov.comment))


def _od_from_xml(od: OdParametersType) -> CdmOdParameters:
    return CdmOdParameters(
        time_lastob_start=od.time_lastob_start,
        time_lastob_end=od.time_lastob_end,
        recommended_od_span=_optval(od.recommended_od_span),
        actual_od_span=_optval(od.actual_od_span),
        obs_available=od.obs_available,
        obs_used=od.obs_used,
        tracks_available=od.tracks_available,
        tracks_used=od.tracks_used,
        residuals_accepted=_optval(od.residuals_accepted),
        weighted_rms=od.weighted_rms,
        comments=tuple(od.comment),
    )


def _add_from_xml(add: AdditionalParametersType) -> CdmAdditionalParameters:
    return CdmAdditionalParameters(
        area_pc=_optval(add.area_pc),
        area_drg=_optval(add.area_drg),
        area_srp=_optval(add.area_srp),
        mass=_optval(add.mass),
        cd_area_over_mass=_optval(add.cd_area_over_mass),
        cr_area_over_mass=_optval(add.cr_area_over_mass),
        thrust_acceleration=_optval(add.thrust_acceleration),
        sedr=_optval(add.sedr),
        comments=tuple(add.comment),
    )


def _optval(value: Any) -> float | None:
    """The ``.value`` of an optional value+units binding, or ``None``."""
    return None if value is None else float(value.value)


def _optenum(member: Any) -> str | None:
    """The ``.value`` of an optional enum binding, or ``None``."""
    return None if member is None else str(member.value)


# --- CdmFile -> XML --------------------------------------------------------------------


def xml_bytes_from_cdm(cdm: CdmFile) -> bytes:
    """Serialise a :class:`CdmFile` to schema-valid CDM XML bytes.

    The mirror of :func:`cdmfile_from_xml`. CDM XML requires the header ``CREATION_DATE``,
    ``ORIGINATOR``, and ``MESSAGE_ID`` (KVN treats them as optional on the model); when one is
    absent a placeholder is written and reported, never dropped silently.
    """
    header = CdmHeader(
        comment=list(cdm.comments),
        creation_date=_require_for_xml("CREATION_DATE", cdm.creation_date),
        originator=_require_for_xml("ORIGINATOR", cdm.originator),
        message_for=cdm.message_for,
        message_id=_require_for_xml("MESSAGE_ID", cdm.message_id),
    )
    body = CdmBody(
        relative_metadata_data=_relative_to_xml(cdm.relative),
        segment=[_object_to_xml(obj) for obj in cdm.objects],
    )
    return serialize_ndm_xml(Cdm(header=header, body=body))


def _relative_to_xml(rel: CdmRelativeMetadata) -> RelativeMetadataData:
    return RelativeMetadataData(
        comment=list(rel.comments),
        tca=_format_epoch(rel.tca),
        miss_distance=_len(rel.miss_distance),
        relative_speed=None if rel.relative_speed is None else _dv(rel.relative_speed),
        relative_state_vector=_relative_state_to_xml(rel),
        start_screen_period=rel.start_screen_period,
        stop_screen_period=rel.stop_screen_period,
        screen_volume_frame=(
            None
            if rel.screen_volume_frame is None
            else ScreenVolumeFrameType(rel.screen_volume_frame)
        ),
        screen_volume_shape=(
            None
            if rel.screen_volume_shape is None
            else ScreenVolumeShapeType(rel.screen_volume_shape)
        ),
        screen_volume_x=None if rel.screen_volume_x is None else _len(rel.screen_volume_x),
        screen_volume_y=None if rel.screen_volume_y is None else _len(rel.screen_volume_y),
        screen_volume_z=None if rel.screen_volume_z is None else _len(rel.screen_volume_z),
        screen_entry_time=rel.screen_entry_time,
        screen_exit_time=rel.screen_exit_time,
        collision_probability=rel.collision_probability,
        collision_probability_method=rel.collision_probability_method,
    )


def _relative_state_to_xml(rel: CdmRelativeMetadata) -> RelativeStateVectorType | None:
    if rel.relative_position is None or rel.relative_velocity is None:
        return None
    pos = rel.relative_position
    vel = rel.relative_velocity
    return RelativeStateVectorType(
        relative_position_r=_len(pos[0]),
        relative_position_t=_len(pos[1]),
        relative_position_n=_len(pos[2]),
        relative_velocity_r=_dv(vel[0]),
        relative_velocity_t=_dv(vel[1]),
        relative_velocity_n=_dv(vel[2]),
    )


def _object_to_xml(obj: CdmObject) -> CdmSegment:
    return CdmSegment(
        metadata=_object_meta_to_xml(obj.metadata),
        data=CdmData(
            comment=list(obj.data_comments),
            od_parameters=None if obj.od_parameters is None else _od_to_xml(obj.od_parameters),
            additional_parameters=(
                None
                if obj.additional_parameters is None
                else _add_to_xml(obj.additional_parameters)
            ),
            state_vector=_state_to_xml(obj.state),
            covariance_matrix=_covariance_to_xml(obj.covariance),
        ),
    )


def _object_meta_to_xml(meta: CdmObjectMetadata) -> CdmMetadata:
    return CdmMetadata(
        comment=list(meta.comments),
        object_value=ObjectType(meta.object_value),
        object_designator=meta.object_designator,
        catalog_name=meta.catalog_name,
        object_name=meta.object_name,
        international_designator=meta.international_designator,
        object_type=None if meta.object_type is None else ObjectDescriptionType(meta.object_type),
        operator_contact_position=meta.operator_contact_position,
        operator_organization=meta.operator_organization,
        operator_phone=meta.operator_phone,
        operator_email=meta.operator_email,
        ephemeris_name=meta.ephemeris_name,
        covariance_method=CovarianceMethodType(meta.covariance_method),
        maneuverable=ManeuverableType(meta.maneuverable),
        orbit_center=meta.orbit_center,
        ref_frame=ReferenceFrameType(meta.ref_frame),
        gravity_model=meta.gravity_model,
        atmospheric_model=meta.atmospheric_model,
        n_body_perturbations=meta.n_body_perturbations,
        solar_rad_pressure=(
            None if meta.solar_rad_pressure is None else YesNoType(meta.solar_rad_pressure)
        ),
        earth_tides=None if meta.earth_tides is None else YesNoType(meta.earth_tides),
        intrack_thrust=None if meta.intrack_thrust is None else YesNoType(meta.intrack_thrust),
    )


def _state_to_xml(state: CdmStateVector) -> CdmStateVectorType:
    return CdmStateVectorType(
        comment=list(state.comments),
        x=_pos(state.x),
        y=_pos(state.y),
        z=_pos(state.z),
        x_dot=_vel(state.x_dot),
        y_dot=_vel(state.y_dot),
        z_dot=_vel(state.z_dot),
    )


def _covariance_to_xml(cov: CdmCovariance) -> CdmCovarianceMatrixType:
    mandatory = {
        key.lower(): _cov(value, key)
        for (key, _unit), value in zip(_COV_MANDATORY, cov.matrix, strict=True)
    }
    binding = CdmCovarianceMatrixType(comment=list(cov.comments), **mandatory)
    for key, value in cov.extended:
        setattr(binding, key.lower(), _cov(value, key))
    return binding


def _od_to_xml(od: CdmOdParameters) -> OdParametersType:
    return OdParametersType(
        comment=list(od.comments),
        time_lastob_start=od.time_lastob_start,
        time_lastob_end=od.time_lastob_end,
        recommended_od_span=None
        if od.recommended_od_span is None
        else _day(od.recommended_od_span),
        actual_od_span=None if od.actual_od_span is None else _day(od.actual_od_span),
        obs_available=od.obs_available,
        obs_used=od.obs_used,
        tracks_available=od.tracks_available,
        tracks_used=od.tracks_used,
        residuals_accepted=None if od.residuals_accepted is None else _pct(od.residuals_accepted),
        weighted_rms=od.weighted_rms,
    )


def _add_to_xml(add: CdmAdditionalParameters) -> AdditionalParametersType:
    return AdditionalParametersType(
        comment=list(add.comments),
        area_pc=None if add.area_pc is None else _area(add.area_pc),
        area_drg=None if add.area_drg is None else _area(add.area_drg),
        area_srp=None if add.area_srp is None else _area(add.area_srp),
        mass=None if add.mass is None else MassType(value=add.mass, units=MassUnits.KG),
        cd_area_over_mass=None if add.cd_area_over_mass is None else _m2kg(add.cd_area_over_mass),
        cr_area_over_mass=None if add.cr_area_over_mass is None else _m2kg(add.cr_area_over_mass),
        thrust_acceleration=(
            None if add.thrust_acceleration is None else _ms2(add.thrust_acceleration)
        ),
        sedr=None if add.sedr is None else WkgType(value=add.sedr, units=WkgUnits.W_KG),
    )


# --- typed value+units constructors ----------------------------------------------------


def _len(value: float) -> LengthTypeUo:
    return LengthTypeUo(value=value, units=LengthUnits.M)


def _pos(value: float) -> PositionTypeUr:
    return PositionTypeUr(value=value, units=PositionUnits.KM)


def _vel(value: float) -> VelocityTypeUr:
    return VelocityTypeUr(value=value, units=VelocityUnits.KM_S)


def _dv(value: float) -> DvType:
    return DvType(value=value, units=DvUnits.M_S)


def _area(value: float) -> AreaType:
    return AreaType(value=value, units=AreaUnits.M_2)


def _m2kg(value: float) -> M2KgType:
    return M2KgType(value=value, units=M2KgUnits.M_2_KG)


def _ms2(value: float) -> Ms2Type:
    return Ms2Type(value=value, units=Ms2Units.M_S_2)


def _day(value: float) -> DayIntervalTypeUo:
    return DayIntervalTypeUo(value=value, units=DayIntervalUnits.D)


def _pct(value: float) -> PercentageTypeUo:
    return PercentageTypeUo(value=value, units=PercentageUnits.PERCENT_SIGN)


def _cov(value: float, keyword: str) -> Any:
    """Construct the right typed covariance binding for ``keyword`` from its unit."""
    cls, units = _COV_BINDING[COV_UNITS[keyword]]
    return cls(value=value, units=units)
