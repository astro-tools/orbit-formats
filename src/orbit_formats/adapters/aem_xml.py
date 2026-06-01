"""The AEM-XML mapping: the xsdata ``Aem`` binding ↔ the :class:`AemFile` fidelity model.

The AEM-specific half of the CCSDS-XML seam (the generic plumbing lives in
:mod:`orbit_formats.adapters.ccsds_xml`). Maps the populated
:class:`~orbit_formats._ccsds_xsd.Aem` binding to and from the *same*
:class:`~orbit_formats.readers.ccsds_aem.AemFile` the hand-written KVN reader produces, so an
AEM read from either notation is the same model — the precondition for the KVN↔XML parity
assertion. Imported lazily (only when an AEM in XML is read or written), never at package
import time.

The KVN orbit-formats writes is version 1.0 and the XML binding is version 2.0; the two carry
the same attitude content, so the version-only fields differ. The version-1 ``ATTITUDE_DIR``
and ``QUATERNION_TYPE`` notation tags have no version-2 XML home: dropping them changes no
attitude value (the canonical records are already scalar-last), so the cross-notation write is
lossless, except a non-default ``ATTITUDE_DIR`` (``B2A``) genuinely inverts the rotation and is
reported through the lossy-conversion framework. The Euler rotation sequence is the numeric
form (``321``) in KVN and the axis form (``ZYX``) in XML; it is mapped both ways here.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray
from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    AdmHeader,
    Aem,
    AemBody,
    AemData,
    AemMetadata,
    AngleRateType,
    AngleType,
    AttitudeStateType,
    AttitudeTypeType,
    EulerAngleType,
    QuaternionEphemerisType,
    QuaternionType,
    RotseqType,
    SpinType,
)
from orbit_formats._ccsds_xsd import (
    AemSegment as XmlAemSegment,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.adapters.oem_xml import _require_for_xml
from orbit_formats.canonical.attitude import ATTITUDE_TYPES
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import _datetime_array, _parse_epoch
from orbit_formats.readers.ccsds_aem import AemFile, AemSegment, AemSegmentMeta
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _format_epoch

__all__ = ["aemfile_from_xml", "xml_bytes_from_aemfile"]

# The Euler rotation sequence is numeric in KVN (``321``) and axis-lettered in XML (``ZYX``).
_DIGIT_TO_AXIS = {"1": "X", "2": "Y", "3": "Z"}
_AXIS_TO_DIGIT = {"X": "1", "Y": "2", "Z": "3"}


# --- XML -> AemFile --------------------------------------------------------------------


def aemfile_from_xml(data: bytes) -> AemFile:
    """Parse AEM XML ``data`` into an :class:`AemFile`, tagged ``serialization="xml"``."""
    try:
        aem = parse_ndm_xml(data, Aem)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the AEM XML: {exc}") from exc

    segments = tuple(_segment_from_xml(segment) for segment in aem.body.segment)
    if not segments:
        raise MalformedSourceError("not a valid AEM: the XML body has no segment")
    return AemFile(
        ccsds_version=aem.version,
        segments=segments,
        creation_date=aem.header.creation_date,
        originator=aem.header.originator,
        comments=tuple(aem.header.comment),
        serialization="xml",
    )


def _segment_from_xml(segment: Any) -> AemSegment:
    meta = _meta_from_xml(segment.metadata)
    epochs, records = _records_from_xml(segment.data.attitude_state, meta.attitude_type)
    return AemSegment(
        meta=meta, epochs=epochs, records=records, comments=tuple(segment.data.comment)
    )


def _meta_from_xml(meta: Any) -> AemSegmentMeta:
    return AemSegmentMeta(
        object_name=meta.object_name,
        object_id=meta.object_id,
        center_name=meta.center_name,
        ref_frame_a=meta.ref_frame_a,
        ref_frame_b=meta.ref_frame_b,
        time_system=meta.time_system,
        start_time=meta.start_time,
        stop_time=meta.stop_time,
        attitude_type=_attitude_type_from_xml(meta.attitude_type),
        useable_start_time=meta.useable_start_time,
        useable_stop_time=meta.useable_stop_time,
        euler_rot_seq=_rotseq_from_xml(meta.euler_rot_seq),
        interpolation_method=meta.interpolation_method,
        interpolation_degree=meta.interpolation_degree,
        comments=tuple(meta.comment),
    )


def _attitude_type_from_xml(attitude_type: Any) -> str:
    token = str(attitude_type.value).upper()
    if token not in ATTITUDE_TYPES:
        raise MalformedSourceError(
            f"unsupported AEM ATTITUDE_TYPE {attitude_type.value!r}; "
            f"orbit-formats supports {', '.join(sorted(ATTITUDE_TYPES))}"
        )
    return token


def _records_from_xml(
    states: list[Any], attitude_type: str
) -> tuple[NDArray[np.datetime64], NDArray[np.float64]]:
    epochs: list[np.datetime64] = []
    rows: list[list[float]] = []
    for state in states:
        epoch, components = _attitude_state_from_xml(state, attitude_type)
        epochs.append(epoch)
        rows.append(components)
    width = len(ATTITUDE_TYPES[attitude_type])
    matrix = np.array(rows, dtype=np.float64) if rows else np.empty((0, width), dtype=np.float64)
    return _datetime_array(epochs), matrix


def _attitude_state_from_xml(state: Any, attitude_type: str) -> tuple[np.datetime64, list[float]]:
    if attitude_type == "QUATERNION":
        block = _require_block(state.quaternion_ephemeris, "quaternionEphemeris")
        quaternion = block.quaternion
        return _parse_epoch(block.epoch), [
            float(quaternion.q1),
            float(quaternion.q2),
            float(quaternion.q3),
            float(quaternion.qc),
        ]
    if attitude_type == "EULER_ANGLE":
        block = _require_block(state.euler_angle, "eulerAngle")
        return _parse_epoch(block.epoch), [
            float(block.angle_1.value),
            float(block.angle_2.value),
            float(block.angle_3.value),
        ]
    block = _require_block(state.spin, "spin")
    return _parse_epoch(block.epoch), [
        float(block.spin_alpha.value),
        float(block.spin_delta.value),
        float(block.spin_angle.value),
        float(block.spin_angle_vel.value),
    ]


def _require_block(block: Any, element: str) -> Any:
    if block is None:
        raise MalformedSourceError(
            f"AEM XML attitude state is missing the expected <{element}> for its ATTITUDE_TYPE"
        )
    return block


def _rotseq_from_xml(euler_rot_seq: Any) -> str | None:
    if euler_rot_seq is None:
        return None
    return "".join(_AXIS_TO_DIGIT.get(axis, axis) for axis in str(euler_rot_seq.value))


# --- AemFile -> XML --------------------------------------------------------------------


def xml_bytes_from_aemfile(aem: AemFile) -> bytes:
    """Serialise an :class:`AemFile` to schema-valid AEM XML bytes.

    The mirror of :func:`aemfile_from_xml`. AEM XML requires the header ``CREATION_DATE`` and
    ``ORIGINATOR`` that KVN treats as optional; when the model does not carry one a placeholder
    is written and reported, never dropped silently.
    """
    header = AdmHeader(
        comment=list(aem.comments),
        creation_date=_require_for_xml("CREATION_DATE", aem.creation_date),
        originator=_require_for_xml("ORIGINATOR", aem.originator),
    )
    body = AemBody(segment=[_segment_to_xml(segment) for segment in aem.segments])
    return serialize_ndm_xml(Aem(header=header, body=body))


def _segment_to_xml(segment: AemSegment) -> Any:
    meta = segment.meta
    if meta.attitude_dir is not None and meta.attitude_dir.upper() not in ("A2B", ""):
        # The version-2 XML schema has no ATTITUDE_DIR and assumes A2B; a B2A direction
        # inverts the rotation and is genuinely lost — reported, never silent.
        warn_lossy(
            LossyConversionWarning(
                "AEM XML (v2) has no ATTITUDE_DIR field and assumes A2B; the B2A direction "
                "was dropped",
                dropped=(
                    DroppedField("ATTITUDE_DIR", "AEM XML v2 assumes the A2B rotation direction"),
                ),
            ),
            stacklevel=3,
        )
    xml_meta = AemMetadata(
        comment=list(meta.comments),
        object_name=meta.object_name,
        object_id=meta.object_id,
        center_name=meta.center_name,
        ref_frame_a=meta.ref_frame_a,
        ref_frame_b=meta.ref_frame_b,
        time_system=meta.time_system,
        start_time=meta.start_time,
        useable_start_time=meta.useable_start_time,
        useable_stop_time=meta.useable_stop_time,
        stop_time=meta.stop_time,
        attitude_type=AttitudeTypeType(meta.attitude_type),
        euler_rot_seq=_rotseq_to_xml(meta.euler_rot_seq),
        interpolation_method=meta.interpolation_method,
        interpolation_degree=meta.interpolation_degree,
    )
    data = AemData(
        comment=list(segment.comments),
        attitude_state=[
            _attitude_state_to_xml(segment, index) for index in range(len(segment.epochs))
        ],
    )
    return XmlAemSegment(metadata=xml_meta, data=data)


def _attitude_state_to_xml(segment: AemSegment, index: int) -> Any:
    epoch = _format_epoch(segment.epochs[index])
    components = segment.records[index]
    attitude_type = segment.meta.attitude_type
    if attitude_type == "QUATERNION":
        return AttitudeStateType(
            quaternion_ephemeris=QuaternionEphemerisType(
                epoch=epoch,
                quaternion=QuaternionType(
                    q1=float(components[0]),
                    q2=float(components[1]),
                    q3=float(components[2]),
                    qc=float(components[3]),
                ),
            )
        )
    if attitude_type == "EULER_ANGLE":
        return AttitudeStateType(
            euler_angle=EulerAngleType(
                epoch=epoch,
                angle_1=AngleType(value=float(components[0])),
                angle_2=AngleType(value=float(components[1])),
                angle_3=AngleType(value=float(components[2])),
            )
        )
    return AttitudeStateType(
        spin=SpinType(
            epoch=epoch,
            spin_alpha=AngleType(value=float(components[0])),
            spin_delta=AngleType(value=float(components[1])),
            spin_angle=AngleType(value=float(components[2])),
            spin_angle_vel=AngleRateType(value=float(components[3])),
        )
    )


def _rotseq_to_xml(euler_rot_seq: str | None) -> RotseqType | None:
    if euler_rot_seq is None:
        return None
    sequence = euler_rot_seq.strip()
    if all(digit in _DIGIT_TO_AXIS for digit in sequence):
        sequence = "".join(_DIGIT_TO_AXIS[digit] for digit in sequence)
    return RotseqType(sequence.upper())
