"""CCSDS OPM reader — in-house parsing of the Orbit Parameter Message into a fidelity model.

The KVN reader is hand-written; the XML form is parsed through orbit-formats' own MIT xsdata
bindings (see :mod:`orbit_formats.adapters.opm_xml`). No GPL dependency is ever imported at
runtime. Both notations parse into the *same* faithful :class:`OpmFile` fidelity model —
every field the OPM defines, across the header, metadata, the mandatory Cartesian state
vector, and the optional Keplerian / spacecraft / covariance / maneuver / user-defined blocks
— which is then adapted into a canonical :class:`~orbit_formats.canonical.state.StateVector`.
The notation a file was read from is recorded on the model (``serialization``) so a write
re-emits in the same notation by default. :func:`read_opm` dispatches on content: an XML
document routes to the XML parser, everything else to the hand-written KVN scanner.

An OPM KVN message is a flat sequence of ``KEYWORD = value`` lines (no ``META_START`` blocks,
as the message carries a single state); each keyword is routed to its block by name, and
``COMMENT`` lines lead the block that follows them. The maneuver block is *repeatable* — each
maneuver opens with ``MAN_EPOCH_IGNITION`` — so a fresh ignition keyword starts a new
maneuver. Covariance is the 21 keyword lines ``CX_X = …`` (the lower triangle of the
symmetric 6x6), optionally preceded by ``COV_REF_FRAME``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar, Literal

import numpy as np

from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.canonical.state import KeplerianElements, StateVector
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import (
    _KEYWORD_RE,
    _canonical_time_scale,
    _comment_text,
    _is_comment,
    _parse_epoch,
)
from orbit_formats.readers.ccsds_omm import (
    _COVARIANCE_KEYS,
    _kvn_float,
    _require,
    _strip_units,
)
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = [
    "OpmCovariance",
    "OpmFile",
    "OpmKeplerianElements",
    "OpmManeuver",
    "OpmMetadata",
    "OpmSpacecraftParameters",
    "OpmStateVector",
    "read_opm",
]

# Keyword → block routing for the flat KVN scanner. A keyword's block tells the scanner
# which block any pending COMMENT lines lead, and where the value belongs.
_HEADER_KEYS = frozenset({"CCSDS_OPM_VERS", "CREATION_DATE", "ORIGINATOR", "MESSAGE_ID"})
_META_KEYS = frozenset(
    {"OBJECT_NAME", "OBJECT_ID", "CENTER_NAME", "REF_FRAME", "REF_FRAME_EPOCH", "TIME_SYSTEM"}
)
_STATE_KEYS = frozenset({"EPOCH", "X", "Y", "Z", "X_DOT", "Y_DOT", "Z_DOT"})
_KEPLERIAN_KEYS = frozenset(
    {
        "SEMI_MAJOR_AXIS",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "TRUE_ANOMALY",
        "MEAN_ANOMALY",
        "GM",
    }
)
_SPACECRAFT_KEYS = frozenset(
    {"MASS", "SOLAR_RAD_AREA", "SOLAR_RAD_COEFF", "DRAG_AREA", "DRAG_COEFF"}
)
_COVARIANCE_FRAME_KEYS = frozenset({"COV_REF_FRAME", *_COVARIANCE_KEYS})
_MANEUVER_KEYS = frozenset(
    {
        "MAN_EPOCH_IGNITION",
        "MAN_DURATION",
        "MAN_DELTA_MASS",
        "MAN_REF_FRAME",
        "MAN_DV_1",
        "MAN_DV_2",
        "MAN_DV_3",
    }
)


@dataclass(frozen=True, slots=True)
class OpmMetadata:
    """The OPM metadata block — the object, frame, and time system the state is tagged with."""

    object_name: str
    object_id: str
    center_name: str
    ref_frame: str
    time_system: str
    ref_frame_epoch: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpmStateVector:
    """The mandatory OPM state vector — the Cartesian position / velocity at one epoch.

    ``x`` / ``y`` / ``z`` are km and ``x_dot`` / ``y_dot`` / ``z_dot`` km/s, in the metadata's
    reference frame. The OPM state vector carries no acceleration triplet (unlike an OEM
    ephemeris line).
    """

    epoch: np.datetime64
    x: float
    y: float
    z: float
    x_dot: float
    y_dot: float
    z_dot: float
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpmKeplerianElements:
    """The optional OPM osculating Keplerian block.

    ``semi_major_axis`` (km), ``eccentricity``, and the angles (degrees) describe the
    osculating orbit; exactly one of ``true_anomaly`` / ``mean_anomaly`` is present, and
    ``gm`` (km^3/s^2) is mandatory when the block is. The block is a redundant restatement of
    the Cartesian state vector, kept verbatim here.
    """

    semi_major_axis: float
    eccentricity: float
    inclination: float
    ra_of_asc_node: float
    arg_of_pericenter: float
    gm: float
    true_anomaly: float | None = None
    mean_anomaly: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpmSpacecraftParameters:
    """The optional OPM spacecraft-parameters block — mass, drag, and solar-radiation areas."""

    mass: float | None = None
    solar_rad_area: float | None = None
    solar_rad_coeff: float | None = None
    drag_area: float | None = None
    drag_coeff: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpmCovariance:
    """The optional OPM covariance — the 21 lower-triangular elements of the symmetric 6x6.

    ``matrix`` holds the elements in row order (the canonical lower-triangular layout);
    ``cov_ref_frame`` is the frame the matrix is expressed in when the block names one. The
    OPM covariance carries no epoch of its own (it is at the state-vector epoch).
    """

    matrix: tuple[float, ...]
    cov_ref_frame: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OpmManeuver:
    """One optional OPM maneuver block — an impulsive or finite burn the message plans.

    Every field is mandatory once the block is present: the ignition epoch, the duration
    (seconds; zero for an impulsive maneuver), the delta-mass (kg, non-positive), the frame
    the delta-v is expressed in, and the three delta-v components (km/s). An OPM may carry
    any number of maneuvers, kept here in file order.
    """

    man_epoch_ignition: np.datetime64
    man_duration: float
    man_delta_mass: float
    man_ref_frame: str
    man_dv_1: float
    man_dv_2: float
    man_dv_3: float
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class OpmFile(FidelityModel):
    """The faithful OPM fidelity model: the header plus every block, in file order.

    Holds every field a same-format OPM write reconstructs from. ``raw_bytes`` is the
    verbatim source kept only when the read opted in via ``retain_source=True``;
    ``serialization`` records the notation it was read from (``"kvn"`` or ``"xml"``) so a
    write re-emits in the same notation by default. ``user_defined`` keeps the
    ``USER_DEFINED_<key> = value`` parameters in order.
    """

    format_name: ClassVar[str] = "ccsds-opm"

    ccsds_version: str
    metadata: OpmMetadata
    state_vector: OpmStateVector
    creation_date: str | None = None
    originator: str | None = None
    message_id: str | None = None
    comments: tuple[str, ...] = ()
    keplerian: OpmKeplerianElements | None = None
    spacecraft_parameters: OpmSpacecraftParameters | None = None
    covariance: OpmCovariance | None = None
    maneuvers: tuple[OpmManeuver, ...] = ()
    user_defined: tuple[tuple[str, str], ...] = ()
    user_defined_comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_opm(source: Source) -> StateVector:
    """Read a CCSDS OPM (KVN or XML) into a canonical :class:`StateVector`.

    Parses the header and every block into an :class:`OpmFile` fidelity model, retained as
    ``source_native``, then adapts the Cartesian state vector into a canonical state tagged
    with the frame, central body, time scale, and object id from the OPM. The notation is
    detected from the content. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword, a
    malformed value or epoch, malformed XML, a partial covariance matrix, or a maneuver
    keyword that does not open with ``MAN_EPOCH_IGNITION``.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.opm_xml import opmfile_from_xml

        opm = opmfile_from_xml(source.read_bytes())
    else:
        opm = _OpmKvnParser(text.splitlines()).parse()
    if source.retain:
        opm = replace(opm, raw_bytes=source.read_bytes())
    return _to_state_vector(opm)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is an OPM in XML rather than KVN — its first content is an XML tag."""
    return text.lstrip("﻿ \t\r\n").startswith("<")


class _OpmKvnParser:
    """A flat scanner over an OPM's KVN lines, routing each keyword to its block."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def parse(self) -> OpmFile:
        header: dict[str, str] = {}
        meta: dict[str, str] = {}
        state: dict[str, str] = {}
        keplerian: dict[str, str] = {}
        spacecraft: dict[str, str] = {}
        cov_frame: dict[str, str] = {}
        cov_values: dict[str, float] = {}
        maneuvers: list[_ManeuverDraft] = []
        user_defined: list[tuple[str, str]] = []
        comments: dict[str, list[str]] = {
            block: [] for block in ("header", "meta", "state", "kep", "sc", "cov", "ud")
        }
        pending: list[str] = []
        current_maneuver: _ManeuverDraft | None = None

        for raw in self._lines:
            stripped = raw.strip()
            if not stripped:
                continue
            if _is_comment(stripped):
                pending.append(_comment_text(stripped))
                continue
            match = _KEYWORD_RE.match(stripped)
            if match is None:
                raise MalformedSourceError(
                    f"expected 'KEYWORD = value' in the OPM, got {stripped!r}"
                )
            key = match.group(1).upper()
            value = _strip_units(match.group(2).strip())
            block = self._block_of(key)
            if block is None:
                raise MalformedSourceError(f"unexpected OPM keyword {key!r}")
            if block == "man":
                current_maneuver = self._route_maneuver(
                    key, value, maneuvers, current_maneuver, pending
                )
            else:
                comments[block].extend(pending)
                self._route(
                    key,
                    value,
                    header,
                    meta,
                    state,
                    keplerian,
                    spacecraft,
                    cov_frame,
                    cov_values,
                    user_defined,
                )
            pending.clear()

        return _build_opm(
            header,
            meta,
            state,
            keplerian,
            spacecraft,
            cov_frame,
            cov_values,
            tuple(maneuvers),
            tuple(user_defined),
            {block: tuple(value) for block, value in comments.items()},
        )

    @staticmethod
    def _block_of(key: str) -> str | None:
        if key in _HEADER_KEYS:
            return "header"
        if key in _META_KEYS:
            return "meta"
        if key in _STATE_KEYS:
            return "state"
        if key in _KEPLERIAN_KEYS:
            return "kep"
        if key in _SPACECRAFT_KEYS:
            return "sc"
        if key in _COVARIANCE_FRAME_KEYS:
            return "cov"
        if key in _MANEUVER_KEYS:
            return "man"
        if key.startswith("USER_DEFINED_"):
            return "ud"
        return None

    @staticmethod
    def _route_maneuver(
        key: str,
        value: str,
        maneuvers: list[_ManeuverDraft],
        current: _ManeuverDraft | None,
        pending: list[str],
    ) -> _ManeuverDraft:
        """Route a ``MAN_*`` keyword, opening a fresh maneuver on each ``MAN_EPOCH_IGNITION``."""
        if key == "MAN_EPOCH_IGNITION":
            current = _ManeuverDraft(values={}, comments=list(pending))
            maneuvers.append(current)
        elif current is None:
            raise MalformedSourceError(
                f"OPM maneuver keyword {key!r} appeared before MAN_EPOCH_IGNITION"
            )
        else:
            current.comments.extend(pending)
        current.values[key] = value
        return current

    @staticmethod
    def _route(
        key: str,
        value: str,
        header: dict[str, str],
        meta: dict[str, str],
        state: dict[str, str],
        keplerian: dict[str, str],
        spacecraft: dict[str, str],
        cov_frame: dict[str, str],
        cov_values: dict[str, float],
        user_defined: list[tuple[str, str]],
    ) -> None:
        if key.startswith("USER_DEFINED_"):
            user_defined.append((key[len("USER_DEFINED_") :], value))
        elif key in _COVARIANCE_KEYS:
            cov_values[key] = _kvn_float(value, key)
        elif key == "COV_REF_FRAME":
            cov_frame[key] = value
        elif key in _HEADER_KEYS:
            header[key] = value
        elif key in _META_KEYS:
            meta[key] = value
        elif key in _STATE_KEYS:
            state[key] = value
        elif key in _KEPLERIAN_KEYS:
            keplerian[key] = value
        else:
            spacecraft[key] = value


@dataclass(frozen=True, slots=True)
class _ManeuverDraft:
    """A maneuver block being accumulated by the scanner before it is validated."""

    values: dict[str, str]
    comments: list[str]


def _build_opm(
    header: dict[str, str],
    meta: dict[str, str],
    state: dict[str, str],
    keplerian: dict[str, str],
    spacecraft: dict[str, str],
    cov_frame: dict[str, str],
    cov_values: dict[str, float],
    maneuvers: tuple[_ManeuverDraft, ...],
    user_defined: tuple[tuple[str, str], ...],
    comments: dict[str, tuple[str, ...]],
) -> OpmFile:
    if "CCSDS_OPM_VERS" not in header:
        raise MalformedSourceError(
            "not a CCSDS OPM: the 'CCSDS_OPM_VERS' header keyword is missing"
        )
    metadata = OpmMetadata(
        object_name=_require(meta, "OBJECT_NAME", "metadata"),
        object_id=_require(meta, "OBJECT_ID", "metadata"),
        center_name=_require(meta, "CENTER_NAME", "metadata"),
        ref_frame=_require(meta, "REF_FRAME", "metadata"),
        time_system=_require(meta, "TIME_SYSTEM", "metadata"),
        ref_frame_epoch=meta.get("REF_FRAME_EPOCH"),
        comments=comments["meta"],
    )
    return OpmFile(
        ccsds_version=header["CCSDS_OPM_VERS"],
        metadata=metadata,
        state_vector=_build_state_vector(state, comments["state"]),
        creation_date=header.get("CREATION_DATE"),
        originator=header.get("ORIGINATOR"),
        message_id=header.get("MESSAGE_ID"),
        comments=comments["header"],
        keplerian=_build_keplerian(keplerian, comments["kep"]),
        spacecraft_parameters=_build_spacecraft_parameters(spacecraft, comments["sc"]),
        covariance=_build_covariance(cov_frame, cov_values, comments["cov"]),
        maneuvers=tuple(_build_maneuver(draft) for draft in maneuvers),
        user_defined=user_defined,
        user_defined_comments=comments["ud"],
    )


def _build_state_vector(state: dict[str, str], block_comments: tuple[str, ...]) -> OpmStateVector:
    return OpmStateVector(
        epoch=_parse_epoch(_require(state, "EPOCH", "state vector")),
        x=_kvn_float(_require(state, "X", "state vector"), "X"),
        y=_kvn_float(_require(state, "Y", "state vector"), "Y"),
        z=_kvn_float(_require(state, "Z", "state vector"), "Z"),
        x_dot=_kvn_float(_require(state, "X_DOT", "state vector"), "X_DOT"),
        y_dot=_kvn_float(_require(state, "Y_DOT", "state vector"), "Y_DOT"),
        z_dot=_kvn_float(_require(state, "Z_DOT", "state vector"), "Z_DOT"),
        comments=block_comments,
    )


def _build_keplerian(
    keplerian: dict[str, str], block_comments: tuple[str, ...]
) -> OpmKeplerianElements | None:
    if not keplerian:
        return None
    true_anomaly = keplerian.get("TRUE_ANOMALY")
    mean_anomaly = keplerian.get("MEAN_ANOMALY")
    if true_anomaly is None and mean_anomaly is None:
        raise MalformedSourceError(
            "OPM Keplerian elements need TRUE_ANOMALY or MEAN_ANOMALY; neither is present"
        )
    return OpmKeplerianElements(
        semi_major_axis=_kvn_float(
            _require(keplerian, "SEMI_MAJOR_AXIS", "Keplerian elements"), "SEMI_MAJOR_AXIS"
        ),
        eccentricity=_kvn_float(
            _require(keplerian, "ECCENTRICITY", "Keplerian elements"), "ECCENTRICITY"
        ),
        inclination=_kvn_float(
            _require(keplerian, "INCLINATION", "Keplerian elements"), "INCLINATION"
        ),
        ra_of_asc_node=_kvn_float(
            _require(keplerian, "RA_OF_ASC_NODE", "Keplerian elements"), "RA_OF_ASC_NODE"
        ),
        arg_of_pericenter=_kvn_float(
            _require(keplerian, "ARG_OF_PERICENTER", "Keplerian elements"), "ARG_OF_PERICENTER"
        ),
        gm=_kvn_float(_require(keplerian, "GM", "Keplerian elements"), "GM"),
        true_anomaly=None if true_anomaly is None else _kvn_float(true_anomaly, "TRUE_ANOMALY"),
        mean_anomaly=None if mean_anomaly is None else _kvn_float(mean_anomaly, "MEAN_ANOMALY"),
        comments=block_comments,
    )


def _build_spacecraft_parameters(
    spacecraft: dict[str, str], block_comments: tuple[str, ...]
) -> OpmSpacecraftParameters | None:
    if not spacecraft:
        return None
    return OpmSpacecraftParameters(
        mass=None if "MASS" not in spacecraft else _kvn_float(spacecraft["MASS"], "MASS"),
        solar_rad_area=None
        if "SOLAR_RAD_AREA" not in spacecraft
        else _kvn_float(spacecraft["SOLAR_RAD_AREA"], "SOLAR_RAD_AREA"),
        solar_rad_coeff=None
        if "SOLAR_RAD_COEFF" not in spacecraft
        else _kvn_float(spacecraft["SOLAR_RAD_COEFF"], "SOLAR_RAD_COEFF"),
        drag_area=None
        if "DRAG_AREA" not in spacecraft
        else _kvn_float(spacecraft["DRAG_AREA"], "DRAG_AREA"),
        drag_coeff=None
        if "DRAG_COEFF" not in spacecraft
        else _kvn_float(spacecraft["DRAG_COEFF"], "DRAG_COEFF"),
        comments=block_comments,
    )


def _build_covariance(
    cov_frame: dict[str, str], cov_values: dict[str, float], block_comments: tuple[str, ...]
) -> OpmCovariance | None:
    if not cov_values and not cov_frame:
        return None
    missing = [key for key in _COVARIANCE_KEYS if key not in cov_values]
    if missing:
        raise MalformedSourceError(f"OPM covariance is incomplete; missing {', '.join(missing)}")
    return OpmCovariance(
        matrix=tuple(cov_values[key] for key in _COVARIANCE_KEYS),
        cov_ref_frame=cov_frame.get("COV_REF_FRAME"),
        comments=block_comments,
    )


def _build_maneuver(draft: _ManeuverDraft) -> OpmManeuver:
    values = draft.values
    return OpmManeuver(
        man_epoch_ignition=_parse_epoch(_require(values, "MAN_EPOCH_IGNITION", "maneuver")),
        man_duration=_kvn_float(_require(values, "MAN_DURATION", "maneuver"), "MAN_DURATION"),
        man_delta_mass=_kvn_float(_require(values, "MAN_DELTA_MASS", "maneuver"), "MAN_DELTA_MASS"),
        man_ref_frame=_require(values, "MAN_REF_FRAME", "maneuver"),
        man_dv_1=_kvn_float(_require(values, "MAN_DV_1", "maneuver"), "MAN_DV_1"),
        man_dv_2=_kvn_float(_require(values, "MAN_DV_2", "maneuver"), "MAN_DV_2"),
        man_dv_3=_kvn_float(_require(values, "MAN_DV_3", "maneuver"), "MAN_DV_3"),
        comments=tuple(draft.comments),
    )


def _to_state_vector(opm: OpmFile) -> StateVector:
    """Adapt an :class:`OpmFile` into the canonical :class:`StateVector`.

    The mandatory Cartesian state vector becomes the canonical position / velocity; the
    osculating Keplerian block, when it states a true anomaly, populates the optional
    canonical ``keplerian`` (the canonical form holds a true-anomaly representation). The
    covariance, maneuver, spacecraft, and full Keplerian blocks the canonical state cannot
    hold ride along on ``source_native`` (the whole :class:`OpmFile`), so nothing is lost.
    """
    md = opm.metadata
    metadata = Metadata(
        object_name=md.object_name,
        object_id=md.object_id,
        originator=opm.originator,
        reference_frame=md.ref_frame,
        central_body=md.center_name,
        time_scale=_canonical_time_scale(md.time_system),
        provenance=Provenance(source_format="ccsds-opm", creation_date=opm.creation_date),
    )
    sv = opm.state_vector
    return StateVector(
        metadata=metadata,
        source_native=opm,
        epoch=sv.epoch,
        position=np.array([sv.x, sv.y, sv.z], dtype=np.float64),
        velocity=np.array([sv.x_dot, sv.y_dot, sv.z_dot], dtype=np.float64),
        keplerian=_canonical_keplerian(opm.keplerian),
    )


def _canonical_keplerian(keplerian: OpmKeplerianElements | None) -> KeplerianElements | None:
    """The canonical Keplerian view of the OPM block, or ``None``.

    Populated only when the block states a ``TRUE_ANOMALY`` — the canonical
    :class:`~orbit_formats.canonical.state.KeplerianElements` carries a true-anomaly
    representation, so a mean-anomaly-only OPM leaves it unset (the full block is still on
    ``source_native``). GM is OPM-specific bookkeeping and stays on the fidelity model.
    """
    if keplerian is None or keplerian.true_anomaly is None:
        return None
    return KeplerianElements(
        semi_major_axis=keplerian.semi_major_axis,
        eccentricity=keplerian.eccentricity,
        inclination=keplerian.inclination,
        raan=keplerian.ra_of_asc_node,
        arg_periapsis=keplerian.arg_of_pericenter,
        true_anomaly=keplerian.true_anomaly,
    )


register_reader("ccsds-opm", read_opm)
