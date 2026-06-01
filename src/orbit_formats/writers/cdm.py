"""CCSDS CDM writer — KVN and XML serialisers for the Conjunction Data Message.

Three tiers, picked automatically (as for the OPM / APM writers):

1. A ``Conjunction`` whose ``source_native`` is a
   :class:`~orbit_formats.readers.ccsds_cdm.CdmFile` with retained bytes → the verbatim bytes
   are echoed (**byte-identical**).
2. A ``CdmFile`` ``source_native`` without retained bytes → the structured fidelity model is
   re-serialised (**content-lossless** — every object, the relative block, the covariances, and
   the comments preserved).
3. Any other ``Conjunction`` → a CDM is built from the canonical record, warning for each
   CDM-required field the canonical form cannot supply.

The notation is chosen from the destination extension (``.cdm`` → KVN, ``.xml`` → XML), else the
source's own notation, else KVN. Dimensioned KVN values carry their bracketed unit suffix
(``MISS_DISTANCE = 715.0 [m]``). The XML half lives in
:mod:`orbit_formats.adapters.cdm_xml`, imported lazily.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.conjunction import Conjunction, ConjunctionObject
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_cdm import (
    _COV_MANDATORY,
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
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _comment_lines, _format_epoch, _format_float

__all__ = ["write_cdm"]

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".cdm", ".kvn")

_CDM_VERSION = "1.0"
_PLACEHOLDER = "UNKNOWN"


def write_cdm(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`Conjunction`) to CCSDS CDM bytes (KVN or XML).

    Picks the byte-identical / content-lossless / synthesised path automatically, and the KVN
    or XML notation from ``suffix`` else the source's own notation else KVN. Raises
    :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not a
    ``Conjunction`` — the CDM is the conjunction category's only format.
    """
    if not isinstance(obj, Conjunction):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-cdm", "conjunction")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, CdmFile):
        notation = requested or native.serialization
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_cdmfile(native, notation)
    return _serialize_cdmfile(_cdmfile_from_conjunction(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_cdmfile(cdm: CdmFile, notation: Literal["kvn", "xml"]) -> bytes:
    if notation == "xml":
        from orbit_formats.adapters.cdm_xml import xml_bytes_from_cdm

        return xml_bytes_from_cdm(cdm)
    return _serialize_cdm_kvn(cdm)


# --- synthesised CDM from a canonical conjunction --------------------------------------


def _cdmfile_from_conjunction(conjunction: Conjunction) -> CdmFile:
    """Build a :class:`CdmFile` from a canonical ``Conjunction``, warning on missing fields."""
    md = conjunction.metadata
    relative = CdmRelativeMetadata(
        tca=conjunction.tca,
        miss_distance=conjunction.miss_distance,
        relative_speed=conjunction.relative_speed,
        relative_position=_triplet(conjunction.relative_position),
        relative_velocity=_triplet(conjunction.relative_velocity),
    )
    return CdmFile(
        ccsds_version=_CDM_VERSION,
        relative=relative,
        objects=(
            _object_from_canonical(conjunction.objects[0]),
            _object_from_canonical(conjunction.objects[1]),
        ),
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
    )


def _object_from_canonical(obj: ConjunctionObject) -> CdmObject:
    metadata = CdmObjectMetadata(
        object_value=obj.label,
        object_designator=obj.object_designator,
        catalog_name=_required("CATALOG_NAME", obj.catalog_name),
        object_name=_required("OBJECT_NAME", obj.object_name),
        international_designator=_required(
            "INTERNATIONAL_DESIGNATOR", obj.international_designator
        ),
        ephemeris_name=_required("EPHEMERIS_NAME", None),
        covariance_method=_required("COVARIANCE_METHOD", None),
        maneuverable=_required("MANEUVERABLE", None),
        ref_frame=obj.ref_frame,
    )
    state = CdmStateVector(
        x=float(obj.state[0]),
        y=float(obj.state[1]),
        z=float(obj.state[2]),
        x_dot=float(obj.state[3]),
        y_dot=float(obj.state[4]),
        z_dot=float(obj.state[5]),
    )
    covariance = CdmCovariance(matrix=_lower_from_symmetric(obj.covariance))
    return CdmObject(metadata=metadata, state=state, covariance=covariance)


def _triplet(value: NDArray[np.float64] | None) -> tuple[float, float, float] | None:
    if value is None:
        return None
    return (float(value[0]), float(value[1]), float(value[2]))


def _lower_from_symmetric(matrix: NDArray[np.float64]) -> tuple[float, ...]:
    """Extract the 21 lower-triangular elements (row order) of a symmetric 6x6 covariance."""
    return tuple(float(matrix[row, col]) for row in range(6) for col in range(row + 1))


def _required(keyword: str, value: str | None) -> str:
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the conjunction does not supply the CDM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical conjunction did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


# --- KVN serialisation -----------------------------------------------------------------


def _serialize_cdm_kvn(cdm: CdmFile) -> bytes:
    """Serialise a :class:`CdmFile` to canonical CDM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_CDM_VERS = {cdm.ccsds_version}"]
    lines.extend(_comment_lines(cdm.comments))
    if cdm.creation_date is not None:
        lines.append(f"CREATION_DATE = {cdm.creation_date}")
    if cdm.originator is not None:
        lines.append(f"ORIGINATOR = {cdm.originator}")
    if cdm.message_for is not None:
        lines.append(f"MESSAGE_FOR = {cdm.message_for}")
    if cdm.message_id is not None:
        lines.append(f"MESSAGE_ID = {cdm.message_id}")

    lines.append("")
    lines.extend(_serialize_relative(cdm.relative))

    for obj in cdm.objects:
        lines.append("")
        lines.extend(_serialize_object(obj))

    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_relative(rel: CdmRelativeMetadata) -> list[str]:
    out = _comment_lines(rel.comments)
    out.append(f"TCA = {_format_epoch(rel.tca)}")
    out.append(_dim("MISS_DISTANCE", rel.miss_distance, "m"))
    if rel.relative_speed is not None:
        out.append(_dim("RELATIVE_SPEED", rel.relative_speed, "m/s"))
    if rel.relative_position is not None:
        out.extend(
            _dim(f"RELATIVE_POSITION_{axis}", value, "m")
            for axis, value in zip("RTN", rel.relative_position, strict=True)
        )
    if rel.relative_velocity is not None:
        out.extend(
            _dim(f"RELATIVE_VELOCITY_{axis}", value, "m/s")
            for axis, value in zip("RTN", rel.relative_velocity, strict=True)
        )
    if rel.start_screen_period is not None:
        out.append(f"START_SCREEN_PERIOD = {rel.start_screen_period}")
    if rel.stop_screen_period is not None:
        out.append(f"STOP_SCREEN_PERIOD = {rel.stop_screen_period}")
    if rel.screen_volume_frame is not None:
        out.append(f"SCREEN_VOLUME_FRAME = {rel.screen_volume_frame}")
    if rel.screen_volume_shape is not None:
        out.append(f"SCREEN_VOLUME_SHAPE = {rel.screen_volume_shape}")
    for axis, value in (
        ("X", rel.screen_volume_x),
        ("Y", rel.screen_volume_y),
        ("Z", rel.screen_volume_z),
    ):
        if value is not None:
            out.append(_dim(f"SCREEN_VOLUME_{axis}", value, "m"))
    if rel.screen_entry_time is not None:
        out.append(f"SCREEN_ENTRY_TIME = {rel.screen_entry_time}")
    if rel.screen_exit_time is not None:
        out.append(f"SCREEN_EXIT_TIME = {rel.screen_exit_time}")
    if rel.collision_probability is not None:
        out.append(f"COLLISION_PROBABILITY = {_format_float(rel.collision_probability)}")
    if rel.collision_probability_method is not None:
        out.append(f"COLLISION_PROBABILITY_METHOD = {rel.collision_probability_method}")
    return out


def _serialize_object(obj: CdmObject) -> list[str]:
    out = _serialize_object_meta(obj.metadata)
    if obj.od_parameters is not None:
        out.extend(_serialize_od(obj.od_parameters))
    if obj.additional_parameters is not None:
        out.extend(_serialize_add(obj.additional_parameters))
    out.extend(_comment_lines(obj.state.comments))
    out.extend(_serialize_state(obj.state))
    out.extend(_comment_lines(obj.covariance.comments))
    out.extend(_serialize_covariance(obj.covariance))
    return out


def _serialize_object_meta(meta: CdmObjectMetadata) -> list[str]:
    out = _comment_lines(meta.comments)
    ordered: tuple[tuple[str, str | None], ...] = (
        ("OBJECT", meta.object_value),
        ("OBJECT_DESIGNATOR", meta.object_designator),
        ("CATALOG_NAME", meta.catalog_name),
        ("OBJECT_NAME", meta.object_name),
        ("INTERNATIONAL_DESIGNATOR", meta.international_designator),
        ("OBJECT_TYPE", meta.object_type),
        ("OPERATOR_CONTACT_POSITION", meta.operator_contact_position),
        ("OPERATOR_ORGANIZATION", meta.operator_organization),
        ("OPERATOR_PHONE", meta.operator_phone),
        ("OPERATOR_EMAIL", meta.operator_email),
        ("EPHEMERIS_NAME", meta.ephemeris_name),
        ("COVARIANCE_METHOD", meta.covariance_method),
        ("MANEUVERABLE", meta.maneuverable),
        ("ORBIT_CENTER", meta.orbit_center),
        ("REF_FRAME", meta.ref_frame),
        ("GRAVITY_MODEL", meta.gravity_model),
        ("ATMOSPHERIC_MODEL", meta.atmospheric_model),
        ("N_BODY_PERTURBATIONS", meta.n_body_perturbations),
        ("SOLAR_RAD_PRESSURE", meta.solar_rad_pressure),
        ("EARTH_TIDES", meta.earth_tides),
        ("INTRACK_THRUST", meta.intrack_thrust),
    )
    out.extend(f"{key} = {value}" for key, value in ordered if value is not None)
    return out


def _serialize_od(od: CdmOdParameters) -> list[str]:
    out = _comment_lines(od.comments)
    if od.time_lastob_start is not None:
        out.append(f"TIME_LASTOB_START = {od.time_lastob_start}")
    if od.time_lastob_end is not None:
        out.append(f"TIME_LASTOB_END = {od.time_lastob_end}")
    if od.recommended_od_span is not None:
        out.append(_dim("RECOMMENDED_OD_SPAN", od.recommended_od_span, "d"))
    if od.actual_od_span is not None:
        out.append(_dim("ACTUAL_OD_SPAN", od.actual_od_span, "d"))
    for key, value in (
        ("OBS_AVAILABLE", od.obs_available),
        ("OBS_USED", od.obs_used),
        ("TRACKS_AVAILABLE", od.tracks_available),
        ("TRACKS_USED", od.tracks_used),
    ):
        if value is not None:
            out.append(f"{key} = {value}")
    if od.residuals_accepted is not None:
        out.append(_dim("RESIDUALS_ACCEPTED", od.residuals_accepted, "%"))
    if od.weighted_rms is not None:
        out.append(f"WEIGHTED_RMS = {_format_float(od.weighted_rms)}")
    return out


def _serialize_add(add: CdmAdditionalParameters) -> list[str]:
    out = _comment_lines(add.comments)
    dimensioned: tuple[tuple[str, float | None, str], ...] = (
        ("AREA_PC", add.area_pc, "m**2"),
        ("AREA_DRG", add.area_drg, "m**2"),
        ("AREA_SRP", add.area_srp, "m**2"),
        ("MASS", add.mass, "kg"),
        ("CD_AREA_OVER_MASS", add.cd_area_over_mass, "m**2/kg"),
        ("CR_AREA_OVER_MASS", add.cr_area_over_mass, "m**2/kg"),
        ("THRUST_ACCELERATION", add.thrust_acceleration, "m/s**2"),
        ("SEDR", add.sedr, "W/kg"),
    )
    out.extend(_dim(key, value, unit) for key, value, unit in dimensioned if value is not None)
    return out


def _serialize_state(state: CdmStateVector) -> list[str]:
    return [
        _dim("X", state.x, "km"),
        _dim("Y", state.y, "km"),
        _dim("Z", state.z, "km"),
        _dim("X_DOT", state.x_dot, "km/s"),
        _dim("Y_DOT", state.y_dot, "km/s"),
        _dim("Z_DOT", state.z_dot, "km/s"),
    ]


def _serialize_covariance(covariance: CdmCovariance) -> list[str]:
    out = [
        _dim(key, value, unit)
        for (key, unit), value in zip(_COV_MANDATORY, covariance.matrix, strict=True)
    ]
    out.extend(_dim(key, value, COV_UNITS[key]) for key, value in covariance.extended)
    return out


def _dim(keyword: str, value: float, unit: str) -> str:
    """A dimensioned KVN line: ``KEYWORD = <value> [unit]``."""
    return f"{keyword} = {_format_float(value)} [{unit}]"


register_writer("ccsds-cdm", write_cdm)
