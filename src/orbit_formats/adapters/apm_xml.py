"""The APM-XML mapping: the xsdata ``Apm`` binding ↔ the :class:`ApmFile` fidelity model.

The APM-specific half of the CCSDS-XML seam (the generic plumbing lives in
:mod:`orbit_formats.adapters.ccsds_xml`). Maps the populated
:class:`~orbit_formats._ccsds_xsd.Apm` binding to and from the *same*
:class:`~orbit_formats.readers.ccsds_apm.ApmFile` the hand-written KVN reader produces, so an
APM read from either notation is the same model — the precondition for the KVN↔XML parity
assertion. Imported lazily (only when an APM in XML is read or written), never at package
import time.

The KVN orbit-formats writes is version 1.0 and the XML binding is version 2.0. The two carry
the same quaternion content but shape it differently: version-1 KVN names the frames
``Q_FRAME_A`` / ``Q_FRAME_B`` in the quaternion block with its own ``EPOCH`` and a ``Q_DIR``
direction; version-2 XML carries the epoch once at the data level, the frames on the quaternion
state (``REF_FRAME_A`` / ``REF_FRAME_B``), and has no direction field — so a non-default
``Q_DIR`` (``B2A``) inverts the rotation and is reported as lossy, while ``A2B`` (the version-2
assumption) is not.
"""

from __future__ import annotations

from typing import Any

from xsdata.exceptions import ParserError

from orbit_formats._ccsds_xsd import (
    AdmHeader,
    Apm,
    ApmBody,
    ApmData,
    QuaternionDotComponentType,
    QuaternionDotType,
    QuaternionStateType,
    QuaternionType,
)
from orbit_formats._ccsds_xsd import (
    ApmMetadata as XmlApmMetadata,
)
from orbit_formats._ccsds_xsd import (
    ApmSegment as XmlApmSegment,
)
from orbit_formats.adapters.ccsds_xml import parse_ndm_xml, serialize_ndm_xml
from orbit_formats.adapters.oem_xml import _require_for_xml
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import _parse_epoch
from orbit_formats.readers.ccsds_apm import ApmFile, ApmMetadata, ApmQuaternion
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _format_epoch

__all__ = ["apmfile_from_xml", "xml_bytes_from_apmfile"]


# --- XML -> ApmFile --------------------------------------------------------------------


def apmfile_from_xml(data: bytes) -> ApmFile:
    """Parse APM XML ``data`` into an :class:`ApmFile`, tagged ``serialization="xml"``."""
    try:
        apm = parse_ndm_xml(data, Apm)
    except (ParserError, TypeError) as exc:
        raise MalformedSourceError(f"could not parse the APM XML: {exc}") from exc

    segment = apm.body.segment
    meta = segment.metadata
    body = segment.data
    _reject_unsupported_blocks(body)
    return ApmFile(
        ccsds_version=apm.version,
        metadata=ApmMetadata(
            object_name=meta.object_name,
            object_id=meta.object_id,
            time_system=meta.time_system,
            center_name=meta.center_name,
            comments=tuple(meta.comment),
        ),
        quaternion=_quaternion_from_xml(body),
        creation_date=apm.header.creation_date,
        originator=apm.header.originator,
        message_id=apm.header.message_id,
        comments=tuple(apm.header.comment),
        serialization="xml",
    )


def _reject_unsupported_blocks(body: Any) -> None:
    for attribute, label in (
        ("euler_angle_state", "Euler-angle"),
        ("angular_velocity", "angular-velocity"),
        ("spin", "spin"),
        ("inertia", "inertia"),
        ("maneuver_parameters", "maneuver"),
    ):
        if getattr(body, attribute, None):
            raise MalformedSourceError(
                f"unsupported APM {label} block; this release supports the quaternion attitude only"
            )


def _quaternion_from_xml(body: Any) -> ApmQuaternion:
    states = body.quaternion_state
    if len(states) != 1:
        raise MalformedSourceError(
            f"APM XML must carry exactly one quaternion state, got {len(states)}"
        )
    state = states[0]
    quaternion = state.quaternion
    # A <data>-level comment folds into the quaternion comments (KVN's single data level).
    comments = tuple(body.comment) + tuple(state.comment)
    rates = _rates_from_xml(state.quaternion_dot)
    return ApmQuaternion(
        epoch=_parse_epoch(body.epoch),
        q_frame_a=state.ref_frame_a,
        q_frame_b=state.ref_frame_b,
        q1=float(quaternion.q1),
        q2=float(quaternion.q2),
        q3=float(quaternion.q3),
        qc=float(quaternion.qc),
        q1_dot=rates[0],
        q2_dot=rates[1],
        q3_dot=rates[2],
        qc_dot=rates[3],
        comments=comments,
    )


def _rates_from_xml(
    quaternion_dot: Any,
) -> tuple[float | None, float | None, float | None, float | None]:
    if quaternion_dot is None:
        return (None, None, None, None)
    return (
        float(quaternion_dot.q1_dot.value),
        float(quaternion_dot.q2_dot.value),
        float(quaternion_dot.q3_dot.value),
        float(quaternion_dot.qc_dot.value),
    )


# --- ApmFile -> XML --------------------------------------------------------------------


def xml_bytes_from_apmfile(apm: ApmFile) -> bytes:
    """Serialise an :class:`ApmFile` to schema-valid APM XML bytes.

    The mirror of :func:`apmfile_from_xml`. APM XML requires the header ``CREATION_DATE`` and
    ``ORIGINATOR`` that KVN treats as optional; when the model does not carry one a placeholder
    is written and reported, never dropped silently.
    """
    header = AdmHeader(
        comment=list(apm.comments),
        creation_date=_require_for_xml("CREATION_DATE", apm.creation_date),
        originator=_require_for_xml("ORIGINATOR", apm.originator),
        message_id=apm.message_id,
    )
    meta = apm.metadata
    xml_meta = XmlApmMetadata(
        comment=list(meta.comments),
        object_name=meta.object_name,
        object_id=meta.object_id,
        center_name=meta.center_name,
        time_system=meta.time_system,
    )
    quaternion = apm.quaternion
    if quaternion.q_dir is not None and quaternion.q_dir.upper() not in ("A2B", ""):
        warn_lossy(
            LossyConversionWarning(
                "APM XML (v2) has no Q_DIR field and assumes A2B; the B2A direction was dropped",
                dropped=(DroppedField("Q_DIR", "APM XML v2 assumes the A2B rotation direction"),),
            ),
            stacklevel=2,
        )
    data = ApmData(
        comment=list(quaternion.comments),
        epoch=_format_epoch(quaternion.epoch),
        quaternion_state=[
            QuaternionStateType(
                ref_frame_a=quaternion.q_frame_a,
                ref_frame_b=quaternion.q_frame_b,
                quaternion=QuaternionType(
                    q1=quaternion.q1, q2=quaternion.q2, q3=quaternion.q3, qc=quaternion.qc
                ),
                quaternion_dot=_rates_to_xml(quaternion),
            )
        ],
    )
    body = ApmBody(segment=XmlApmSegment(metadata=xml_meta, data=data))
    return serialize_ndm_xml(Apm(header=header, body=body))


def _rates_to_xml(quaternion: ApmQuaternion) -> Any:
    if quaternion.q1_dot is None:
        return None
    return QuaternionDotType(
        q1_dot=QuaternionDotComponentType(value=quaternion.q1_dot),
        q2_dot=QuaternionDotComponentType(value=quaternion.q2_dot),
        q3_dot=QuaternionDotComponentType(value=quaternion.q3_dot),
        qc_dot=QuaternionDotComponentType(value=quaternion.qc_dot),
    )
