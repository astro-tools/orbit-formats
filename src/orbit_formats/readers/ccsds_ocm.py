"""CCSDS OCM reader — in-house parsing of the Orbit Comprehensive Message into a fidelity model.

The OCM is the largest and most general NDM member: a single segment whose data section
carries any of seven optional blocks — one or more trajectory state histories (``traj``), a
physical-properties block (``phys``), one or more covariance histories (``cov``) and
maneuver specifications (``man``), a perturbations block (``pert``), an orbit-determination
block (``od``), and a user-defined block (``user``). The KVN reader is hand-written; the XML
form is parsed through orbit-formats' own MIT xsdata bindings (see
:mod:`orbit_formats.adapters.ocm_xml`). No GPL dependency is ever imported at runtime.

Both notations parse into the *same* faithful :class:`OcmFile` fidelity model, which is then
adapted into a canonical :class:`~orbit_formats.canonical.ephemeris.Ephemeris` built from the
Cartesian trajectory blocks, with the whole :class:`OcmFile` retained as ``source_native`` so
a same-format write stays byte-lossless and the blocks the canonical ephemeris cannot
represent (covariance, maneuvers, physical, perturbations, OD, user-defined, and non-Cartesian
trajectory state) survive there, dropped-with-warning only on a cross-format write.

Every OCM block is, structurally, a set of ``KEYWORD = value`` lines (a closed vocabulary per
block) plus — for ``traj`` / ``cov`` / ``man`` — a run of free-form data lines (``trajLine`` /
``covLine`` / ``manLine`` in the schema) that the reader carries verbatim. The keyword
vocabularies are modelled by declarative tables (:data:`_METADATA_FIELDS` and friends), each
keyword paired with the scalar kind its value parses to; the same tables drive the KVN parser,
the KVN writer, and the XML adapter from one source of truth, so the two notations stay
symmetric by construction. OCM is version 3.0 in both notations, so there is no version skew.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import ClassVar, Literal

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.maneuver import Maneuver
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import (
    _KEYWORD_RE,
    _canonical_time_scale,
    _comment_text,
    _datetime_array,
    _float_matrix,
    _is_comment,
    _parse_epoch,
)
from orbit_formats.registry import register_reader
from orbit_formats.source import Source
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy

__all__ = [
    "FieldValue",
    "OcmCovarianceBlock",
    "OcmFile",
    "OcmKeywordBlock",
    "OcmManeuverBlock",
    "OcmTrajectoryBlock",
    "OcmUserDefined",
    "Quantity",
    "read_ocm",
]


# --- the typed value model -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Quantity:
    """A dimensioned scalar: a numeric ``value`` and an optional ``units`` token.

    KVN writes a dimensioned value as ``<value> [unit]`` (the unit optional, the SI default
    implied when absent); NDM/XML writes the same value with a ``units`` XML attribute. Both
    notations parse to this one type, so the unit travels with the value and a KVN ↔ XML
    comparison holds. ``units`` is the unit token verbatim (e.g. ``"kg"``, ``"m**2"``), or
    ``None`` when the source named none.
    """

    value: float
    units: str | None = None


#: A parsed OCM keyword value: a string (covering plain strings and enum tokens), an integer,
#: a float, a dimensioned :class:`Quantity`, or a fixed-length numeric vector (``DC_REF_DIR``).
FieldValue = str | int | float | Quantity | tuple[float, ...]

# The scalar kind each keyword parses to. ``"str"`` covers plain strings and enum tokens
# (stored verbatim; the XML adapter rebuilds the enum). ``"quantity"`` is a value + optional
# unit, ``"vec3"`` a whitespace-separated numeric vector. The tables below are in schema
# (canonical write) order, the order both readers build each block in, so a KVN-read and an
# XML-read block compare equal. Generated from the vendored OCM XSD bindings; see
# :mod:`orbit_formats.adapters.ocm_xml`, which derives the same shape by introspecting them.
FieldKind = Literal["str", "int", "float", "quantity", "vec3", "enum"]
_FieldTable = tuple[tuple[str, FieldKind], ...]


# --- declarative keyword vocabularies (CCSDS 502.0-B-3 / ndmxml-4.0.0-ocm-3.0) ----------

_METADATA_FIELDS: _FieldTable = (
    ("OBJECT_NAME", "str"),
    ("INTERNATIONAL_DESIGNATOR", "str"),
    ("CATALOG_NAME", "str"),
    ("OBJECT_DESIGNATOR", "str"),
    ("ALTERNATE_NAMES", "str"),
    ("ORIGINATOR_POC", "str"),
    ("ORIGINATOR_POSITION", "str"),
    ("ORIGINATOR_PHONE", "str"),
    ("ORIGINATOR_EMAIL", "str"),
    ("ORIGINATOR_ADDRESS", "str"),
    ("TECH_ORG", "str"),
    ("TECH_POC", "str"),
    ("TECH_POSITION", "str"),
    ("TECH_PHONE", "str"),
    ("TECH_EMAIL", "str"),
    ("TECH_ADDRESS", "str"),
    ("PREVIOUS_MESSAGE_ID", "str"),
    ("NEXT_MESSAGE_ID", "str"),
    ("ADM_MSG_LINK", "str"),
    ("CDM_MSG_LINK", "str"),
    ("PRM_MSG_LINK", "str"),
    ("RDM_MSG_LINK", "str"),
    ("TDM_MSG_LINK", "str"),
    ("OPERATOR", "str"),
    ("OWNER", "str"),
    ("COUNTRY", "str"),
    ("CONSTELLATION", "str"),
    ("OBJECT_TYPE", "enum"),
    ("TIME_SYSTEM", "str"),
    ("EPOCH_TZERO", "str"),
    ("OPS_STATUS", "str"),
    ("ORBIT_CATEGORY", "str"),
    ("OCM_DATA_ELEMENTS", "str"),
    ("SCLK_OFFSET_AT_EPOCH", "quantity"),
    ("SCLK_SEC_PER_SI_SEC", "quantity"),
    ("PREVIOUS_MESSAGE_EPOCH", "str"),
    ("NEXT_MESSAGE_EPOCH", "str"),
    ("START_TIME", "str"),
    ("STOP_TIME", "str"),
    ("TIME_SPAN", "quantity"),
    ("TAIMUTC_AT_TZERO", "quantity"),
    ("NEXT_LEAP_EPOCH", "str"),
    ("NEXT_LEAP_TAIMUTC", "quantity"),
    ("UT1MUTC_AT_TZERO", "quantity"),
    ("EOP_SOURCE", "str"),
    ("INTERP_METHOD_EOP", "str"),
    ("CELESTIAL_SOURCE", "str"),
)

_TRAJ_FIELDS: _FieldTable = (
    ("TRAJ_ID", "str"),
    ("TRAJ_PREV_ID", "str"),
    ("TRAJ_NEXT_ID", "str"),
    ("TRAJ_BASIS", "enum"),
    ("TRAJ_BASIS_ID", "str"),
    ("INTERPOLATION", "str"),
    ("INTERPOLATION_DEGREE", "int"),
    ("PROPAGATOR", "str"),
    ("CENTER_NAME", "str"),
    ("TRAJ_REF_FRAME", "str"),
    ("TRAJ_FRAME_EPOCH", "str"),
    ("USEABLE_START_TIME", "str"),
    ("USEABLE_STOP_TIME", "str"),
    ("ORB_REVNUM", "float"),
    ("ORB_REVNUM_BASIS", "enum"),
    ("TRAJ_TYPE", "str"),
    ("ORB_AVERAGING", "str"),
    ("TRAJ_UNITS", "str"),
)

_COV_FIELDS: _FieldTable = (
    ("COV_ID", "str"),
    ("COV_PREV_ID", "str"),
    ("COV_NEXT_ID", "str"),
    ("COV_BASIS", "enum"),
    ("COV_BASIS_ID", "str"),
    ("COV_REF_FRAME", "str"),
    ("COV_FRAME_EPOCH", "str"),
    ("COV_SCALE_MIN", "float"),
    ("COV_SCALE_MAX", "float"),
    ("COV_CONFIDENCE", "quantity"),
    ("COV_TYPE", "str"),
    ("COV_ORDERING", "enum"),
    ("COV_UNITS", "str"),
)

_MAN_FIELDS: _FieldTable = (
    ("MAN_ID", "str"),
    ("MAN_PREV_ID", "str"),
    ("MAN_NEXT_ID", "str"),
    ("MAN_BASIS", "enum"),
    ("MAN_BASIS_ID", "str"),
    ("MAN_DEVICE_ID", "str"),
    ("MAN_PREV_EPOCH", "str"),
    ("MAN_NEXT_EPOCH", "str"),
    ("MAN_PURPOSE", "str"),
    ("MAN_PRED_SOURCE", "str"),
    ("MAN_REF_FRAME", "str"),
    ("MAN_FRAME_EPOCH", "str"),
    ("GRAV_ASSIST_NAME", "str"),
    ("DC_TYPE", "enum"),
    ("DC_WIN_OPEN", "str"),
    ("DC_WIN_CLOSE", "str"),
    ("DC_MIN_CYCLES", "int"),
    ("DC_MAX_CYCLES", "int"),
    ("DC_EXEC_START", "str"),
    ("DC_EXEC_STOP", "str"),
    ("DC_REF_TIME", "str"),
    ("DC_TIME_PULSE_DURATION", "quantity"),
    ("DC_TIME_PULSE_PERIOD", "quantity"),
    ("DC_REF_DIR", "vec3"),
    ("DC_BODY_FRAME", "str"),
    ("DC_BODY_TRIGGER", "vec3"),
    ("DC_PA_START_ANGLE", "quantity"),
    ("DC_PA_STOP_ANGLE", "quantity"),
    ("MAN_COMPOSITION", "str"),
    ("MAN_UNITS", "str"),
)

_PHYS_FIELDS: _FieldTable = (
    ("MANUFACTURER", "str"),
    ("BUS_MODEL", "str"),
    ("DOCKED_WITH", "str"),
    ("DRAG_CONST_AREA", "quantity"),
    ("DRAG_COEFF_NOM", "float"),
    ("DRAG_UNCERTAINTY", "quantity"),
    ("INITIAL_WET_MASS", "quantity"),
    ("WET_MASS", "quantity"),
    ("DRY_MASS", "quantity"),
    ("OEB_PARENT_FRAME", "str"),
    ("OEB_PARENT_FRAME_EPOCH", "str"),
    ("OEB_Q1", "float"),
    ("OEB_Q2", "float"),
    ("OEB_Q3", "float"),
    ("OEB_QC", "float"),
    ("OEB_MAX", "quantity"),
    ("OEB_INT", "quantity"),
    ("OEB_MIN", "quantity"),
    ("AREA_ALONG_OEB_MAX", "quantity"),
    ("AREA_ALONG_OEB_INT", "quantity"),
    ("AREA_ALONG_OEB_MIN", "quantity"),
    ("AREA_MIN_FOR_PC", "quantity"),
    ("AREA_MAX_FOR_PC", "quantity"),
    ("AREA_TYP_FOR_PC", "quantity"),
    ("RCS", "quantity"),
    ("RCS_MIN", "quantity"),
    ("RCS_MAX", "quantity"),
    ("SRP_CONST_AREA", "quantity"),
    ("SOLAR_RAD_COEFF", "float"),
    ("SOLAR_RAD_UNCERTAINTY", "quantity"),
    ("VM_ABSOLUTE", "float"),
    ("VM_APPARENT_MIN", "float"),
    ("VM_APPARENT", "float"),
    ("VM_APPARENT_MAX", "float"),
    ("REFLECTANCE", "float"),
    ("ATT_CONTROL_MODE", "str"),
    ("ATT_ACTUATOR_TYPE", "str"),
    ("ATT_KNOWLEDGE", "quantity"),
    ("ATT_CONTROL", "quantity"),
    ("ATT_POINTING", "quantity"),
    ("AVG_MANEUVER_FREQ", "quantity"),
    ("MAX_THRUST", "quantity"),
    ("DV_BOL", "quantity"),
    ("DV_REMAINING", "quantity"),
    ("IXX", "quantity"),
    ("IYY", "quantity"),
    ("IZZ", "quantity"),
    ("IXY", "quantity"),
    ("IXZ", "quantity"),
    ("IYZ", "quantity"),
)

_PERT_FIELDS: _FieldTable = (
    ("ATMOSPHERIC_MODEL", "str"),
    ("GRAVITY_MODEL", "str"),
    ("EQUATORIAL_RADIUS", "quantity"),
    ("GM", "quantity"),
    ("N_BODY_PERTURBATIONS", "str"),
    ("CENTRAL_BODY_ROTATION", "quantity"),
    ("OBLATE_FLATTENING", "float"),
    ("OCEAN_TIDES_MODEL", "str"),
    ("SOLID_TIDES_MODEL", "str"),
    ("REDUCTION_THEORY", "str"),
    ("ALBEDO_MODEL", "str"),
    ("ALBEDO_GRID_SIZE", "int"),
    ("SHADOW_MODEL", "str"),
    ("SHADOW_BODIES", "str"),
    ("SRP_MODEL", "str"),
    ("SW_DATA_SOURCE", "str"),
    ("SW_DATA_EPOCH", "str"),
    ("SW_INTERP_METHOD", "str"),
    ("FIXED_GEOMAG_KP", "quantity"),
    ("FIXED_GEOMAG_AP", "quantity"),
    ("FIXED_GEOMAG_DST", "quantity"),
    ("FIXED_F10P7", "quantity"),
    ("FIXED_F10P7_MEAN", "quantity"),
    ("FIXED_M10P7", "quantity"),
    ("FIXED_M10P7_MEAN", "quantity"),
    ("FIXED_S10P7", "quantity"),
    ("FIXED_S10P7_MEAN", "quantity"),
    ("FIXED_Y10P7", "quantity"),
    ("FIXED_Y10P7_MEAN", "quantity"),
)

_OD_FIELDS: _FieldTable = (
    ("OD_ID", "str"),
    ("OD_PREV_ID", "str"),
    ("OD_METHOD", "str"),
    ("OD_EPOCH", "str"),
    ("DAYS_SINCE_FIRST_OBS", "quantity"),
    ("DAYS_SINCE_LAST_OBS", "quantity"),
    ("RECOMMENDED_OD_SPAN", "quantity"),
    ("ACTUAL_OD_SPAN", "quantity"),
    ("OBS_AVAILABLE", "int"),
    ("OBS_USED", "int"),
    ("TRACKS_AVAILABLE", "int"),
    ("TRACKS_USED", "int"),
    ("MAXIMUM_OBS_GAP", "quantity"),
    ("OD_EPOCH_EIGMAJ", "quantity"),
    ("OD_EPOCH_EIGINT", "quantity"),
    ("OD_EPOCH_EIGMIN", "quantity"),
    ("OD_MAX_PRED_EIGMAJ", "quantity"),
    ("OD_MIN_PRED_EIGMIN", "quantity"),
    ("OD_CONFIDENCE", "quantity"),
    ("GDOP", "float"),
    ("SOLVE_N", "int"),
    ("SOLVE_STATES", "str"),
    ("CONSIDER_N", "int"),
    ("CONSIDER_PARAMS", "str"),
    ("SEDR", "quantity"),
    ("SENSORS_N", "int"),
    ("SENSORS", "str"),
    ("WEIGHTED_RMS", "float"),
    ("DATA_TYPES", "str"),
)

# The keywords each block must carry (XSD elements without ``minOccurs="0"``). The metadata
# requires the time system and the message epoch; the data blocks require the frame / type
# keywords needed to interpret their data lines.
_METADATA_REQUIRED = ("TIME_SYSTEM", "EPOCH_TZERO")
_TRAJ_REQUIRED = ("CENTER_NAME", "TRAJ_REF_FRAME", "TRAJ_TYPE")
_COV_REQUIRED = ("COV_REF_FRAME", "COV_TYPE", "COV_ORDERING")
_MAN_REQUIRED = ("MAN_ID", "MAN_DEVICE_ID", "MAN_REF_FRAME", "DC_TYPE", "MAN_COMPOSITION")
_OD_REQUIRED = ("OD_ID", "OD_METHOD", "OD_EPOCH")

# OCM KVN block markers, each alone on its own line.
_META_START, _META_STOP = "META_START", "META_STOP"
_TRAJ_START, _TRAJ_STOP = "TRAJ_START", "TRAJ_STOP"
_PHYS_START, _PHYS_STOP = "PHYS_START", "PHYS_STOP"
_COV_START, _COV_STOP = "COV_START", "COV_STOP"
_MAN_START, _MAN_STOP = "MAN_START", "MAN_STOP"
_PERT_START, _PERT_STOP = "PERT_START", "PERT_STOP"
_OD_START, _OD_STOP = "OD_START", "OD_STOP"
_USER_START, _USER_STOP = "USER_START", "USER_STOP"
_USER_DEFINED_PREFIX = "USER_DEFINED_"

# The Cartesian trajectory types the canonical ephemeris can hold: position + velocity, with
# the optional acceleration triplet (CARTPVA) preserved on the fidelity model only. A
# non-Cartesian TRAJ_TYPE (Keplerian, equinoctial, …) is carried faithfully but not projected.
_CARTESIAN_TRAJ_TYPES = frozenset({"CARTPV", "CARTPVA"})


# --- fidelity model --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OcmKeywordBlock:
    """A block of typed ``(keyword, value)`` fields plus its ``COMMENT`` lines.

    Models the OCM metadata block and the keyword-only data blocks (``phys`` / ``pert`` /
    ``od``). ``fields`` is in canonical (schema) order, so a KVN-read and an XML-read block
    compare equal regardless of source ordering.
    """

    fields: tuple[tuple[str, FieldValue], ...] = ()
    comments: tuple[str, ...] = ()

    def get(self, keyword: str) -> FieldValue | None:
        """The value for ``keyword`` if the block carries it, else ``None``."""
        for key, value in self.fields:
            if key == keyword:
                return value
        return None


@dataclass(frozen=True, slots=True)
class OcmTrajectoryBlock:
    """One OCM ``traj`` block: its keyword fields, its data lines, and comments.

    ``lines`` are the trajectory state lines (``trajLine``) verbatim — an epoch token plus the
    state components per ``TRAJ_TYPE`` — carried as text so the block round-trips losslessly
    regardless of element set. The Cartesian ones are interpreted into the canonical ephemeris.
    """

    fields: tuple[tuple[str, FieldValue], ...]
    lines: tuple[str, ...]
    comments: tuple[str, ...] = ()

    def get(self, keyword: str) -> FieldValue | None:
        for key, value in self.fields:
            if key == keyword:
                return value
        return None


@dataclass(frozen=True, slots=True)
class OcmCovarianceBlock:
    """One OCM ``cov`` block: its keyword fields, its ``covLine`` data lines, and comments."""

    fields: tuple[tuple[str, FieldValue], ...]
    lines: tuple[str, ...]
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OcmManeuverBlock:
    """One OCM ``man`` block: its keyword fields, its ``manLine`` data lines, and comments."""

    fields: tuple[tuple[str, FieldValue], ...]
    lines: tuple[str, ...]
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OcmUserDefined:
    """The OCM ``user`` block: ``USER_DEFINED_<key> = value`` parameters, in order."""

    parameters: tuple[tuple[str, str], ...] = ()
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class OcmFile(FidelityModel):
    """The faithful OCM fidelity model: the header plus the single segment's every block.

    Holds every field a same-format OCM write reconstructs from, so an OCM → OCM round-trip
    stays content-lossless. ``raw_bytes`` is the verbatim source, kept only when the read
    opted in via ``retain_source=True``; ``serialization`` records the notation the file was
    read from (``"kvn"`` or ``"xml"``) so a write re-emits in the same notation by default.
    """

    format_name: ClassVar[str] = "ccsds-ocm"

    ccsds_version: str
    metadata: OcmKeywordBlock
    trajectories: tuple[OcmTrajectoryBlock, ...] = ()
    physical: OcmKeywordBlock | None = None
    covariances: tuple[OcmCovarianceBlock, ...] = ()
    maneuvers: tuple[OcmManeuverBlock, ...] = ()
    perturbations: OcmKeywordBlock | None = None
    orbit_determination: OcmKeywordBlock | None = None
    user_defined: OcmUserDefined | None = None
    creation_date: str | None = None
    originator: str | None = None
    message_id: str | None = None
    classification: str | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


# --- public reader ---------------------------------------------------------------------


def read_ocm(source: Source) -> Ephemeris:
    """Read a CCSDS OCM (KVN or XML) into a canonical :class:`Ephemeris`.

    Parses the header and the single segment's blocks into an :class:`OcmFile` fidelity model,
    retained as ``source_native``, then builds the canonical ephemeris from the Cartesian
    trajectory blocks (concatenated when there is more than one), tagging it with the frame,
    central body, time scale, and object id from the OCM metadata. Trajectory state lines time
    against ``EPOCH_TZERO`` either absolutely (a calendar epoch token) or relatively (a numeric
    offset in seconds). The notation is detected from the content — an XML document routes to
    the xsdata bindings (:mod:`orbit_formats.adapters.ocm_xml`), everything else to the
    hand-written KVN scanner — and both produce the same :class:`OcmFile`. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword, an
    unclosed or unknown block, an unrecognised keyword, a malformed trajectory line or epoch,
    malformed XML, or trajectory blocks that disagree on frame / central body.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.ocm_xml import ocmfile_from_xml

        ocm = ocmfile_from_xml(source.read_bytes())
    else:
        ocm = _OcmParser(text.splitlines()).parse()
    if source.retain:
        ocm = replace(ocm, raw_bytes=source.read_bytes())
    return _to_ephemeris(ocm)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is an OCM in XML rather than KVN — its first content is an XML tag."""
    return text.lstrip("﻿ \t\r\n").startswith("<")


# --- KVN scanner -----------------------------------------------------------------------


class _OcmParser:
    """A single-pass, blank-tolerant scanner over an OCM's KVN lines."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._i = 0

    def parse(self) -> OcmFile:
        version, creation_date, originator, message_id, classification, comments = (
            self._parse_header()
        )
        metadata = self._parse_metadata()
        trajectories: list[OcmTrajectoryBlock] = []
        physical: OcmKeywordBlock | None = None
        covariances: list[OcmCovarianceBlock] = []
        maneuvers: list[OcmManeuverBlock] = []
        perturbations: OcmKeywordBlock | None = None
        orbit_determination: OcmKeywordBlock | None = None
        user_defined: OcmUserDefined | None = None
        while True:
            line = self._peek()
            if line is None:
                break
            marker = line.strip().upper()
            if marker == _TRAJ_START:
                trajectories.append(self._parse_traj())
            elif marker == _PHYS_START:
                _reject_duplicate("PHYS", physical)
                physical = self._parse_keyword_block(
                    "PHYS", _PHYS_START, _PHYS_STOP, _PHYS_FIELDS, ()
                )
            elif marker == _COV_START:
                covariances.append(self._parse_cov())
            elif marker == _MAN_START:
                maneuvers.append(self._parse_man())
            elif marker == _PERT_START:
                _reject_duplicate("PERT", perturbations)
                perturbations = self._parse_keyword_block(
                    "PERT", _PERT_START, _PERT_STOP, _PERT_FIELDS, ()
                )
            elif marker == _OD_START:
                _reject_duplicate("OD", orbit_determination)
                orbit_determination = self._parse_keyword_block(
                    "OD", _OD_START, _OD_STOP, _OD_FIELDS, _OD_REQUIRED
                )
            elif marker == _USER_START:
                _reject_duplicate("USER", user_defined)
                user_defined = self._parse_user()
            else:
                raise MalformedSourceError(
                    f"unexpected content outside an OCM data block: {line.strip()!r}"
                )
        return OcmFile(
            ccsds_version=version,
            metadata=metadata,
            trajectories=tuple(trajectories),
            physical=physical,
            covariances=tuple(covariances),
            maneuvers=tuple(maneuvers),
            perturbations=perturbations,
            orbit_determination=orbit_determination,
            user_defined=user_defined,
            creation_date=creation_date,
            originator=originator,
            message_id=message_id,
            classification=classification,
            comments=tuple(comments),
        )

    def _parse_header(
        self,
    ) -> tuple[str, str | None, str | None, str | None, str | None, list[str]]:
        version: str | None = None
        creation_date: str | None = None
        originator: str | None = None
        message_id: str | None = None
        classification: str | None = None
        comments: list[str] = []
        while True:
            line = self._peek()
            if line is None or line.strip().upper() == _META_START:
                break
            stripped = self._next_stripped()
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            key, value = self._require_keyword(stripped, "header")
            if key == "CCSDS_OCM_VERS":
                version = value
            elif key == "CLASSIFICATION":
                classification = value
            elif key == "CREATION_DATE":
                creation_date = value
            elif key == "ORIGINATOR":
                originator = value
            elif key == "MESSAGE_ID":
                message_id = value
            else:
                raise MalformedSourceError(
                    f"unexpected keyword {key!r} in the OCM header before META_START"
                )
        if version is None:
            raise MalformedSourceError(
                "not a CCSDS OCM: the 'CCSDS_OCM_VERS' header keyword is missing"
            )
        return version, creation_date, originator, message_id, classification, comments

    def _parse_metadata(self) -> OcmKeywordBlock:
        line = self._peek()
        if line is None or line.strip().upper() != _META_START:
            got = "end of file" if line is None else repr(line.strip())
            raise MalformedSourceError(f"expected META_START after the OCM header, got {got}")
        return self._parse_keyword_block(
            "META", _META_START, _META_STOP, _METADATA_FIELDS, _METADATA_REQUIRED
        )

    def _parse_keyword_block(
        self, name: str, start: str, stop: str, table: _FieldTable, required: tuple[str, ...]
    ) -> OcmKeywordBlock:
        self._next()  # consume the START marker (already confirmed by the caller)
        kinds = dict(table)
        values: dict[str, FieldValue] = {}
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError(f"OCM {name} block was not closed with {stop}")
            stripped = line.strip()
            if stripped.upper() == stop:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            key, raw = self._require_keyword(stripped, f"{name} block")
            if key not in kinds:
                raise MalformedSourceError(f"unexpected OCM {name} keyword {key!r}")
            if key in values:
                raise MalformedSourceError(f"duplicate OCM {name} keyword {key!r}")
            values[key] = _coerce_field(key, kinds[key], raw)
        _require_fields(name, values, required)
        return OcmKeywordBlock(fields=_ordered(values, table), comments=tuple(comments))

    def _parse_data_block(
        self, name: str, start: str, stop: str, table: _FieldTable, required: tuple[str, ...]
    ) -> tuple[tuple[tuple[str, FieldValue], ...], tuple[str, ...], tuple[str, ...]]:
        """Parse a ``traj`` / ``cov`` / ``man`` block: keyword fields + data lines + comments."""
        self._next()  # consume the START marker
        kinds = dict(table)
        values: dict[str, FieldValue] = {}
        comments: list[str] = []
        lines: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError(f"OCM {name} block was not closed with {stop}")
            stripped = line.strip()
            if stripped.upper() == stop:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            match = _KEYWORD_RE.match(stripped)
            if match is not None:
                key = match.group(1).upper()
                if key not in kinds:
                    raise MalformedSourceError(f"unexpected OCM {name} keyword {key!r}")
                if key in values:
                    raise MalformedSourceError(f"duplicate OCM {name} keyword {key!r}")
                values[key] = _coerce_field(key, kinds[key], match.group(2).strip())
            else:
                lines.append(stripped)
        _require_fields(name, values, required)
        if not lines:
            raise MalformedSourceError(f"OCM {name} block carries no data lines")
        return _ordered(values, table), tuple(lines), tuple(comments)

    def _parse_traj(self) -> OcmTrajectoryBlock:
        fields, lines, comments = self._parse_data_block(
            "TRAJ", _TRAJ_START, _TRAJ_STOP, _TRAJ_FIELDS, _TRAJ_REQUIRED
        )
        return OcmTrajectoryBlock(fields=fields, lines=lines, comments=comments)

    def _parse_cov(self) -> OcmCovarianceBlock:
        fields, lines, comments = self._parse_data_block(
            "COV", _COV_START, _COV_STOP, _COV_FIELDS, _COV_REQUIRED
        )
        return OcmCovarianceBlock(fields=fields, lines=lines, comments=comments)

    def _parse_man(self) -> OcmManeuverBlock:
        fields, lines, comments = self._parse_data_block(
            "MAN", _MAN_START, _MAN_STOP, _MAN_FIELDS, _MAN_REQUIRED
        )
        return OcmManeuverBlock(fields=fields, lines=lines, comments=comments)

    def _parse_user(self) -> OcmUserDefined:
        self._next()  # consume USER_START
        parameters: list[tuple[str, str]] = []
        comments: list[str] = []
        while True:
            line = self._next()
            if line is None:
                raise MalformedSourceError("OCM USER block was not closed with USER_STOP")
            stripped = line.strip()
            if stripped.upper() == _USER_STOP:
                break
            if _is_comment(stripped):
                comments.append(_comment_text(stripped))
                continue
            key, value = self._require_keyword(stripped, "USER block")
            if not key.startswith(_USER_DEFINED_PREFIX):
                raise MalformedSourceError(
                    f"OCM USER block keyword must start with {_USER_DEFINED_PREFIX!r}, got {key!r}"
                )
            parameters.append((key[len(_USER_DEFINED_PREFIX) :], value))
        return OcmUserDefined(parameters=tuple(parameters), comments=tuple(comments))

    def _require_keyword(self, line: str, where: str) -> tuple[str, str]:
        match = _KEYWORD_RE.match(line)
        if match is None:
            raise MalformedSourceError(
                f"expected 'KEYWORD = value' in the OCM {where}, got {line!r}"
            )
        return match.group(1).upper(), match.group(2).strip()

    def _peek(self) -> str | None:
        while self._i < len(self._lines) and not self._lines[self._i].strip():
            self._i += 1
        return self._lines[self._i] if self._i < len(self._lines) else None

    def _next(self) -> str | None:
        line = self._peek()
        if line is not None:
            self._i += 1
        return line

    def _next_stripped(self) -> str:
        line = self._next()
        assert line is not None  # callers guard EOF via _peek() before calling
        return line.strip()


def _reject_duplicate(name: str, existing: object | None) -> None:
    """Assert a singleton OCM block (PHYS / PERT / OD / USER) has not already been seen."""
    if existing is not None:
        raise MalformedSourceError(f"OCM has more than one {name} block")


# --- value (de)serialisation, shared with the KVN writer and the XML adapter -----------

_QUANTITY_RE = re.compile(r"^(?P<number>.*?)\s*\[(?P<unit>[^\]]*)\]\s*$")


def _coerce_field(keyword: str, kind: FieldKind, raw: str) -> FieldValue:
    """Coerce a raw KVN value to the scalar kind its keyword declares."""
    if kind == "int":
        try:
            return int(raw)
        except ValueError as exc:
            raise MalformedSourceError(f"OCM {keyword} must be an integer, got {raw!r}") from exc
    if kind == "float":
        return _to_float(keyword, raw)
    if kind == "quantity":
        return _parse_quantity(keyword, raw)
    if kind == "vec3":
        try:
            return tuple(float(token) for token in raw.split())
        except ValueError as exc:
            raise MalformedSourceError(
                f"OCM {keyword} must be space-separated numbers, got {raw!r}"
            ) from exc
    return raw


def format_field(kind: FieldKind, value: FieldValue) -> str:
    """Format a typed value back to its KVN text. Shared by the writer and the XML adapter."""
    if kind == "int":
        assert isinstance(value, int)
        return str(value)
    if kind == "float":
        assert isinstance(value, (int, float))
        return _format_float(float(value))
    if kind == "quantity":
        assert isinstance(value, Quantity)
        unit = f" [{value.units}]" if value.units is not None else ""
        return f"{_format_float(value.value)}{unit}"
    if kind == "vec3":
        assert isinstance(value, tuple)
        return " ".join(_format_float(component) for component in value)
    return str(value)


def _parse_quantity(keyword: str, raw: str) -> Quantity:
    match = _QUANTITY_RE.match(raw)
    if match is not None:
        number, unit = match.group("number").strip(), match.group("unit").strip()
    else:
        number, unit = raw.strip(), None
    return Quantity(_to_float(keyword, number), unit)


def _to_float(keyword: str, raw: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise MalformedSourceError(f"OCM {keyword} must be a number, got {raw!r}") from exc


def _format_float(value: float) -> str:
    """Shortest decimal string that round-trips to the same float64 — no precision lost."""
    return repr(float(value))


def _ordered(
    values: dict[str, FieldValue], table: _FieldTable
) -> tuple[tuple[str, FieldValue], ...]:
    """Order a collected mapping into the table's canonical sequence (KVN ↔ XML parity)."""
    return tuple((keyword, values[keyword]) for keyword, _kind in table if keyword in values)


def _require_fields(name: str, values: dict[str, FieldValue], required: tuple[str, ...]) -> None:
    missing = [keyword for keyword in required if keyword not in values]
    if missing:
        raise MalformedSourceError(
            f"OCM {name} block is missing required keyword(s): {', '.join(missing)}"
        )


# --- adaptation to the canonical ephemeris ---------------------------------------------


@dataclass(frozen=True, slots=True)
class _TrajStates:
    """Cartesian states pulled from one trajectory block, with its frame / central body."""

    center_name: str
    ref_frame: str
    epochs: list[np.datetime64] = field(default_factory=list)
    positions: list[list[float]] = field(default_factory=list)
    velocities: list[list[float]] = field(default_factory=list)


def _to_ephemeris(ocm: OcmFile) -> Ephemeris:
    """Adapt an :class:`OcmFile` into the canonical :class:`Ephemeris`.

    Concatenates the Cartesian trajectory blocks' states into one series (after asserting they
    share a frame and central body), timing each line against ``EPOCH_TZERO``. The ``man`` blocks
    map into the canonical ``maneuvers`` collection (one record per ``manLine``). A non-Cartesian
    trajectory, and every other block, is carried on the ``source_native`` model only — the
    canonical ephemeris holds position and velocity. An OCM with no Cartesian trajectory yields
    an empty ephemeris (whose maneuvers and other blocks still live on ``source_native``).
    """
    tzero = _epoch_tzero(ocm.metadata)
    cartesian = [
        _states_from_traj(traj, tzero)
        for traj in ocm.trajectories
        if _traj_type(traj) in _CARTESIAN_TRAJ_TYPES
    ]
    _require_consistent_trajectories(cartesian)
    epochs: list[np.datetime64] = []
    positions: list[list[float]] = []
    velocities: list[list[float]] = []
    for states in cartesian:
        epochs.extend(states.epochs)
        positions.extend(states.positions)
        velocities.extend(states.velocities)

    first = cartesian[0] if cartesian else None
    interpolation, degree = _interpolation_of(ocm)
    metadata = Metadata(
        object_name=_as_str(ocm.metadata.get("OBJECT_NAME")),
        object_id=_as_str(ocm.metadata.get("INTERNATIONAL_DESIGNATOR")),
        originator=ocm.originator,
        reference_frame=first.ref_frame if first is not None else None,
        central_body=first.center_name if first is not None else None,
        time_scale=_time_scale(ocm.metadata),
        provenance=Provenance(source_format="ccsds-ocm", creation_date=ocm.creation_date),
    )
    return Ephemeris(
        metadata=metadata,
        source_native=ocm,
        epochs=_datetime_array(epochs),
        positions=_float_matrix(positions),
        velocities=_float_matrix(velocities),
        interpolation=interpolation,
        interpolation_degree=degree,
        maneuvers=_canonical_maneuvers(ocm, tzero),
    )


def _states_from_traj(traj: OcmTrajectoryBlock, tzero: np.datetime64 | None) -> _TrajStates:
    center = _as_str(traj.get("CENTER_NAME")) or ""
    frame = _as_str(traj.get("TRAJ_REF_FRAME")) or ""
    states = _TrajStates(center_name=center, ref_frame=frame)
    for line in traj.lines:
        tokens = line.split()
        if len(tokens) < 7:
            raise MalformedSourceError(
                f"OCM Cartesian trajectory line needs a time plus 6 components, got {line!r}"
            )
        states.epochs.append(_traj_epoch(tokens[0], tzero))
        try:
            numbers = [float(token) for token in tokens[1:7]]
        except ValueError as exc:
            raise MalformedSourceError(
                f"non-numeric value in the OCM trajectory line {line!r}"
            ) from exc
        states.positions.append(numbers[0:3])
        states.velocities.append(numbers[3:6])
    return states


def _traj_epoch(token: str, tzero: np.datetime64 | None) -> np.datetime64:
    """An OCM trajectory time: an absolute epoch, or a seconds offset from ``EPOCH_TZERO``."""
    if "T" in token or token.count("-") > 1:
        return _parse_epoch(token)
    if tzero is None:
        raise MalformedSourceError(
            "OCM trajectory line uses a relative time but the metadata has no EPOCH_TZERO"
        )
    try:
        offset_seconds = float(token)
    except ValueError as exc:
        raise MalformedSourceError(
            f"OCM trajectory line time must be an epoch or a numeric offset, got {token!r}"
        ) from exc
    return tzero + np.timedelta64(round(offset_seconds * 1_000_000_000), "ns")


def _epoch_tzero(metadata: OcmKeywordBlock) -> np.datetime64 | None:
    raw = metadata.get("EPOCH_TZERO")
    return _parse_epoch(raw) if isinstance(raw, str) else None


def _traj_type(traj: OcmTrajectoryBlock) -> str:
    value = traj.get("TRAJ_TYPE")
    return value.upper() if isinstance(value, str) else ""


def _interpolation_of(ocm: OcmFile) -> tuple[str | None, int | None]:
    for traj in ocm.trajectories:
        if _traj_type(traj) in _CARTESIAN_TRAJ_TYPES:
            interpolation = traj.get("INTERPOLATION")
            degree = traj.get("INTERPOLATION_DEGREE")
            return (
                interpolation if isinstance(interpolation, str) else None,
                degree if isinstance(degree, int) else None,
            )
    return None, None


def _time_scale(metadata: OcmKeywordBlock) -> str | None:
    value = metadata.get("TIME_SYSTEM")
    return _canonical_time_scale(value) if isinstance(value, str) else None


def _require_consistent_trajectories(blocks: list[_TrajStates]) -> None:
    """Reject Cartesian trajectory blocks that cannot share one canonical series.

    They are concatenated under one metadata spine, so they must agree on the reference frame
    and central body; the reader does not transform between frames, so a disagreement raises.
    """
    if not blocks:
        return
    first = blocks[0]
    for block in blocks[1:]:
        for label, expected, actual in (
            ("TRAJ_REF_FRAME", first.ref_frame, block.ref_frame),
            ("CENTER_NAME", first.center_name, block.center_name),
        ):
            if expected != actual:
                raise MalformedSourceError(
                    f"OCM trajectory blocks disagree on {label} ({expected!r} vs {actual!r}); "
                    "states across different values cannot be concatenated into one ephemeris"
                )


def _as_str(value: FieldValue | None) -> str | None:
    return value if isinstance(value, str) else None


# --- adaptation of the man blocks to the canonical maneuver record ---------------------

# The MAN_COMPOSITION time tokens, and the value tokens the canonical maneuver record reads.
# Everything else a composition can list (thrust, acceleration, deterministic-command timing,
# per-element sigmas, deployment terms) stays on the OcmFile ``source_native`` only.
_MAN_TIME_COLUMNS = frozenset({"TIME_ABSOLUTE", "TIME_RELATIVE"})
_DV_COLUMNS = ("DV_X", "DV_Y", "DV_Z")
# Δv unit token → factor to the canonical km/s. An *unstated* unit (no MAN_UNITS, or a count
# that matches no column layout) defaults to km/s — the canonical speed unit and the (unit-less)
# OPM convention — warning-free, since nothing was stated to honour. A unit that *is* stated but
# is not one of these is a different matter: it cannot be honoured, so the Δv is read as km/s and
# the loss is named through warn_lossy (see _warn_unrecognised_dv_units) rather than mis-scaled in
# silence.
_DV_TO_KM_S = {"km/s": 1.0, "m/s": 1.0e-3}


def _canonical_maneuvers(ocm: OcmFile, tzero: np.datetime64 | None) -> tuple[Maneuver, ...]:
    """The canonical maneuvers across every OCM ``man`` block, one record per ``manLine``."""
    maneuvers: list[Maneuver] = []
    for block in ocm.maneuvers:
        maneuvers.extend(_maneuvers_from_block(block, tzero))
    return tuple(maneuvers)


def _maneuvers_from_block(block: OcmManeuverBlock, tzero: np.datetime64 | None) -> list[Maneuver]:
    """Read one ``man`` block into canonical maneuvers via its ``MAN_COMPOSITION`` columns.

    ``MAN_COMPOSITION`` names the columns each ``manLine`` carries; the time column places the
    burn (absolute epoch, or seconds relative to ``EPOCH_TZERO``), ``DV_X/DV_Y/DV_Z`` give the
    Δv (scaled to km/s via ``MAN_UNITS``), ``MAN_DURA`` the duration, and ``DELTA_MASS`` the mass
    change. A block whose composition has no time column cannot place its burns in time, so it
    yields no canonical record and survives on ``source_native`` alone. The block's leading
    comments attach to the first maneuver only, so a multi-line block does not duplicate them.
    """
    ref_frame = _man_field(block, "MAN_REF_FRAME")
    composition = _man_field(block, "MAN_COMPOSITION")
    if not isinstance(ref_frame, str) or not isinstance(composition, str):
        return []  # MAN_REF_FRAME and MAN_COMPOSITION are required keywords; guard defensively
    columns = [token.strip() for token in composition.split(",")]
    time_index = next((i for i, column in enumerate(columns) if column in _MAN_TIME_COLUMNS), None)
    if time_index is None:
        return []
    time_kind = columns[time_index]
    units = _man_unit_map(block, columns)
    dv_indices = _dv_indices(columns)
    if dv_indices is not None:
        _warn_unrecognised_dv_units(units)
    dura_index = columns.index("MAN_DURA") if "MAN_DURA" in columns else None
    dmass_index = columns.index("DELTA_MASS") if "DELTA_MASS" in columns else None

    maneuvers: list[Maneuver] = []
    for position, line in enumerate(block.lines):
        tokens = line.split()
        if len(tokens) != len(columns):
            raise MalformedSourceError(
                f"OCM maneuver line has {len(tokens)} value(s) but MAN_COMPOSITION names "
                f"{len(columns)} column(s): {line!r}"
            )
        duration = _man_float(tokens[dura_index], "MAN_DURA") if dura_index is not None else 0.0
        delta_v = _man_delta_v(tokens, dv_indices, units) if dv_indices is not None else None
        delta_mass = (
            _man_float(tokens[dmass_index], "DELTA_MASS") if dmass_index is not None else None
        )
        maneuvers.append(
            Maneuver(
                epoch_ignition=_man_epoch(tokens[time_index], time_kind, tzero),
                ref_frame=ref_frame,
                duration=duration,
                delta_v=delta_v,
                delta_mass=delta_mass,
                comments=block.comments if position == 0 else (),
            )
        )
    return maneuvers


def _man_field(block: OcmManeuverBlock, keyword: str) -> FieldValue | None:
    for key, value in block.fields:
        if key == keyword:
            return value
    return None


def _dv_indices(columns: list[str]) -> tuple[int, int, int] | None:
    """The ``(DV_X, DV_Y, DV_Z)`` column indices, or ``None`` unless all three are present.

    A partial Δv (some components only) is not a vector, so it is not surfaced — the block's
    full data survives on ``source_native``.
    """
    if all(column in columns for column in _DV_COLUMNS):
        x, y, z = (columns.index(column) for column in _DV_COLUMNS)
        return x, y, z
    return None


def _man_unit_map(block: OcmManeuverBlock, columns: list[str]) -> dict[str, str]:
    """Map each composition column to its ``MAN_UNITS`` token, when the counts line up.

    ``MAN_UNITS`` is a comma-separated list whose tokens describe either every column or just
    the non-time columns; a single token applies to all non-time columns. Anything else leaves
    the map empty and the readers fall back to the canonical default unit.
    """
    raw = _man_field(block, "MAN_UNITS")
    if not isinstance(raw, str):
        return {}
    units = [token.strip() for token in raw.split(",")]
    non_time = [column for column in columns if column not in _MAN_TIME_COLUMNS]
    if len(units) == len(columns):
        return dict(zip(columns, units, strict=True))
    if len(units) == len(non_time):
        return dict(zip(non_time, units, strict=True))
    if len(units) == 1 and non_time:
        return {column: units[0] for column in non_time}
    return {}


def _warn_unrecognised_dv_units(units: dict[str, str]) -> None:
    """Warn once per block if a Δv column states a unit this reader cannot scale to km/s.

    Only a *stated* Δv unit triggers this — a column absent from ``units`` legitimately falls
    back to the canonical km/s (see :data:`_DV_TO_KM_S`). A stated unit that is neither ``km/s``
    nor ``m/s`` cannot be honoured: the Δv is read as km/s and may be mis-scaled, so the loss is
    named rather than applied in silence. Duplicate tokens (the common single-unit-for-all case)
    collapse to one named field.
    """
    unrecognised = sorted(
        {
            units[column]
            for column in _DV_COLUMNS
            if column in units and units[column] not in _DV_TO_KM_S
        }
    )
    if not unrecognised:
        return
    listed = ", ".join(repr(unit) for unit in unrecognised)
    warn_lossy(
        LossyConversionWarning(
            f"OCM maneuver Δv unit {listed} is not recognised; the Δv was read as km/s "
            f"(the canonical default) and may be mis-scaled",
            dropped=tuple(
                DroppedField("MAN_UNITS", f"the stated Δv unit {unit} is not km/s or m/s")
                for unit in unrecognised
            ),
        ),
        stacklevel=3,
    )


def _man_delta_v(
    tokens: list[str], dv_indices: tuple[int, int, int], units: dict[str, str]
) -> NDArray[np.float64]:
    components = [
        _man_float(tokens[index], column) * _DV_TO_KM_S.get(units.get(column, "km/s"), 1.0)
        for column, index in zip(_DV_COLUMNS, dv_indices, strict=True)
    ]
    return np.array(components, dtype=np.float64)


def _man_epoch(token: str, time_kind: str, tzero: np.datetime64 | None) -> np.datetime64:
    """An OCM maneuver ignition time: an absolute epoch, or seconds relative to ``EPOCH_TZERO``."""
    if time_kind == "TIME_ABSOLUTE":
        return _parse_epoch(token)
    if tzero is None:
        raise MalformedSourceError(
            "OCM maneuver uses a relative time but the metadata has no EPOCH_TZERO"
        )
    offset_seconds = _man_float(token, "TIME_RELATIVE")
    return tzero + np.timedelta64(round(offset_seconds * 1_000_000_000), "ns")


def _man_float(token: str, column: str) -> float:
    try:
        return float(token)
    except ValueError as exc:
        raise MalformedSourceError(
            f"OCM maneuver {column} value must be a number, got {token!r}"
        ) from exc


register_reader("ccsds-ocm", read_ocm)
