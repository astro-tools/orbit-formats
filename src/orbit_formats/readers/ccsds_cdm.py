"""CCSDS CDM reader — in-house parsing of the Conjunction Data Message into a fidelity model.

The KVN reader is hand-written; the XML form is parsed through orbit-formats' own MIT xsdata
bindings (see :mod:`orbit_formats.adapters.cdm_xml`). No GPL dependency is ever imported at
runtime. Both notations parse into the *same* faithful :class:`CdmFile` fidelity model — the
header, the relative metadata/data, and the two object segments (each with its metadata, its
optional OD / additional parameters, its Cartesian state at TCA, and its RTN covariance) —
which is adapted into a canonical :class:`~orbit_formats.canonical.conjunction.Conjunction`.

A CDM is structurally unlike the other NDM members this library reads: it has **no
``META_START`` / ``META_STOP`` markers** (KVN sections are delimited by keyword identity and
the two ``OBJECT = OBJECT1`` / ``OBJECT = OBJECT2`` markers), it carries **two mandatory
segments** (the two objects) plus a shared relative-metadata/data block, and its dimensioned
KVN values carry a bracketed unit suffix (``MISS_DISTANCE = 715.0 [m]``). There is a single
message version (1.0) for both notations, and the CDM has no ``TIME_SYSTEM`` keyword — its
epochs are UTC by convention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import ClassVar, Literal

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.conjunction import Conjunction, ConjunctionObject
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import (
    _KEYWORD_RE,
    _comment_text,
    _is_comment,
    _parse_epoch,
)
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = [
    "CdmAdditionalParameters",
    "CdmCovariance",
    "CdmFile",
    "CdmObject",
    "CdmObjectMetadata",
    "CdmOdParameters",
    "CdmRelativeMetadata",
    "CdmStateVector",
    "read_cdm",
]

# The CDM is UTC by convention — it has no TIME_SYSTEM keyword.
_CDM_TIME_SCALE = "UTC"

# The header keyword set (everything before the relative-metadata block).
_HEADER_KEYS = frozenset(
    {"CCSDS_CDM_VERS", "CREATION_DATE", "ORIGINATOR", "MESSAGE_FOR", "MESSAGE_ID"}
)

# The relative metadata/data block, shared by the two objects.
_RELATIVE_KEYS = frozenset(
    {
        "TCA",
        "MISS_DISTANCE",
        "RELATIVE_SPEED",
        "RELATIVE_POSITION_R",
        "RELATIVE_POSITION_T",
        "RELATIVE_POSITION_N",
        "RELATIVE_VELOCITY_R",
        "RELATIVE_VELOCITY_T",
        "RELATIVE_VELOCITY_N",
        "START_SCREEN_PERIOD",
        "STOP_SCREEN_PERIOD",
        "SCREEN_VOLUME_FRAME",
        "SCREEN_VOLUME_SHAPE",
        "SCREEN_VOLUME_X",
        "SCREEN_VOLUME_Y",
        "SCREEN_VOLUME_Z",
        "SCREEN_ENTRY_TIME",
        "SCREEN_EXIT_TIME",
        "COLLISION_PROBABILITY",
        "COLLISION_PROBABILITY_METHOD",
    }
)

# Per-object metadata. ``OBJECT`` starts a new object section and is handled out of band.
_META_KEYS = frozenset(
    {
        "OBJECT",
        "OBJECT_DESIGNATOR",
        "CATALOG_NAME",
        "OBJECT_NAME",
        "INTERNATIONAL_DESIGNATOR",
        "OBJECT_TYPE",
        "OPERATOR_CONTACT_POSITION",
        "OPERATOR_ORGANIZATION",
        "OPERATOR_PHONE",
        "OPERATOR_EMAIL",
        "EPHEMERIS_NAME",
        "COVARIANCE_METHOD",
        "MANEUVERABLE",
        "ORBIT_CENTER",
        "REF_FRAME",
        "GRAVITY_MODEL",
        "ATMOSPHERIC_MODEL",
        "N_BODY_PERTURBATIONS",
        "SOLAR_RAD_PRESSURE",
        "EARTH_TIDES",
        "INTRACK_THRUST",
    }
)

_OD_KEYS = frozenset(
    {
        "TIME_LASTOB_START",
        "TIME_LASTOB_END",
        "RECOMMENDED_OD_SPAN",
        "ACTUAL_OD_SPAN",
        "OBS_AVAILABLE",
        "OBS_USED",
        "TRACKS_AVAILABLE",
        "TRACKS_USED",
        "RESIDUALS_ACCEPTED",
        "WEIGHTED_RMS",
    }
)

_ADD_KEYS = frozenset(
    {
        "AREA_PC",
        "AREA_DRG",
        "AREA_SRP",
        "MASS",
        "CD_AREA_OVER_MASS",
        "CR_AREA_OVER_MASS",
        "THRUST_ACCELERATION",
        "SEDR",
    }
)

_STATE_KEYS = ("X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT")

# The 21 mandatory lower-triangular elements of the symmetric 6x6 position/velocity covariance,
# in the RTN axis order (R, T, N, Ṙ, Ṫ, Ṅ), each paired with its CCSDS unit.
_COV_MANDATORY: tuple[tuple[str, str], ...] = (
    ("CR_R", "m**2"),
    ("CT_R", "m**2"),
    ("CT_T", "m**2"),
    ("CN_R", "m**2"),
    ("CN_T", "m**2"),
    ("CN_N", "m**2"),
    ("CRDOT_R", "m**2/s"),
    ("CRDOT_T", "m**2/s"),
    ("CRDOT_N", "m**2/s"),
    ("CRDOT_RDOT", "m**2/s**2"),
    ("CTDOT_R", "m**2/s"),
    ("CTDOT_T", "m**2/s"),
    ("CTDOT_N", "m**2/s"),
    ("CTDOT_RDOT", "m**2/s**2"),
    ("CTDOT_TDOT", "m**2/s**2"),
    ("CNDOT_R", "m**2/s"),
    ("CNDOT_T", "m**2/s"),
    ("CNDOT_N", "m**2/s"),
    ("CNDOT_RDOT", "m**2/s**2"),
    ("CNDOT_TDOT", "m**2/s**2"),
    ("CNDOT_NDOT", "m**2/s**2"),
)

# The optional extended covariance cross-terms (drag, SRP, thrust), in schema order.
_COV_EXTENDED: tuple[tuple[str, str], ...] = (
    ("CDRG_R", "m**3/kg"),
    ("CDRG_T", "m**3/kg"),
    ("CDRG_N", "m**3/kg"),
    ("CDRG_RDOT", "m**3/(kg*s)"),
    ("CDRG_TDOT", "m**3/(kg*s)"),
    ("CDRG_NDOT", "m**3/(kg*s)"),
    ("CDRG_DRG", "m**4/kg**2"),
    ("CSRP_R", "m**3/kg"),
    ("CSRP_T", "m**3/kg"),
    ("CSRP_N", "m**3/kg"),
    ("CSRP_RDOT", "m**3/(kg*s)"),
    ("CSRP_TDOT", "m**3/(kg*s)"),
    ("CSRP_NDOT", "m**3/(kg*s)"),
    ("CSRP_DRG", "m**4/kg**2"),
    ("CSRP_SRP", "m**4/kg**2"),
    ("CTHR_R", "m**2/s**2"),
    ("CTHR_T", "m**2/s**2"),
    ("CTHR_N", "m**2/s**2"),
    ("CTHR_RDOT", "m**2/s**3"),
    ("CTHR_TDOT", "m**2/s**3"),
    ("CTHR_NDOT", "m**2/s**3"),
    ("CTHR_DRG", "m**3/(kg*s**2)"),
    ("CTHR_SRP", "m**3/(kg*s**2)"),
    ("CTHR_THR", "m**2/s**4"),
)

_COV_MANDATORY_KEYS = tuple(key for key, _ in _COV_MANDATORY)
_COV_EXTENDED_KEYS = tuple(key for key, _ in _COV_EXTENDED)
#: Every covariance keyword mapped to its CCSDS unit — shared by the KVN writer and XML adapter.
COV_UNITS: dict[str, str] = dict(_COV_MANDATORY + _COV_EXTENDED)
_COV_KEYS = frozenset(COV_UNITS)

# A trailing bracketed unit on a KVN value, e.g. the ``[m]`` in ``MISS_DISTANCE = 715.0 [m]``.
_UNIT_SUFFIX_RE = re.compile(r"\s*\[[^\]]*\]\s*$")


# --- fidelity model --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CdmRelativeMetadata:
    """The CDM relative metadata/data block — the conjunction geometry shared by both objects.

    ``tca`` is the time of closest approach and ``miss_distance`` the separation at TCA (m).
    ``relative_position`` / ``relative_velocity`` are the ``(R, T, N)`` relative state (m, m/s)
    when the optional relative-state block is present. The screen-period / screen-volume and
    collision-probability fields are present only when the CDM states them.
    """

    tca: np.datetime64
    miss_distance: float
    relative_speed: float | None = None
    relative_position: tuple[float, float, float] | None = None
    relative_velocity: tuple[float, float, float] | None = None
    start_screen_period: str | None = None
    stop_screen_period: str | None = None
    screen_volume_frame: str | None = None
    screen_volume_shape: str | None = None
    screen_volume_x: float | None = None
    screen_volume_y: float | None = None
    screen_volume_z: float | None = None
    screen_entry_time: str | None = None
    screen_exit_time: str | None = None
    collision_probability: float | None = None
    collision_probability_method: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CdmObjectMetadata:
    """One object's CDM metadata block — its identity, frame, and modelling flags.

    The nine mandatory keywords (``object_value`` through ``ref_frame``) are non-optional; the
    operator-contact, perturbation-model, and flag fields are present only when stated.
    ``object_value`` is the slot marker (``"OBJECT1"`` / ``"OBJECT2"``).
    """

    object_value: str
    object_designator: str
    catalog_name: str
    object_name: str
    international_designator: str
    ephemeris_name: str
    covariance_method: str
    maneuverable: str
    ref_frame: str
    object_type: str | None = None
    operator_contact_position: str | None = None
    operator_organization: str | None = None
    operator_phone: str | None = None
    operator_email: str | None = None
    orbit_center: str | None = None
    gravity_model: str | None = None
    atmospheric_model: str | None = None
    n_body_perturbations: str | None = None
    solar_rad_pressure: str | None = None
    earth_tides: str | None = None
    intrack_thrust: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CdmStateVector:
    """One object's Cartesian state at TCA — position (km) and velocity (km/s) in ``ref_frame``."""

    x: float
    y: float
    z: float
    x_dot: float
    y_dot: float
    z_dot: float
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CdmCovariance:
    """One object's covariance: the 21 mandatory RTN elements plus optional extended terms.

    ``matrix`` is the 21 lower-triangular elements of the symmetric 6x6 position/velocity
    covariance in RTN order; ``extended`` keeps any optional drag / SRP / thrust cross-terms
    as ``(keyword, value)`` pairs in schema order, so a CDM that carries them round-trips
    losslessly without the canonical record having to model them.
    """

    matrix: tuple[float, ...]
    extended: tuple[tuple[str, float], ...] = ()
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CdmOdParameters:
    """One object's optional orbit-determination parameters block."""

    time_lastob_start: str | None = None
    time_lastob_end: str | None = None
    recommended_od_span: float | None = None
    actual_od_span: float | None = None
    obs_available: int | None = None
    obs_used: int | None = None
    tracks_available: int | None = None
    tracks_used: int | None = None
    residuals_accepted: float | None = None
    weighted_rms: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CdmAdditionalParameters:
    """One object's optional additional-parameters block — areas, mass, ballistic ratios."""

    area_pc: float | None = None
    area_drg: float | None = None
    area_srp: float | None = None
    mass: float | None = None
    cd_area_over_mass: float | None = None
    cr_area_over_mass: float | None = None
    thrust_acceleration: float | None = None
    sedr: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CdmObject:
    """One CDM object segment: its metadata, state, covariance, and optional parameter blocks."""

    metadata: CdmObjectMetadata
    state: CdmStateVector
    covariance: CdmCovariance
    od_parameters: CdmOdParameters | None = None
    additional_parameters: CdmAdditionalParameters | None = None
    data_comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class CdmFile(FidelityModel):
    """The faithful CDM fidelity model: the header, the relative block, and the two objects.

    Holds every field a same-format CDM write reconstructs from, so a CDM → CDM round-trip
    stays content-lossless without polluting the canonical schema. ``raw_bytes`` is the
    verbatim source kept only when the read opted in via ``retain_source=True``;
    ``serialization`` records the notation the file was read from (``"kvn"`` or ``"xml"``) so a
    write re-emits in the same notation by default.
    """

    format_name: ClassVar[str] = "ccsds-cdm"

    ccsds_version: str
    relative: CdmRelativeMetadata
    objects: tuple[CdmObject, CdmObject]
    creation_date: str | None = None
    originator: str | None = None
    message_for: str | None = None
    message_id: str | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_cdm(source: Source) -> Conjunction:
    """Read a CCSDS CDM (KVN or XML) into a canonical :class:`Conjunction`.

    Parses the header, the relative metadata/data, and the two object segments into a
    :class:`CdmFile` fidelity model, retained as ``source_native``, then adapts it into a
    canonical conjunction tagged with the primary object, the originator, and the UTC time
    scale. An XML document (whose first token is a tag) routes to the xsdata bindings
    (:mod:`orbit_formats.adapters.cdm_xml`); everything else to the hand-written KVN scanner.
    Raises :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword,
    a malformed value or epoch, malformed XML, a partial relative-state or covariance block, or
    a CDM that does not carry exactly two objects.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.cdm_xml import cdmfile_from_xml

        cdm = cdmfile_from_xml(source.read_bytes())
    else:
        cdm = _CdmKvnParser(text.splitlines()).parse()
    if source.retain:
        cdm = replace(cdm, raw_bytes=source.read_bytes())
    return _to_conjunction(cdm)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is a CDM in XML rather than KVN — its first content is an XML tag."""
    return text.lstrip("﻿ \t\r\n").startswith("<")


# --- KVN parsing -----------------------------------------------------------------------


@dataclass
class _RawObject:
    """Per-object KVN accumulators, one sub-block per CDM data section."""

    meta: dict[str, str] = field(default_factory=dict)
    meta_comments: list[str] = field(default_factory=list)
    od: dict[str, str] = field(default_factory=dict)
    od_comments: list[str] = field(default_factory=list)
    add: dict[str, str] = field(default_factory=dict)
    add_comments: list[str] = field(default_factory=list)
    state: dict[str, str] = field(default_factory=dict)
    state_comments: list[str] = field(default_factory=list)
    cov: dict[str, str] = field(default_factory=dict)
    cov_comments: list[str] = field(default_factory=list)
    data_comments: list[str] = field(default_factory=list)


class _CdmKvnParser:
    """A scanner over a CDM's KVN lines: a header, a relative block, then two object blocks.

    The CDM has no block markers, so the current section is decided by keyword identity: each
    keyword is routed to its block by membership, and an ``OBJECT`` keyword opens a new object.
    A ``COMMENT`` line attaches to the block of the next keyword it precedes.
    """

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._i = 0

    def parse(self) -> CdmFile:
        header: dict[str, str] = {}
        header_comments: list[str] = []
        relative: dict[str, str] = {}
        relative_comments: list[str] = []
        objects: list[_RawObject] = []
        pending: list[str] = []
        current: _RawObject | None = None
        phase = "header"

        while True:
            line = self._next()
            if line is None:
                break
            stripped = line.strip()
            if _is_comment(stripped):
                pending.append(_comment_text(stripped))
                continue
            key, value = self._require_keyword(stripped)
            if key == "OBJECT":
                current = _RawObject()
                objects.append(current)
                current.meta["OBJECT"] = value
                current.meta_comments.extend(pending)
                pending = []
                phase = "object"
                continue
            if phase == "header" and key in _HEADER_KEYS:
                header[key] = value
                header_comments.extend(pending)
            elif key in _RELATIVE_KEYS:
                phase = "relative"
                relative[key] = value
                relative_comments.extend(pending)
            elif current is not None and key in _META_KEYS:
                current.meta[key] = value
                current.meta_comments.extend(pending)
            elif current is not None and key in _OD_KEYS:
                current.od[key] = value
                current.od_comments.extend(pending)
            elif current is not None and key in _ADD_KEYS:
                current.add[key] = value
                current.add_comments.extend(pending)
            elif current is not None and key in _STATE_KEYS:
                current.state[key] = value
                current.state_comments.extend(pending)
            elif current is not None and key in _COV_KEYS:
                current.cov[key] = value
                current.cov_comments.extend(pending)
            else:
                raise MalformedSourceError(f"unexpected keyword {key!r} in the CDM")
            pending = []

        if "CCSDS_CDM_VERS" not in header:
            raise MalformedSourceError(
                "not a CCSDS CDM: the 'CCSDS_CDM_VERS' header keyword is missing"
            )
        if len(objects) != 2:
            raise MalformedSourceError(f"a CDM must carry exactly two objects, got {len(objects)}")
        return CdmFile(
            ccsds_version=header["CCSDS_CDM_VERS"],
            relative=_build_relative(relative, relative_comments),
            objects=(_build_object(objects[0]), _build_object(objects[1])),
            creation_date=header.get("CREATION_DATE"),
            originator=header.get("ORIGINATOR"),
            message_for=header.get("MESSAGE_FOR"),
            message_id=header.get("MESSAGE_ID"),
            comments=tuple(header_comments),
        )

    def _require_keyword(self, line: str) -> tuple[str, str]:
        match = _KEYWORD_RE.match(line)
        if match is None:
            raise MalformedSourceError(f"expected 'KEYWORD = value' in the CDM, got {line!r}")
        return match.group(1).upper(), match.group(2).strip()

    def _next(self) -> str | None:
        while self._i < len(self._lines) and not self._lines[self._i].strip():
            self._i += 1
        if self._i >= len(self._lines):
            return None
        line = self._lines[self._i]
        self._i += 1
        return line


def _build_relative(values: dict[str, str], comments: list[str]) -> CdmRelativeMetadata:
    return CdmRelativeMetadata(
        tca=_parse_epoch(_require(values, "TCA", "relative metadata")),
        miss_distance=_dim_float(
            _require(values, "MISS_DISTANCE", "relative metadata"), "MISS_DISTANCE"
        ),
        relative_speed=_opt_dim_float(values, "RELATIVE_SPEED"),
        relative_position=_relative_triplet(values, "RELATIVE_POSITION"),
        relative_velocity=_relative_triplet(values, "RELATIVE_VELOCITY"),
        start_screen_period=values.get("START_SCREEN_PERIOD"),
        stop_screen_period=values.get("STOP_SCREEN_PERIOD"),
        screen_volume_frame=values.get("SCREEN_VOLUME_FRAME"),
        screen_volume_shape=values.get("SCREEN_VOLUME_SHAPE"),
        screen_volume_x=_opt_dim_float(values, "SCREEN_VOLUME_X"),
        screen_volume_y=_opt_dim_float(values, "SCREEN_VOLUME_Y"),
        screen_volume_z=_opt_dim_float(values, "SCREEN_VOLUME_Z"),
        screen_entry_time=values.get("SCREEN_ENTRY_TIME"),
        screen_exit_time=values.get("SCREEN_EXIT_TIME"),
        collision_probability=_opt_dim_float(values, "COLLISION_PROBABILITY"),
        collision_probability_method=values.get("COLLISION_PROBABILITY_METHOD"),
        comments=tuple(comments),
    )


def _relative_triplet(values: dict[str, str], prefix: str) -> tuple[float, float, float] | None:
    keys = (f"{prefix}_R", f"{prefix}_T", f"{prefix}_N")
    present = [key for key in keys if key in values]
    if not present:
        return None
    if len(present) != len(keys):
        missing = [key for key in keys if key not in values]
        raise MalformedSourceError(f"CDM {prefix} is incomplete; missing {', '.join(missing)}")
    r, t, n = (_dim_float(values[key], key) for key in keys)
    return (r, t, n)


def _build_object(raw: _RawObject) -> CdmObject:
    return CdmObject(
        metadata=_build_object_meta(raw.meta, raw.meta_comments),
        state=_build_state(raw.state, raw.state_comments),
        covariance=_build_covariance(raw.cov, raw.cov_comments),
        od_parameters=_build_od(raw.od, raw.od_comments) if (raw.od or raw.od_comments) else None,
        additional_parameters=(
            _build_add(raw.add, raw.add_comments) if (raw.add or raw.add_comments) else None
        ),
        data_comments=tuple(raw.data_comments),
    )


def _build_object_meta(values: dict[str, str], comments: list[str]) -> CdmObjectMetadata:
    return CdmObjectMetadata(
        object_value=_require(values, "OBJECT", "object metadata"),
        object_designator=_require(values, "OBJECT_DESIGNATOR", "object metadata"),
        catalog_name=_require(values, "CATALOG_NAME", "object metadata"),
        object_name=_require(values, "OBJECT_NAME", "object metadata"),
        international_designator=_require(values, "INTERNATIONAL_DESIGNATOR", "object metadata"),
        ephemeris_name=_require(values, "EPHEMERIS_NAME", "object metadata"),
        covariance_method=_require(values, "COVARIANCE_METHOD", "object metadata"),
        maneuverable=_require(values, "MANEUVERABLE", "object metadata"),
        ref_frame=_require(values, "REF_FRAME", "object metadata"),
        object_type=values.get("OBJECT_TYPE"),
        operator_contact_position=values.get("OPERATOR_CONTACT_POSITION"),
        operator_organization=values.get("OPERATOR_ORGANIZATION"),
        operator_phone=values.get("OPERATOR_PHONE"),
        operator_email=values.get("OPERATOR_EMAIL"),
        orbit_center=values.get("ORBIT_CENTER"),
        gravity_model=values.get("GRAVITY_MODEL"),
        atmospheric_model=values.get("ATMOSPHERIC_MODEL"),
        n_body_perturbations=values.get("N_BODY_PERTURBATIONS"),
        solar_rad_pressure=values.get("SOLAR_RAD_PRESSURE"),
        earth_tides=values.get("EARTH_TIDES"),
        intrack_thrust=values.get("INTRACK_THRUST"),
        comments=tuple(comments),
    )


def _build_state(values: dict[str, str], comments: list[str]) -> CdmStateVector:
    x, y, z, x_dot, y_dot, z_dot = (
        _dim_float(_require(values, key, "state vector"), key) for key in _STATE_KEYS
    )
    return CdmStateVector(
        x=x, y=y, z=z, x_dot=x_dot, y_dot=y_dot, z_dot=z_dot, comments=tuple(comments)
    )


def _build_covariance(values: dict[str, str], comments: list[str]) -> CdmCovariance:
    missing = [key for key in _COV_MANDATORY_KEYS if key not in values]
    if missing:
        raise MalformedSourceError(
            f"CDM covariance is missing required element(s): {', '.join(missing)}"
        )
    matrix = tuple(_dim_float(values[key], key) for key in _COV_MANDATORY_KEYS)
    extended = tuple(
        (key, _dim_float(values[key], key)) for key in _COV_EXTENDED_KEYS if key in values
    )
    return CdmCovariance(matrix=matrix, extended=extended, comments=tuple(comments))


def _build_od(values: dict[str, str], comments: list[str]) -> CdmOdParameters:
    return CdmOdParameters(
        time_lastob_start=values.get("TIME_LASTOB_START"),
        time_lastob_end=values.get("TIME_LASTOB_END"),
        recommended_od_span=_opt_dim_float(values, "RECOMMENDED_OD_SPAN"),
        actual_od_span=_opt_dim_float(values, "ACTUAL_OD_SPAN"),
        obs_available=_opt_int(values, "OBS_AVAILABLE"),
        obs_used=_opt_int(values, "OBS_USED"),
        tracks_available=_opt_int(values, "TRACKS_AVAILABLE"),
        tracks_used=_opt_int(values, "TRACKS_USED"),
        residuals_accepted=_opt_dim_float(values, "RESIDUALS_ACCEPTED"),
        weighted_rms=_opt_dim_float(values, "WEIGHTED_RMS"),
        comments=tuple(comments),
    )


def _build_add(values: dict[str, str], comments: list[str]) -> CdmAdditionalParameters:
    return CdmAdditionalParameters(
        area_pc=_opt_dim_float(values, "AREA_PC"),
        area_drg=_opt_dim_float(values, "AREA_DRG"),
        area_srp=_opt_dim_float(values, "AREA_SRP"),
        mass=_opt_dim_float(values, "MASS"),
        cd_area_over_mass=_opt_dim_float(values, "CD_AREA_OVER_MASS"),
        cr_area_over_mass=_opt_dim_float(values, "CR_AREA_OVER_MASS"),
        thrust_acceleration=_opt_dim_float(values, "THRUST_ACCELERATION"),
        sedr=_opt_dim_float(values, "SEDR"),
        comments=tuple(comments),
    )


def _strip_units(value: str) -> str:
    """Drop a trailing bracketed unit (``715.0 [m]`` -> ``715.0``)."""
    return _UNIT_SUFFIX_RE.sub("", value).strip()


def _dim_float(value: str, keyword: str) -> float:
    try:
        return float(_strip_units(value))
    except ValueError as exc:
        raise MalformedSourceError(f"CDM {keyword} must be a number, got {value!r}") from exc


def _opt_dim_float(values: dict[str, str], key: str) -> float | None:
    raw = values.get(key)
    return None if raw is None else _dim_float(raw, key)


def _opt_int(values: dict[str, str], key: str) -> int | None:
    raw = values.get(key)
    if raw is None:
        return None
    try:
        return int(_strip_units(raw))
    except ValueError as exc:
        raise MalformedSourceError(f"CDM {key} must be an integer, got {raw!r}") from exc


def _require(values: dict[str, str], key: str, where: str) -> str:
    if key not in values:
        raise MalformedSourceError(f"CDM {where} is missing the required keyword {key!r}")
    return values[key]


# --- adaptation to the canonical Conjunction -------------------------------------------


def _to_conjunction(cdm: CdmFile) -> Conjunction:
    """Adapt a :class:`CdmFile` into the canonical :class:`Conjunction`.

    The primary object (``OBJECT1``) and the originator tag the metadata spine; the time scale
    is UTC (the CDM convention). The relative state and each object's Cartesian state and 6x6
    RTN covariance become the canonical payload, while the screen-volume block, OD / additional
    parameters, and any extended covariance terms ride on ``source_native``.
    """
    relative = cdm.relative
    primary = cdm.objects[0].metadata
    metadata = Metadata(
        object_name=primary.object_name,
        object_id=primary.object_designator,
        originator=cdm.originator,
        time_scale=_CDM_TIME_SCALE,
        provenance=Provenance(source_format="ccsds-cdm", creation_date=cdm.creation_date),
    )
    return Conjunction(
        metadata=metadata,
        source_native=cdm,
        tca=relative.tca,
        miss_distance=relative.miss_distance,
        relative_speed=relative.relative_speed,
        relative_position=_triplet_array(relative.relative_position),
        relative_velocity=_triplet_array(relative.relative_velocity),
        objects=(_to_object(cdm.objects[0]), _to_object(cdm.objects[1])),
    )


def _to_object(obj: CdmObject) -> ConjunctionObject:
    meta = obj.metadata
    state = obj.state
    return ConjunctionObject(
        label=meta.object_value,
        object_designator=meta.object_designator,
        ref_frame=meta.ref_frame,
        state=np.array(
            [state.x, state.y, state.z, state.x_dot, state.y_dot, state.z_dot], dtype=np.float64
        ),
        covariance=_symmetric_from_lower(obj.covariance.matrix),
        object_name=meta.object_name,
        catalog_name=meta.catalog_name,
        international_designator=meta.international_designator,
    )


def _triplet_array(value: tuple[float, float, float] | None) -> NDArray[np.float64] | None:
    """Project an optional ``(R, T, N)`` tuple to a float array (or ``None``)."""
    return None if value is None else np.array(value, dtype=np.float64)


def _symmetric_from_lower(values: tuple[float, ...]) -> NDArray[np.float64]:
    """Rebuild the symmetric 6x6 covariance from its 21 lower-triangular elements (row order)."""
    matrix = np.zeros((6, 6), dtype=np.float64)
    index = 0
    for row in range(6):
        for col in range(row + 1):
            matrix[row, col] = matrix[col, row] = values[index]
            index += 1
    return matrix


register_reader("ccsds-cdm", read_cdm)
