"""The OPM-XML mapping: the xsdata ``Opm`` binding ↔ the :class:`OpmFile` fidelity model.

The OPM-specific half of the CCSDS-XML seam (the generic plumbing lives in
:mod:`orbit_formats.adapters.ccsds_xml`). Maps the populated
:class:`~orbit_formats._ccsds_xsd.Opm` binding to and from the *same*
:class:`~orbit_formats.readers.ccsds_opm.OpmFile` the hand-written KVN reader produces, so an
OPM read from either notation is the same model — the precondition for the KVN↔XML parity
assertion. Imported lazily (only when an OPM in XML is actually read or written), never at
package import time.

Two XML-only details normalise on round-trip: the state vector carries its canonical units
(``km`` / ``km/s``) on write and they are dropped on read (the unit is fixed by the element),
and a ``<data>``-level comment is folded into the state-vector comments (KVN has a single data
comment level). Both preserve the orbital content; the byte-identical tier (``retain_source``)
reproduces the source verbatim regardless.
"""

from __future__ import annotations

from typing import Any

from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    AngleType,
    AreaType,
    DeltamassTypeZ,
    DistanceType,
    DurationType,
    GmType,
    InclinationType,
    KeplerianElementsType,
    ManeuverParametersType,
    MassType,
    OdmHeader,
    Opm,
    OpmBody,
    OpmData,
    PositionTypeUo,
    PositionUnits,
    SpacecraftParametersType,
    StateVectorType,
    UserDefinedParameterType,
    UserDefinedType,
    VelocityTypeUo,
    VelocityUnits,
)
from orbit_formats._ccsds_xsd import (
    OpmCovarianceMatrixType as XmlOpmCovariance,
)
from orbit_formats._ccsds_xsd import (
    OpmMetadata as XmlOpmMetadata,
)
from orbit_formats._ccsds_xsd import (
    OpmSegment as XmlOpmSegment,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.adapters.oem_xml import _COVARIANCE_LAYOUT, _require_for_xml
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import _parse_epoch
from orbit_formats.readers.ccsds_opm import (
    OpmCovariance,
    OpmFile,
    OpmKeplerianElements,
    OpmManeuver,
    OpmMetadata,
    OpmSpacecraftParameters,
    OpmStateVector,
)
from orbit_formats.writers.oem import _format_epoch

__all__ = ["opmfile_from_xml", "xml_bytes_from_opmfile"]


# --- XML -> OpmFile --------------------------------------------------------------------


def opmfile_from_xml(data: bytes) -> OpmFile:
    """Parse OPM XML ``data`` into an :class:`OpmFile`, tagged ``serialization="xml"``."""
    try:
        opm = parse_ndm_xml(data, Opm)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the OPM XML: {exc}") from exc

    segment = opm.body.segment
    meta = segment.metadata
    body = segment.data
    user_defined, user_defined_comments = _user_defined_from_xml(body.user_defined_parameters)
    return OpmFile(
        ccsds_version=opm.version,
        metadata=OpmMetadata(
            object_name=meta.object_name,
            object_id=meta.object_id,
            center_name=meta.center_name,
            ref_frame=meta.ref_frame,
            time_system=meta.time_system,
            ref_frame_epoch=meta.ref_frame_epoch,
            comments=tuple(meta.comment),
        ),
        state_vector=_state_from_xml(body),
        creation_date=opm.header.creation_date,
        originator=opm.header.originator,
        message_id=opm.header.message_id,
        comments=tuple(opm.header.comment),
        keplerian=_keplerian_from_xml(body.keplerian_elements),
        spacecraft_parameters=_spacecraft_from_xml(body.spacecraft_parameters),
        covariance=_covariance_from_xml(body.covariance_matrix),
        maneuvers=tuple(_maneuver_from_xml(maneuver) for maneuver in body.maneuver_parameters),
        user_defined=user_defined,
        user_defined_comments=user_defined_comments,
        serialization="xml",
    )


def _value(quantity: Any) -> float | None:
    """The numeric value of an optional ``{value, units}`` element, or ``None``."""
    return None if quantity is None else float(quantity.value)


def _state_from_xml(body: Any) -> OpmStateVector:
    state = body.state_vector
    # A <data>-level comment folds into the state-vector comments (KVN's single data level).
    comments = tuple(body.comment) + tuple(state.comment)
    return OpmStateVector(
        epoch=_parse_epoch(state.epoch),
        x=float(state.x.value),
        y=float(state.y.value),
        z=float(state.z.value),
        x_dot=float(state.x_dot.value),
        y_dot=float(state.y_dot.value),
        z_dot=float(state.z_dot.value),
        comments=comments,
    )


def _keplerian_from_xml(keplerian: Any) -> OpmKeplerianElements | None:
    if keplerian is None:
        return None
    return OpmKeplerianElements(
        semi_major_axis=float(keplerian.semi_major_axis.value),
        eccentricity=float(keplerian.eccentricity),
        inclination=float(keplerian.inclination.value),
        ra_of_asc_node=float(keplerian.ra_of_asc_node.value),
        arg_of_pericenter=float(keplerian.arg_of_pericenter.value),
        gm=float(keplerian.gm.value),
        true_anomaly=_value(keplerian.true_anomaly),
        mean_anomaly=_value(keplerian.mean_anomaly),
        comments=tuple(keplerian.comment),
    )


def _spacecraft_from_xml(spacecraft: Any) -> OpmSpacecraftParameters | None:
    if spacecraft is None:
        return None
    return OpmSpacecraftParameters(
        mass=_value(spacecraft.mass),
        solar_rad_area=_value(spacecraft.solar_rad_area),
        solar_rad_coeff=spacecraft.solar_rad_coeff,
        drag_area=_value(spacecraft.drag_area),
        drag_coeff=spacecraft.drag_coeff,
        comments=tuple(spacecraft.comment),
    )


def _covariance_from_xml(covariance: Any) -> OpmCovariance | None:
    if covariance is None:
        return None
    return OpmCovariance(
        matrix=tuple(float(getattr(covariance, name).value) for name, _ in _COVARIANCE_LAYOUT),
        cov_ref_frame=covariance.cov_ref_frame,
        comments=tuple(covariance.comment),
    )


def _maneuver_from_xml(maneuver: Any) -> OpmManeuver:
    return OpmManeuver(
        man_epoch_ignition=_parse_epoch(maneuver.man_epoch_ignition),
        man_duration=float(maneuver.man_duration.value),
        man_delta_mass=float(maneuver.man_delta_mass.value),
        man_ref_frame=maneuver.man_ref_frame,
        man_dv_1=float(maneuver.man_dv_1.value),
        man_dv_2=float(maneuver.man_dv_2.value),
        man_dv_3=float(maneuver.man_dv_3.value),
        comments=tuple(maneuver.comment),
    )


def _user_defined_from_xml(
    user_defined: Any,
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    if user_defined is None:
        return (), ()
    params = tuple((param.parameter, param.value) for param in user_defined.user_defined)
    return params, tuple(user_defined.comment)


# --- OpmFile -> XML --------------------------------------------------------------------


def xml_bytes_from_opmfile(opm: OpmFile) -> bytes:
    """Serialise an :class:`OpmFile` to schema-valid OPM XML bytes.

    The mirror of :func:`opmfile_from_xml`. OPM XML requires the header ``CREATION_DATE`` and
    ``ORIGINATOR`` that KVN treats as optional; when the model does not carry one a placeholder
    is written and reported through the lossy-conversion framework, never dropped silently.
    """
    header = OdmHeader(
        comment=list(opm.comments),
        creation_date=_require_for_xml("CREATION_DATE", opm.creation_date),
        originator=_require_for_xml("ORIGINATOR", opm.originator),
        message_id=opm.message_id,
    )
    meta = opm.metadata
    xml_meta = XmlOpmMetadata(
        comment=list(meta.comments),
        object_name=meta.object_name,
        object_id=meta.object_id,
        center_name=meta.center_name,
        ref_frame=meta.ref_frame,
        ref_frame_epoch=meta.ref_frame_epoch,
        time_system=meta.time_system,
    )
    data = OpmData(
        state_vector=_state_to_xml(opm.state_vector),
        keplerian_elements=_keplerian_to_xml(opm.keplerian),
        spacecraft_parameters=_spacecraft_to_xml(opm.spacecraft_parameters),
        covariance_matrix=_covariance_to_xml(opm.covariance),
        maneuver_parameters=[_maneuver_to_xml(maneuver) for maneuver in opm.maneuvers],
        user_defined_parameters=_user_defined_to_xml(opm.user_defined, opm.user_defined_comments),
    )
    body = OpmBody(segment=XmlOpmSegment(metadata=xml_meta, data=data))
    return serialize_ndm_xml(Opm(header=header, body=body))


def _state_to_xml(state: OpmStateVector) -> Any:
    return StateVectorType(
        comment=list(state.comments),
        epoch=_format_epoch(state.epoch),
        x=PositionTypeUo(value=state.x, units=PositionUnits.KM),
        y=PositionTypeUo(value=state.y, units=PositionUnits.KM),
        z=PositionTypeUo(value=state.z, units=PositionUnits.KM),
        x_dot=VelocityTypeUo(value=state.x_dot, units=VelocityUnits.KM_S),
        y_dot=VelocityTypeUo(value=state.y_dot, units=VelocityUnits.KM_S),
        z_dot=VelocityTypeUo(value=state.z_dot, units=VelocityUnits.KM_S),
    )


def _keplerian_to_xml(keplerian: OpmKeplerianElements | None) -> Any:
    if keplerian is None:
        return None
    return KeplerianElementsType(
        comment=list(keplerian.comments),
        semi_major_axis=DistanceType(value=keplerian.semi_major_axis),
        eccentricity=keplerian.eccentricity,
        inclination=InclinationType(value=keplerian.inclination),
        ra_of_asc_node=AngleType(value=keplerian.ra_of_asc_node),
        arg_of_pericenter=AngleType(value=keplerian.arg_of_pericenter),
        true_anomaly=None
        if keplerian.true_anomaly is None
        else AngleType(value=keplerian.true_anomaly),
        mean_anomaly=None
        if keplerian.mean_anomaly is None
        else AngleType(value=keplerian.mean_anomaly),
        gm=GmType(value=keplerian.gm),
    )


def _spacecraft_to_xml(spacecraft: OpmSpacecraftParameters | None) -> Any:
    if spacecraft is None:
        return None
    return SpacecraftParametersType(
        comment=list(spacecraft.comments),
        mass=None if spacecraft.mass is None else MassType(value=spacecraft.mass),
        solar_rad_area=(
            None if spacecraft.solar_rad_area is None else AreaType(value=spacecraft.solar_rad_area)
        ),
        solar_rad_coeff=spacecraft.solar_rad_coeff,
        drag_area=None if spacecraft.drag_area is None else AreaType(value=spacecraft.drag_area),
        drag_coeff=spacecraft.drag_coeff,
    )


def _covariance_to_xml(covariance: OpmCovariance | None) -> Any:
    if covariance is None:
        return None
    elements = {
        name: value_type(value=covariance.matrix[index])
        for index, (name, value_type) in enumerate(_COVARIANCE_LAYOUT)
    }
    return XmlOpmCovariance(
        comment=list(covariance.comments),
        cov_ref_frame=covariance.cov_ref_frame,
        **elements,
    )


def _maneuver_to_xml(maneuver: OpmManeuver) -> Any:
    return ManeuverParametersType(
        comment=list(maneuver.comments),
        man_epoch_ignition=_format_epoch(maneuver.man_epoch_ignition),
        man_duration=DurationType(value=maneuver.man_duration),
        man_delta_mass=DeltamassTypeZ(value=maneuver.man_delta_mass),
        man_ref_frame=maneuver.man_ref_frame,
        man_dv_1=VelocityTypeUo(value=maneuver.man_dv_1),
        man_dv_2=VelocityTypeUo(value=maneuver.man_dv_2),
        man_dv_3=VelocityTypeUo(value=maneuver.man_dv_3),
    )


def _user_defined_to_xml(
    user_defined: tuple[tuple[str, str], ...], comments: tuple[str, ...]
) -> Any:
    if not user_defined and not comments:
        return None
    return UserDefinedType(
        comment=list(comments),
        user_defined=[
            UserDefinedParameterType(parameter=key, value=value) for key, value in user_defined
        ],
    )
