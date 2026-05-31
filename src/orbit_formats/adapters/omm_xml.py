"""The OMM-XML mapping: the xsdata ``Omm`` binding ↔ the :class:`OmmFile` fidelity model.

The OMM-specific half of the CCSDS-XML seam (the generic plumbing lives in
:mod:`orbit_formats.adapters.ccsds_xml`). Maps the populated
:class:`~orbit_formats._ccsds_xsd.Omm` binding to and from the *same*
:class:`~orbit_formats.readers.ccsds_omm.OmmFile` the hand-written KVN reader produces, so an
OMM read from either notation is the same model — the precondition for the KVN↔XML parity
assertion. Imported lazily (only when an OMM in XML is actually read or written), never at
package import time.

Two XML-only details normalise on round-trip: a dimensional value's optional ``units``
attribute is dropped (the unit is fixed by the keyword, so the number is the content), and a
``<data>``-level comment is folded into the mean-elements comments (KVN has a single data
comment level). Both preserve the orbital content; the byte-identical tier (``retain_source``)
reproduces the source verbatim regardless.
"""

from __future__ import annotations

from typing import Any

from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    AgomType,
    AngleType,
    AreaType,
    BStarType,
    BTermType,
    DdRevType,
    DistanceType,
    DRevType,
    GmType,
    InclinationType,
    MassType,
    MeanElementsType,
    OdmHeader,
    Omm,
    OmmBody,
    OmmData,
    RevType,
    SpacecraftParametersType,
    TleParametersType,
    UserDefinedParameterType,
    UserDefinedType,
)
from orbit_formats._ccsds_xsd import (
    OmmMetadata as XmlOmmMetadata,
)
from orbit_formats._ccsds_xsd import (
    OmmSegment as XmlOmmSegment,
)
from orbit_formats._ccsds_xsd import (
    OpmCovarianceMatrixType as XmlOmmCovariance,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.adapters.oem_xml import _COVARIANCE_LAYOUT, _require_for_xml
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import _parse_epoch
from orbit_formats.readers.ccsds_omm import (
    OmmCovariance,
    OmmFile,
    OmmMeanElements,
    OmmMetadata,
    OmmSpacecraftParameters,
    OmmTleParameters,
)
from orbit_formats.writers.oem import _format_epoch

__all__ = ["ommfile_from_xml", "xml_bytes_from_ommfile"]


# --- XML -> OmmFile --------------------------------------------------------------------


def ommfile_from_xml(data: bytes) -> OmmFile:
    """Parse OMM XML ``data`` into an :class:`OmmFile`, tagged ``serialization="xml"``."""
    try:
        omm = parse_ndm_xml(data, Omm)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the OMM XML: {exc}") from exc

    segment = omm.body.segment
    meta = segment.metadata
    body = segment.data
    user_defined, user_defined_comments = _user_defined_from_xml(body.user_defined_parameters)
    return OmmFile(
        ccsds_version=omm.version,
        metadata=OmmMetadata(
            object_name=meta.object_name,
            object_id=meta.object_id,
            center_name=meta.center_name,
            ref_frame=meta.ref_frame,
            time_system=meta.time_system,
            mean_element_theory=meta.mean_element_theory,
            ref_frame_epoch=meta.ref_frame_epoch,
            comments=tuple(meta.comment),
        ),
        mean_elements=_mean_elements_from_xml(body),
        creation_date=omm.header.creation_date,
        originator=omm.header.originator,
        comments=tuple(omm.header.comment),
        tle_parameters=_tle_from_xml(body.tle_parameters),
        spacecraft_parameters=_spacecraft_from_xml(body.spacecraft_parameters),
        covariance=_covariance_from_xml(body.covariance_matrix),
        user_defined=user_defined,
        user_defined_comments=user_defined_comments,
        serialization="xml",
    )


def _value(quantity: Any) -> float | None:
    """The numeric value of an optional ``{value, units}`` element, or ``None``."""
    return None if quantity is None else float(quantity.value)


def _mean_elements_from_xml(body: Any) -> OmmMeanElements:
    elements = body.mean_elements
    # A <data>-level comment folds into the mean-elements comments (KVN's single data level).
    comments = tuple(body.comment) + tuple(elements.comment)
    return OmmMeanElements(
        epoch=_parse_epoch(elements.epoch),
        eccentricity=float(elements.eccentricity),
        inclination=float(elements.inclination.value),
        ra_of_asc_node=float(elements.ra_of_asc_node.value),
        arg_of_pericenter=float(elements.arg_of_pericenter.value),
        mean_anomaly=float(elements.mean_anomaly.value),
        mean_motion=_value(elements.mean_motion),
        semi_major_axis=_value(elements.semi_major_axis),
        gm=_value(elements.gm),
        comments=comments,
    )


def _tle_from_xml(tle: Any) -> OmmTleParameters | None:
    if tle is None:
        return None
    return OmmTleParameters(
        mean_motion_dot=float(tle.mean_motion_dot.value),
        ephemeris_type=tle.ephemeris_type,
        classification_type=tle.classification_type,
        norad_cat_id=tle.norad_cat_id,
        element_set_no=tle.element_set_no,
        rev_at_epoch=tle.rev_at_epoch,
        bstar=_value(tle.bstar),
        bterm=_value(tle.bterm),
        mean_motion_ddot=_value(tle.mean_motion_ddot),
        agom=_value(tle.agom),
        comments=tuple(tle.comment),
    )


def _spacecraft_from_xml(spacecraft: Any) -> OmmSpacecraftParameters | None:
    if spacecraft is None:
        return None
    return OmmSpacecraftParameters(
        mass=_value(spacecraft.mass),
        solar_rad_area=_value(spacecraft.solar_rad_area),
        solar_rad_coeff=spacecraft.solar_rad_coeff,
        drag_area=_value(spacecraft.drag_area),
        drag_coeff=spacecraft.drag_coeff,
        comments=tuple(spacecraft.comment),
    )


def _covariance_from_xml(covariance: Any) -> OmmCovariance | None:
    if covariance is None:
        return None
    return OmmCovariance(
        matrix=tuple(float(getattr(covariance, name).value) for name, _ in _COVARIANCE_LAYOUT),
        cov_ref_frame=covariance.cov_ref_frame,
        comments=tuple(covariance.comment),
    )


def _user_defined_from_xml(
    user_defined: Any,
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    if user_defined is None:
        return (), ()
    params = tuple((param.parameter, param.value) for param in user_defined.user_defined)
    return params, tuple(user_defined.comment)


# --- OmmFile -> XML --------------------------------------------------------------------


def xml_bytes_from_ommfile(omm: OmmFile) -> bytes:
    """Serialise an :class:`OmmFile` to schema-valid OMM XML bytes.

    The mirror of :func:`ommfile_from_xml`. OMM XML requires the header ``CREATION_DATE`` and
    ``ORIGINATOR`` that KVN treats as optional; when the model does not carry one a placeholder
    is written and reported through the lossy-conversion framework, never dropped silently.
    """
    header = OdmHeader(
        comment=list(omm.comments),
        creation_date=_require_for_xml("CREATION_DATE", omm.creation_date),
        originator=_require_for_xml("ORIGINATOR", omm.originator),
    )
    meta = omm.metadata
    xml_meta = XmlOmmMetadata(
        comment=list(meta.comments),
        object_name=meta.object_name,
        object_id=meta.object_id,
        center_name=meta.center_name,
        ref_frame=meta.ref_frame,
        ref_frame_epoch=meta.ref_frame_epoch,
        time_system=meta.time_system,
        mean_element_theory=meta.mean_element_theory,
    )
    data = OmmData(
        mean_elements=_mean_elements_to_xml(omm.mean_elements),
        spacecraft_parameters=_spacecraft_to_xml(omm.spacecraft_parameters),
        tle_parameters=_tle_to_xml(omm.tle_parameters),
        covariance_matrix=_covariance_to_xml(omm.covariance),
        user_defined_parameters=_user_defined_to_xml(omm.user_defined, omm.user_defined_comments),
    )
    body = OmmBody(segment=XmlOmmSegment(metadata=xml_meta, data=data))
    return serialize_ndm_xml(Omm(header=header, body=body))


def _mean_elements_to_xml(elements: OmmMeanElements) -> Any:
    return MeanElementsType(
        comment=list(elements.comments),
        epoch=_format_epoch(elements.epoch),
        semi_major_axis=(
            None
            if elements.semi_major_axis is None
            else DistanceType(value=elements.semi_major_axis)
        ),
        mean_motion=None if elements.mean_motion is None else RevType(value=elements.mean_motion),
        eccentricity=elements.eccentricity,
        inclination=InclinationType(value=elements.inclination),
        ra_of_asc_node=AngleType(value=elements.ra_of_asc_node),
        arg_of_pericenter=AngleType(value=elements.arg_of_pericenter),
        mean_anomaly=AngleType(value=elements.mean_anomaly),
        gm=None if elements.gm is None else GmType(value=elements.gm),
    )


def _tle_to_xml(tle: OmmTleParameters | None) -> Any:
    if tle is None:
        return None
    return TleParametersType(
        comment=list(tle.comments),
        ephemeris_type=tle.ephemeris_type,
        classification_type=tle.classification_type,
        norad_cat_id=tle.norad_cat_id,
        element_set_no=tle.element_set_no,
        rev_at_epoch=tle.rev_at_epoch,
        bstar=None if tle.bstar is None else BStarType(value=tle.bstar),
        bterm=None if tle.bterm is None else BTermType(value=tle.bterm),
        mean_motion_dot=DRevType(value=tle.mean_motion_dot),
        mean_motion_ddot=None
        if tle.mean_motion_ddot is None
        else DdRevType(value=tle.mean_motion_ddot),
        agom=None if tle.agom is None else AgomType(value=tle.agom),
    )


def _spacecraft_to_xml(spacecraft: OmmSpacecraftParameters | None) -> Any:
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


def _covariance_to_xml(covariance: OmmCovariance | None) -> Any:
    if covariance is None:
        return None
    elements = {
        name: value_type(value=covariance.matrix[index])
        for index, (name, value_type) in enumerate(_COVARIANCE_LAYOUT)
    }
    return XmlOmmCovariance(
        comment=list(covariance.comments),
        cov_ref_frame=covariance.cov_ref_frame,
        **elements,
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
