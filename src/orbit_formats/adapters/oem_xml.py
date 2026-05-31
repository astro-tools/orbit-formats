"""The OEM-XML mapping: the xsdata ``Oem`` binding ↔ the :class:`OemFile` fidelity model.

This is the OEM-specific half of the CCSDS-XML seam. The generic plumbing —
NDM/XML bytes ↔ a populated binding — lives in :mod:`orbit_formats.adapters.ccsds_xml`;
here we map the populated :class:`~orbit_formats._ccsds_xsd.Oem` binding to and from the
*same* :class:`~orbit_formats.readers.ccsds.OemFile` the hand-written KVN reader produces.
Routing both notations through one fidelity model is what makes the KVN↔XML round-trip and
the parity assertion possible — an OEM read from either notation is the same model, and a
write re-emits it in whichever notation is asked for.

The module imports the large generated binding module, so it is imported lazily (only when
an OEM in XML is actually read or written), never at package import time — mirroring
:mod:`orbit_formats.adapters.ccsds_xml`.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    AccType,
    AccUnits,
    OdmHeader,
    Oem,
    OemBody,
    OemData,
    OemMetadata,
    PositionCovarianceType,
    PositionTypeUo,
    PositionUnits,
    PositionVelocityCovarianceType,
    StateVectorAccType,
    VelocityCovarianceType,
    VelocityTypeUo,
    VelocityUnits,
)
from orbit_formats._ccsds_xsd import (
    OemCovarianceMatrixType as XmlOemCovariance,
)
from orbit_formats._ccsds_xsd import (
    OemSegment as XmlOemSegment,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.errors import MalformedSourceError

# The KVN reader/writer's epoch and array helpers are reused verbatim so the two notations
# produce byte-for-byte identical canonical values — the precondition for the KVN↔XML
# parity assertion. They are package-internal helpers of the same OEM format.
from orbit_formats.readers.ccsds import (
    OemCovariance,
    OemFile,
    OemSegment,
    OemSegmentMeta,
    _datetime_array,
    _float_matrix,
    _parse_epoch,
)
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _format_epoch

__all__ = ["oemfile_from_xml", "xml_bytes_from_oemfile"]

_PLACEHOLDER = "UNKNOWN"

# The 21 lower-triangular elements of the symmetric 6x6 covariance, in row order, paired
# with the binding value type each is expressed as (position-position, position-velocity,
# velocity-velocity). The order is the same row order :class:`OemCovariance.matrix` uses,
# so element ``i`` of the matrix tuple maps to entry ``i`` here.
_COVARIANCE_LAYOUT: tuple[tuple[str, Any], ...] = (
    ("cx_x", PositionCovarianceType),
    ("cy_x", PositionCovarianceType),
    ("cy_y", PositionCovarianceType),
    ("cz_x", PositionCovarianceType),
    ("cz_y", PositionCovarianceType),
    ("cz_z", PositionCovarianceType),
    ("cx_dot_x", PositionVelocityCovarianceType),
    ("cx_dot_y", PositionVelocityCovarianceType),
    ("cx_dot_z", PositionVelocityCovarianceType),
    ("cx_dot_x_dot", VelocityCovarianceType),
    ("cy_dot_x", PositionVelocityCovarianceType),
    ("cy_dot_y", PositionVelocityCovarianceType),
    ("cy_dot_z", PositionVelocityCovarianceType),
    ("cy_dot_x_dot", VelocityCovarianceType),
    ("cy_dot_y_dot", VelocityCovarianceType),
    ("cz_dot_x", PositionVelocityCovarianceType),
    ("cz_dot_y", PositionVelocityCovarianceType),
    ("cz_dot_z", PositionVelocityCovarianceType),
    ("cz_dot_x_dot", VelocityCovarianceType),
    ("cz_dot_y_dot", VelocityCovarianceType),
    ("cz_dot_z_dot", VelocityCovarianceType),
)


# --- XML -> OemFile --------------------------------------------------------------------


def oemfile_from_xml(data: bytes) -> OemFile:
    """Parse OEM XML ``data`` into an :class:`OemFile`, tagged ``serialization="xml"``.

    The whole document is bound by the xsdata parser, then mapped field-for-field into the
    fidelity model the KVN reader also produces, so an OEM read from XML is indistinguishable
    in content from the same OEM read from KVN. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for XML that is not well-formed or
    does not match the OEM schema (a missing required element included).
    """
    try:
        oem = parse_ndm_xml(data, Oem)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the OEM XML: {exc}") from exc

    segments = tuple(_segment_from_xml(segment) for segment in oem.body.segment)
    if not segments:
        raise MalformedSourceError("not a valid OEM: the XML body has no segment")
    return OemFile(
        ccsds_version=oem.version,
        segments=segments,
        creation_date=oem.header.creation_date,
        originator=oem.header.originator,
        comments=tuple(oem.header.comment),
        serialization="xml",
    )


def _segment_from_xml(segment: Any) -> OemSegment:
    epochs, positions, velocities, accelerations = _states_from_xml(segment.data.state_vector)
    covariances = tuple(_covariance_from_xml(cov) for cov in segment.data.covariance_matrix)
    return OemSegment(
        meta=_meta_from_xml(segment.metadata),
        epochs=epochs,
        positions=positions,
        velocities=velocities,
        accelerations=accelerations,
        covariances=covariances,
        comments=tuple(segment.data.comment),
    )


def _meta_from_xml(meta: Any) -> OemSegmentMeta:
    # OEM XML is schema-closed: it has no slot for non-standard keywords, so ``extra`` is
    # always empty (the KVN ``extra`` channel has no XML counterpart).
    return OemSegmentMeta(
        object_name=meta.object_name,
        object_id=meta.object_id,
        center_name=meta.center_name,
        ref_frame=meta.ref_frame,
        time_system=meta.time_system,
        start_time=meta.start_time,
        stop_time=meta.stop_time,
        ref_frame_epoch=meta.ref_frame_epoch,
        useable_start_time=meta.useable_start_time,
        useable_stop_time=meta.useable_stop_time,
        interpolation=meta.interpolation,
        interpolation_degree=meta.interpolation_degree,
        comments=tuple(meta.comment),
    )


def _states_from_xml(
    states: list[Any],
) -> tuple[
    NDArray[np.datetime64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64] | None
]:
    epochs: list[np.datetime64] = []
    positions: list[list[float]] = []
    velocities: list[list[float]] = []
    accelerations: list[list[float]] = []
    saw_accel = False
    saw_no_accel = False
    for state in states:
        epochs.append(_parse_epoch(state.epoch))
        positions.append([float(state.x.value), float(state.y.value), float(state.z.value)])
        velocities.append(
            [float(state.x_dot.value), float(state.y_dot.value), float(state.z_dot.value)]
        )
        acceleration = _acceleration_triplet(state)
        if acceleration is None:
            saw_no_accel = True
        else:
            saw_accel = True
            accelerations.append(acceleration)
    if saw_accel and saw_no_accel:
        raise MalformedSourceError(
            "OEM XML segment mixes state vectors with and without acceleration"
        )
    return (
        _datetime_array(epochs),
        _float_matrix(positions),
        _float_matrix(velocities),
        _float_matrix(accelerations) if saw_accel else None,
    )


def _acceleration_triplet(state: Any) -> list[float] | None:
    """The acceleration triplet of a state vector, or ``None`` when it carries none.

    CCSDS requires acceleration to be all-three-or-none on a state vector; a partial triplet
    is rejected as malformed.
    """
    components = (state.x_ddot, state.y_ddot, state.z_ddot)
    present = [component for component in components if component is not None]
    if not present:
        return None
    if len(present) != 3:
        raise MalformedSourceError("OEM XML state vector has a partial acceleration triplet")
    return [float(state.x_ddot.value), float(state.y_ddot.value), float(state.z_ddot.value)]


def _covariance_from_xml(covariance: Any) -> OemCovariance:
    matrix = tuple(float(getattr(covariance, name).value) for name, _ in _COVARIANCE_LAYOUT)
    return OemCovariance(
        epoch=_parse_epoch(covariance.epoch),
        matrix=matrix,
        cov_ref_frame=covariance.cov_ref_frame,
        comments=tuple(covariance.comment),
    )


# --- OemFile -> XML --------------------------------------------------------------------


def xml_bytes_from_oemfile(oem: OemFile) -> bytes:
    """Serialise an :class:`OemFile` to schema-valid OEM XML bytes.

    The mirror of :func:`oemfile_from_xml`. Position / velocity / acceleration carry their
    canonical units (``km`` / ``km/s`` / ``km/s**2``). OEM XML additionally requires the
    header ``CREATION_DATE`` and ``ORIGINATOR`` that KVN treats as optional; when the model
    does not carry one (a synthesised or KVN-sourced OEM), a placeholder is written and the
    loss is reported through the lossy-conversion framework, never dropped silently.
    """
    header = OdmHeader(
        comment=list(oem.comments),
        creation_date=_require_for_xml("CREATION_DATE", oem.creation_date),
        originator=_require_for_xml("ORIGINATOR", oem.originator),
    )
    body = OemBody(segment=[_segment_to_xml(segment) for segment in oem.segments])
    return serialize_ndm_xml(Oem(header=header, body=body))


def _require_for_xml(keyword: str, value: str | None) -> str:
    """Return ``value`` for a header field the NDM/XML schema requires, or warn + placeholder.

    Shared by the OEM and OMM XML writers: NDM/XML requires the header ``CREATION_DATE`` and
    ``ORIGINATOR`` that KVN treats as optional, so a source that does not carry one is
    placeholdered and the loss reported, never dropped silently.
    """
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the source does not supply the NDM/XML-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical object did not carry it"),),
        ),
        stacklevel=2,
    )
    return _PLACEHOLDER


def _segment_to_xml(segment: OemSegment) -> Any:
    if segment.meta.extra:
        # OEM XML is schema-closed; the non-standard KVN keywords a cross-notation write
        # carries have no XML field and are dropped — reported, never silent.
        warn_lossy(
            LossyConversionWarning(
                "OEM XML has no field for non-standard META keyword(s); they were dropped",
                dropped=tuple(
                    DroppedField(key, "OEM XML is schema-closed; non-standard keywords are lost")
                    for key, _ in segment.meta.extra
                ),
            ),
            stacklevel=2,
        )
    meta = segment.meta
    xml_meta = OemMetadata(
        comment=list(meta.comments),
        object_name=meta.object_name,
        object_id=meta.object_id,
        center_name=meta.center_name,
        ref_frame=meta.ref_frame,
        ref_frame_epoch=meta.ref_frame_epoch,
        time_system=meta.time_system,
        start_time=meta.start_time,
        useable_start_time=meta.useable_start_time,
        useable_stop_time=meta.useable_stop_time,
        stop_time=meta.stop_time,
        interpolation=meta.interpolation,
        interpolation_degree=meta.interpolation_degree,
    )
    data = OemData(
        comment=list(segment.comments),
        state_vector=[_state_to_xml(segment, index) for index in range(len(segment.epochs))],
        covariance_matrix=[_covariance_to_xml(cov) for cov in segment.covariances],
    )
    return XmlOemSegment(metadata=xml_meta, data=data)


def _state_to_xml(segment: OemSegment, index: int) -> Any:
    position = segment.positions[index]
    velocity = segment.velocities[index]
    fields: dict[str, Any] = {
        "epoch": _format_epoch(segment.epochs[index]),
        "x": PositionTypeUo(value=float(position[0]), units=PositionUnits.KM),
        "y": PositionTypeUo(value=float(position[1]), units=PositionUnits.KM),
        "z": PositionTypeUo(value=float(position[2]), units=PositionUnits.KM),
        "x_dot": VelocityTypeUo(value=float(velocity[0]), units=VelocityUnits.KM_S),
        "y_dot": VelocityTypeUo(value=float(velocity[1]), units=VelocityUnits.KM_S),
        "z_dot": VelocityTypeUo(value=float(velocity[2]), units=VelocityUnits.KM_S),
    }
    if segment.accelerations is not None:
        acceleration = segment.accelerations[index]
        fields["x_ddot"] = AccType(value=float(acceleration[0]), units=AccUnits.KM_S_2)
        fields["y_ddot"] = AccType(value=float(acceleration[1]), units=AccUnits.KM_S_2)
        fields["z_ddot"] = AccType(value=float(acceleration[2]), units=AccUnits.KM_S_2)
    return StateVectorAccType(**fields)


def _covariance_to_xml(covariance: OemCovariance) -> Any:
    elements = {
        name: value_type(value=covariance.matrix[index])
        for index, (name, value_type) in enumerate(_COVARIANCE_LAYOUT)
    }
    return XmlOemCovariance(
        comment=list(covariance.comments),
        epoch=_format_epoch(covariance.epoch),
        cov_ref_frame=covariance.cov_ref_frame,
        **elements,
    )
