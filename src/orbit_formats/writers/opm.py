"""CCSDS OPM writer — KVN and XML serialisers for the Orbit Parameter Message.

Three tiers, picked automatically (as for the OEM and OMM writers):

1. A ``StateVector`` whose ``source_native`` is an
   :class:`~orbit_formats.readers.ccsds_opm.OpmFile` with retained bytes → the verbatim bytes
   are echoed (**byte-identical**).
2. An ``OpmFile`` ``source_native`` without retained bytes → the structured model is
   re-serialised (**content-lossless** — every block preserved: the state vector, the
   Keplerian, spacecraft, covariance, and maneuver blocks, comments, and user-defined
   parameters).
3. Any other ``StateVector`` → an OPM is built from the canonical Cartesian state, warning for
   each OPM-required metadata field the source cannot supply.

The notation is chosen from the destination extension (``.opm`` → KVN, ``.xml`` → XML), else
the source's own notation, else KVN. The XML half lives in
:mod:`orbit_formats.adapters.opm_xml`, imported lazily.
"""

from __future__ import annotations

from typing import Literal

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.state import StateVector
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_omm import _COVARIANCE_KEYS
from orbit_formats.readers.ccsds_opm import (
    OpmCovariance,
    OpmFile,
    OpmKeplerianElements,
    OpmManeuver,
    OpmMetadata,
    OpmSpacecraftParameters,
    OpmStateVector,
)
from orbit_formats.registry import register_writer
from orbit_formats.warnings import (
    DroppedField,
    LossyConversionWarning,
    warn_dropped_maneuvers,
    warn_lossy,
)
from orbit_formats.writers.oem import _comment_lines, _format_epoch, _format_float

__all__ = ["write_opm"]

# The OPM version the synthesised / re-serialised KVN header declares, and the placeholder a
# synthesised OPM uses where the canonical state cannot supply a required metadata value.
_OPM_VERSION = "2.0"
_PLACEHOLDER = "UNKNOWN"

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".opm", ".kvn")


def write_opm(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`StateVector`) to CCSDS OPM bytes, in KVN or XML.

    Picks the byte-identical / content-lossless / synthesised path automatically, and the KVN
    or XML notation from ``suffix`` (the destination extension) else the source's own notation
    else KVN. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is
    not a ``StateVector`` — OPM is a single-state format.
    """
    if not isinstance(obj, StateVector):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-opm", "state")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, OpmFile):
        notation = requested or native.serialization
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_opmfile(native, notation)
    # Synthesising from a non-OPM state: the synthesised OPM holds only the state and metadata,
    # so any canonical maneuvers the object carries cannot be serialised and are reported dropped.
    warn_dropped_maneuvers(obj.maneuvers, target_format="ccsds-opm")
    return _serialize_opmfile(_opmfile_from_state_vector(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_opmfile(opm: OpmFile, notation: Literal["kvn", "xml"]) -> bytes:
    if notation == "xml":
        from orbit_formats.adapters.opm_xml import xml_bytes_from_opmfile

        return xml_bytes_from_opmfile(opm)
    return _serialize_opm_kvn(opm)


# --- synthesised OPM from a canonical state --------------------------------------------


def _opmfile_from_state_vector(state: StateVector) -> OpmFile:
    """Build an :class:`OpmFile` from a canonical ``StateVector``, warning on missing fields.

    Only the mandatory state vector and metadata are synthesised: the optional Keplerian block
    is a redundant restatement of the Cartesian state (no orbital information is lost by
    omitting it), and the covariance / maneuver / spacecraft blocks only exist on a real
    OPM's ``source_native``, which this path does not have. Each OPM-required metadata field
    the canonical state cannot supply is placeholdered and reported, never dropped silently.
    """
    md = state.metadata
    metadata = OpmMetadata(
        object_name=_required("OBJECT_NAME", md.object_name),
        object_id=_required("OBJECT_ID", md.object_id),
        center_name=_required("CENTER_NAME", md.central_body),
        ref_frame=_required("REF_FRAME", md.reference_frame),
        time_system=_required("TIME_SYSTEM", md.time_scale),
    )
    state_vector = OpmStateVector(
        epoch=state.epoch,
        x=float(state.position[0]),
        y=float(state.position[1]),
        z=float(state.position[2]),
        x_dot=float(state.velocity[0]),
        y_dot=float(state.velocity[1]),
        z_dot=float(state.velocity[2]),
    )
    return OpmFile(
        ccsds_version=_OPM_VERSION,
        metadata=metadata,
        state_vector=state_vector,
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
    )


def _required(keyword: str, value: str | None) -> str:
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the state vector does not supply the OPM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical state vector did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


# --- KVN serialisation -----------------------------------------------------------------


def _serialize_opm_kvn(opm: OpmFile) -> bytes:
    """Serialise an :class:`OpmFile` to canonical OPM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_OPM_VERS = {opm.ccsds_version}"]
    lines.extend(_comment_lines(opm.comments))
    if opm.creation_date is not None:
        lines.append(f"CREATION_DATE = {opm.creation_date}")
    if opm.originator is not None:
        lines.append(f"ORIGINATOR = {opm.originator}")
    if opm.message_id is not None:
        lines.append(f"MESSAGE_ID = {opm.message_id}")

    lines.extend(_comment_lines(opm.metadata.comments))
    lines.extend(_serialize_metadata(opm.metadata))

    lines.extend(_comment_lines(opm.state_vector.comments))
    lines.extend(_serialize_state_vector(opm.state_vector))

    if opm.keplerian is not None:
        lines.extend(_comment_lines(opm.keplerian.comments))
        lines.extend(_serialize_keplerian(opm.keplerian))

    if opm.spacecraft_parameters is not None:
        lines.extend(_comment_lines(opm.spacecraft_parameters.comments))
        lines.extend(_serialize_spacecraft(opm.spacecraft_parameters))

    if opm.covariance is not None:
        lines.extend(_comment_lines(opm.covariance.comments))
        lines.extend(_serialize_covariance(opm.covariance))

    for maneuver in opm.maneuvers:
        lines.extend(_comment_lines(maneuver.comments))
        lines.extend(_serialize_maneuver(maneuver))

    if opm.user_defined or opm.user_defined_comments:
        lines.extend(_comment_lines(opm.user_defined_comments))
        lines.extend(f"USER_DEFINED_{key} = {value}" for key, value in opm.user_defined)

    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_metadata(meta: OpmMetadata) -> list[str]:
    ordered: tuple[tuple[str, str | None], ...] = (
        ("OBJECT_NAME", meta.object_name),
        ("OBJECT_ID", meta.object_id),
        ("CENTER_NAME", meta.center_name),
        ("REF_FRAME", meta.ref_frame),
        ("REF_FRAME_EPOCH", meta.ref_frame_epoch),
        ("TIME_SYSTEM", meta.time_system),
    )
    return [f"{key} = {value}" for key, value in ordered if value is not None]


def _serialize_state_vector(state: OpmStateVector) -> list[str]:
    out = [f"EPOCH = {_format_epoch(state.epoch)}"]
    out.extend(
        f"{key} = {_format_float(value)}"
        for key, value in (
            ("X", state.x),
            ("Y", state.y),
            ("Z", state.z),
            ("X_DOT", state.x_dot),
            ("Y_DOT", state.y_dot),
            ("Z_DOT", state.z_dot),
        )
    )
    return out


def _serialize_keplerian(keplerian: OpmKeplerianElements) -> list[str]:
    out = [
        f"{key} = {_format_float(value)}"
        for key, value in (
            ("SEMI_MAJOR_AXIS", keplerian.semi_major_axis),
            ("ECCENTRICITY", keplerian.eccentricity),
            ("INCLINATION", keplerian.inclination),
            ("RA_OF_ASC_NODE", keplerian.ra_of_asc_node),
            ("ARG_OF_PERICENTER", keplerian.arg_of_pericenter),
        )
    ]
    if keplerian.true_anomaly is not None:
        out.append(f"TRUE_ANOMALY = {_format_float(keplerian.true_anomaly)}")
    if keplerian.mean_anomaly is not None:
        out.append(f"MEAN_ANOMALY = {_format_float(keplerian.mean_anomaly)}")
    out.append(f"GM = {_format_float(keplerian.gm)}")
    return out


def _serialize_spacecraft(spacecraft: OpmSpacecraftParameters) -> list[str]:
    ordered: tuple[tuple[str, float | None], ...] = (
        ("MASS", spacecraft.mass),
        ("SOLAR_RAD_AREA", spacecraft.solar_rad_area),
        ("SOLAR_RAD_COEFF", spacecraft.solar_rad_coeff),
        ("DRAG_AREA", spacecraft.drag_area),
        ("DRAG_COEFF", spacecraft.drag_coeff),
    )
    return [f"{key} = {_format_float(value)}" for key, value in ordered if value is not None]


def _serialize_covariance(covariance: OpmCovariance) -> list[str]:
    out: list[str] = []
    if covariance.cov_ref_frame is not None:
        out.append(f"COV_REF_FRAME = {covariance.cov_ref_frame}")
    out.extend(
        f"{key} = {_format_float(value)}"
        for key, value in zip(_COVARIANCE_KEYS, covariance.matrix, strict=True)
    )
    return out


def _serialize_maneuver(maneuver: OpmManeuver) -> list[str]:
    return [
        f"MAN_EPOCH_IGNITION = {_format_epoch(maneuver.man_epoch_ignition)}",
        f"MAN_DURATION = {_format_float(maneuver.man_duration)}",
        f"MAN_DELTA_MASS = {_format_float(maneuver.man_delta_mass)}",
        f"MAN_REF_FRAME = {maneuver.man_ref_frame}",
        f"MAN_DV_1 = {_format_float(maneuver.man_dv_1)}",
        f"MAN_DV_2 = {_format_float(maneuver.man_dv_2)}",
        f"MAN_DV_3 = {_format_float(maneuver.man_dv_3)}",
    ]


register_writer("ccsds-opm", write_opm)
