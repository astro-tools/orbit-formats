"""CCSDS OMM reader — in-house parsing of the Orbit Mean-elements Message into a fidelity model.

The KVN reader is hand-written; the XML form is parsed through orbit-formats' own MIT xsdata
bindings (see :mod:`orbit_formats.adapters.omm_xml`). No GPL dependency is ever imported at
runtime. Both notations parse into the *same* faithful :class:`OmmFile` fidelity model —
every field the OMM defines, across the header, metadata, mean-elements, and the optional
TLE / spacecraft / covariance / user-defined blocks — which is then adapted into a canonical
:class:`~orbit_formats.canonical.elements.MeanElementSet`. The notation a file was read from
is recorded on the model (``serialization``) so a write re-emits in the same notation by
default. :func:`read_omm` dispatches on content: an XML document routes to the XML parser,
everything else to the hand-written KVN scanner.

An OMM KVN message is a flat sequence of ``KEYWORD = value`` lines (no ``META_START`` blocks);
each keyword is routed to its block by name, and ``COMMENT`` lines lead the block that
follows them. Covariance is the 21 keyword lines ``CX_X = …`` (the lower triangle of the
symmetric 6x6), optionally preceded by ``COV_REF_FRAME``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar, Literal

import numpy as np

from orbit_formats.canonical.elements import MeanElementSet
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds import (
    _KEYWORD_RE,
    _canonical_time_scale,
    _comment_text,
    _is_comment,
    _parse_epoch,
)
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = [
    "OmmCovariance",
    "OmmFile",
    "OmmMeanElements",
    "OmmMetadata",
    "OmmSpacecraftParameters",
    "OmmTleParameters",
    "read_omm",
]

# Standard gravitational parameter (km^3/s^2) used only when an OMM gives SEMI_MAJOR_AXIS
# but no MEAN_MOTION and no GM — the canonical mean set is keyed on mean motion.
_EARTH_GM = 398600.4418

# The 21 lower-triangular covariance keywords, in row order — the same layout the canonical
# matrix tuple uses, so element i of the tuple is keyword i here.
_COVARIANCE_KEYS = (
    "CX_X",
    "CY_X",
    "CY_Y",
    "CZ_X",
    "CZ_Y",
    "CZ_Z",
    "CX_DOT_X",
    "CX_DOT_Y",
    "CX_DOT_Z",
    "CX_DOT_X_DOT",
    "CY_DOT_X",
    "CY_DOT_Y",
    "CY_DOT_Z",
    "CY_DOT_X_DOT",
    "CY_DOT_Y_DOT",
    "CZ_DOT_X",
    "CZ_DOT_Y",
    "CZ_DOT_Z",
    "CZ_DOT_X_DOT",
    "CZ_DOT_Y_DOT",
    "CZ_DOT_Z_DOT",
)

# Keyword → block routing for the flat KVN scanner. A keyword's block tells the scanner
# which block any pending COMMENT lines lead, and where the value belongs.
_HEADER_KEYS = frozenset({"CCSDS_OMM_VERS", "CREATION_DATE", "ORIGINATOR", "MESSAGE_ID"})
_META_KEYS = frozenset(
    {
        "OBJECT_NAME",
        "OBJECT_ID",
        "CENTER_NAME",
        "REF_FRAME",
        "REF_FRAME_EPOCH",
        "TIME_SYSTEM",
        "MEAN_ELEMENT_THEORY",
    }
)
_MEAN_ELEMENT_KEYS = frozenset(
    {
        "EPOCH",
        "SEMI_MAJOR_AXIS",
        "MEAN_MOTION",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "MEAN_ANOMALY",
        "GM",
    }
)
_TLE_KEYS = frozenset(
    {
        "EPHEMERIS_TYPE",
        "CLASSIFICATION_TYPE",
        "NORAD_CAT_ID",
        "ELEMENT_SET_NO",
        "REV_AT_EPOCH",
        "BSTAR",
        "BTERM",
        "MEAN_MOTION_DOT",
        "MEAN_MOTION_DDOT",
        "AGOM",
    }
)
_SPACECRAFT_KEYS = frozenset(
    {"MASS", "SOLAR_RAD_AREA", "SOLAR_RAD_COEFF", "DRAG_AREA", "DRAG_COEFF"}
)
_COVARIANCE_FRAME_KEYS = frozenset({"COV_REF_FRAME", *_COVARIANCE_KEYS})


@dataclass(frozen=True, slots=True)
class OmmMetadata:
    """The OMM metadata block — the object, frame, time system, and mean-element theory."""

    object_name: str
    object_id: str
    center_name: str
    ref_frame: str
    time_system: str
    mean_element_theory: str
    ref_frame_epoch: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OmmMeanElements:
    """The OMM mean-element set — the six Keplerian mean elements plus the SGP4 mean motion.

    ``mean_motion`` (rev/day) is present for an SGP4/TLE-theory OMM; ``semi_major_axis`` (km)
    appears instead for a Keplerian-theory one. Angles are degrees. ``gm`` (km^3/s^2) is
    carried when the file states it.
    """

    epoch: np.datetime64
    eccentricity: float
    inclination: float
    ra_of_asc_node: float
    arg_of_pericenter: float
    mean_anomaly: float
    mean_motion: float | None = None
    semi_major_axis: float | None = None
    gm: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OmmTleParameters:
    """The optional OMM TLE-parameters block — the SGP4 drag terms and TLE bookkeeping.

    ``mean_motion_dot`` (rev/day^2) is mandatory when the block is present; everything else
    is optional. ``ephemeris_type`` / ``classification_type`` / ``norad_cat_id`` /
    ``element_set_no`` / ``rev_at_epoch`` are the TLE identifiers; ``bstar`` (1/ER) and
    ``mean_motion_ddot`` (rev/day^3) the remaining drag terms.
    """

    mean_motion_dot: float
    ephemeris_type: int | None = None
    classification_type: str | None = None
    norad_cat_id: int | None = None
    element_set_no: int | None = None
    rev_at_epoch: int | None = None
    bstar: float | None = None
    bterm: float | None = None
    mean_motion_ddot: float | None = None
    agom: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OmmSpacecraftParameters:
    """The optional OMM spacecraft-parameters block — mass, drag, and solar-radiation areas."""

    mass: float | None = None
    solar_rad_area: float | None = None
    solar_rad_coeff: float | None = None
    drag_area: float | None = None
    drag_coeff: float | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OmmCovariance:
    """The optional OMM covariance — the 21 lower-triangular elements of the symmetric 6x6.

    ``matrix`` holds the elements in row order (the canonical lower-triangular layout);
    ``cov_ref_frame`` is the frame the matrix is expressed in when the block names one. The
    OMM covariance carries no epoch of its own (it is at the mean-element epoch).
    """

    matrix: tuple[float, ...]
    cov_ref_frame: str | None = None
    comments: tuple[str, ...] = ()


@dataclass(frozen=True, eq=False)
class OmmFile(FidelityModel):
    """The faithful OMM fidelity model: the header plus every block, in file order.

    Holds every field a same-format OMM write reconstructs from. ``raw_bytes`` is the
    verbatim source kept only when the read opted in via ``retain_source=True``;
    ``serialization`` records the notation it was read from (``"kvn"`` or ``"xml"``) so a
    write re-emits in the same notation by default. ``user_defined`` keeps the
    ``USER_DEFINED_<key> = value`` parameters in order.
    """

    format_name: ClassVar[str] = "ccsds-omm"

    ccsds_version: str
    metadata: OmmMetadata
    mean_elements: OmmMeanElements
    creation_date: str | None = None
    originator: str | None = None
    comments: tuple[str, ...] = ()
    tle_parameters: OmmTleParameters | None = None
    spacecraft_parameters: OmmSpacecraftParameters | None = None
    covariance: OmmCovariance | None = None
    user_defined: tuple[tuple[str, str], ...] = ()
    user_defined_comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None
    serialization: Literal["kvn", "xml"] = "kvn"


def read_omm(source: Source) -> MeanElementSet:
    """Read a CCSDS OMM (KVN or XML) into a canonical :class:`MeanElementSet`.

    Parses the header and every block into an :class:`OmmFile` fidelity model, retained as
    ``source_native``, then adapts the mean elements into a canonical mean-element set tagged
    with the frame, central body, time scale, and object id from the OMM. The notation is
    detected from the content. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing required keyword, a
    malformed value or epoch, malformed XML, or a partial covariance matrix.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    text = source.read_text()
    if _looks_like_xml(text):
        from orbit_formats.adapters.omm_xml import ommfile_from_xml

        omm = ommfile_from_xml(source.read_bytes())
    else:
        omm = _OmmKvnParser(text.splitlines()).parse()
    if source.retain:
        omm = replace(omm, raw_bytes=source.read_bytes())
    return _to_mean_elements(omm)


def _looks_like_xml(text: str) -> bool:
    """Whether ``text`` is an OMM in XML rather than KVN — its first content is an XML tag."""
    return text.lstrip("\ufeff \t\r\n").startswith("<")


class _OmmKvnParser:
    """A flat scanner over an OMM's KVN lines, routing each keyword to its block."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def parse(self) -> OmmFile:
        header: dict[str, str] = {}
        meta: dict[str, str] = {}
        elements: dict[str, str] = {}
        tle: dict[str, str] = {}
        spacecraft: dict[str, str] = {}
        cov_frame: dict[str, str] = {}
        cov_values: dict[str, float] = {}
        user_defined: list[tuple[str, str]] = []
        comments: dict[str, list[str]] = {
            block: [] for block in ("header", "meta", "elements", "tle", "sc", "cov", "ud")
        }
        pending: list[str] = []

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
                    f"expected 'KEYWORD = value' in the OMM, got {stripped!r}"
                )
            key = match.group(1).upper()
            value = _strip_units(match.group(2).strip())
            block = self._block_of(key)
            if block is None:
                raise MalformedSourceError(f"unexpected OMM keyword {key!r}")
            comments[block].extend(pending)
            pending.clear()
            self._route(
                key,
                value,
                header,
                meta,
                elements,
                tle,
                spacecraft,
                cov_frame,
                cov_values,
                user_defined,
            )

        return _build_omm(
            header,
            meta,
            elements,
            tle,
            spacecraft,
            cov_frame,
            cov_values,
            tuple(user_defined),
            {block: tuple(value) for block, value in comments.items()},
        )

    @staticmethod
    def _block_of(key: str) -> str | None:
        if key in _HEADER_KEYS:
            return "header"
        if key in _META_KEYS:
            return "meta"
        if key in _MEAN_ELEMENT_KEYS:
            return "elements"
        if key in _TLE_KEYS:
            return "tle"
        if key in _SPACECRAFT_KEYS:
            return "sc"
        if key in _COVARIANCE_FRAME_KEYS:
            return "cov"
        if key.startswith("USER_DEFINED_"):
            return "ud"
        return None

    @staticmethod
    def _route(
        key: str,
        value: str,
        header: dict[str, str],
        meta: dict[str, str],
        elements: dict[str, str],
        tle: dict[str, str],
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
        elif key in _MEAN_ELEMENT_KEYS:
            elements[key] = value
        elif key in _TLE_KEYS:
            tle[key] = value
        else:
            spacecraft[key] = value


def _strip_units(value: str) -> str:
    """Drop a trailing ``[units]`` annotation from a KVN value (``13.8 [rev/day]`` -> ``13.8``)."""
    if value.endswith("]"):
        start = value.rfind("[")
        if start != -1:
            return value[:start].strip()
    return value


def _kvn_float(value: str, keyword: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise MalformedSourceError(f"OMM {keyword} must be a number, got {value!r}") from exc


def _kvn_int(value: str, keyword: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise MalformedSourceError(f"OMM {keyword} must be an integer, got {value!r}") from exc


def _require(values: dict[str, str], key: str, where: str) -> str:
    if key not in values:
        raise MalformedSourceError(f"OMM {where} is missing the required keyword {key!r}")
    return values[key]


def _build_omm(
    header: dict[str, str],
    meta: dict[str, str],
    elements: dict[str, str],
    tle: dict[str, str],
    spacecraft: dict[str, str],
    cov_frame: dict[str, str],
    cov_values: dict[str, float],
    user_defined: tuple[tuple[str, str], ...],
    comments: dict[str, tuple[str, ...]],
) -> OmmFile:
    if "CCSDS_OMM_VERS" not in header:
        raise MalformedSourceError(
            "not a CCSDS OMM: the 'CCSDS_OMM_VERS' header keyword is missing"
        )
    metadata = OmmMetadata(
        object_name=_require(meta, "OBJECT_NAME", "metadata"),
        object_id=_require(meta, "OBJECT_ID", "metadata"),
        center_name=_require(meta, "CENTER_NAME", "metadata"),
        ref_frame=_require(meta, "REF_FRAME", "metadata"),
        time_system=_require(meta, "TIME_SYSTEM", "metadata"),
        mean_element_theory=_require(meta, "MEAN_ELEMENT_THEORY", "metadata"),
        ref_frame_epoch=meta.get("REF_FRAME_EPOCH"),
        comments=comments["meta"],
    )
    mean_elements = _build_mean_elements(elements, comments["elements"])
    return OmmFile(
        ccsds_version=header["CCSDS_OMM_VERS"],
        metadata=metadata,
        mean_elements=mean_elements,
        creation_date=header.get("CREATION_DATE"),
        originator=header.get("ORIGINATOR"),
        comments=comments["header"],
        tle_parameters=_build_tle_parameters(tle, comments["tle"]),
        spacecraft_parameters=_build_spacecraft_parameters(spacecraft, comments["sc"]),
        covariance=_build_covariance(cov_frame, cov_values, comments["cov"]),
        user_defined=user_defined,
        user_defined_comments=comments["ud"],
    )


def _build_mean_elements(
    elements: dict[str, str], block_comments: tuple[str, ...]
) -> OmmMeanElements:
    epoch = _parse_epoch(_require(elements, "EPOCH", "mean elements"))
    mean_motion = elements.get("MEAN_MOTION")
    semi_major_axis = elements.get("SEMI_MAJOR_AXIS")
    if mean_motion is None and semi_major_axis is None:
        raise MalformedSourceError(
            "OMM mean elements need MEAN_MOTION or SEMI_MAJOR_AXIS; neither is present"
        )
    return OmmMeanElements(
        epoch=epoch,
        eccentricity=_kvn_float(
            _require(elements, "ECCENTRICITY", "mean elements"), "ECCENTRICITY"
        ),
        inclination=_kvn_float(_require(elements, "INCLINATION", "mean elements"), "INCLINATION"),
        ra_of_asc_node=_kvn_float(
            _require(elements, "RA_OF_ASC_NODE", "mean elements"), "RA_OF_ASC_NODE"
        ),
        arg_of_pericenter=_kvn_float(
            _require(elements, "ARG_OF_PERICENTER", "mean elements"), "ARG_OF_PERICENTER"
        ),
        mean_anomaly=_kvn_float(
            _require(elements, "MEAN_ANOMALY", "mean elements"), "MEAN_ANOMALY"
        ),
        mean_motion=None if mean_motion is None else _kvn_float(mean_motion, "MEAN_MOTION"),
        semi_major_axis=(
            None if semi_major_axis is None else _kvn_float(semi_major_axis, "SEMI_MAJOR_AXIS")
        ),
        gm=None if "GM" not in elements else _kvn_float(elements["GM"], "GM"),
        comments=block_comments,
    )


def _build_tle_parameters(
    tle: dict[str, str], block_comments: tuple[str, ...]
) -> OmmTleParameters | None:
    if not tle:
        return None
    return OmmTleParameters(
        mean_motion_dot=_kvn_float(
            _require(tle, "MEAN_MOTION_DOT", "TLE parameters"), "MEAN_MOTION_DOT"
        ),
        ephemeris_type=None
        if "EPHEMERIS_TYPE" not in tle
        else _kvn_int(tle["EPHEMERIS_TYPE"], "EPHEMERIS_TYPE"),
        classification_type=tle.get("CLASSIFICATION_TYPE"),
        norad_cat_id=None
        if "NORAD_CAT_ID" not in tle
        else _kvn_int(tle["NORAD_CAT_ID"], "NORAD_CAT_ID"),
        element_set_no=None
        if "ELEMENT_SET_NO" not in tle
        else _kvn_int(tle["ELEMENT_SET_NO"], "ELEMENT_SET_NO"),
        rev_at_epoch=None
        if "REV_AT_EPOCH" not in tle
        else _kvn_int(tle["REV_AT_EPOCH"], "REV_AT_EPOCH"),
        bstar=None if "BSTAR" not in tle else _kvn_float(tle["BSTAR"], "BSTAR"),
        bterm=None if "BTERM" not in tle else _kvn_float(tle["BTERM"], "BTERM"),
        mean_motion_ddot=None
        if "MEAN_MOTION_DDOT" not in tle
        else _kvn_float(tle["MEAN_MOTION_DDOT"], "MEAN_MOTION_DDOT"),
        agom=None if "AGOM" not in tle else _kvn_float(tle["AGOM"], "AGOM"),
        comments=block_comments,
    )


def _build_spacecraft_parameters(
    spacecraft: dict[str, str], block_comments: tuple[str, ...]
) -> OmmSpacecraftParameters | None:
    if not spacecraft:
        return None
    return OmmSpacecraftParameters(
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
) -> OmmCovariance | None:
    if not cov_values and not cov_frame:
        return None
    missing = [key for key in _COVARIANCE_KEYS if key not in cov_values]
    if missing:
        raise MalformedSourceError(f"OMM covariance is incomplete; missing {', '.join(missing)}")
    return OmmCovariance(
        matrix=tuple(cov_values[key] for key in _COVARIANCE_KEYS),
        cov_ref_frame=cov_frame.get("COV_REF_FRAME"),
        comments=block_comments,
    )


def _to_mean_elements(omm: OmmFile) -> MeanElementSet:
    """Adapt an :class:`OmmFile` into the canonical :class:`MeanElementSet`.

    The mean motion comes straight from ``MEAN_MOTION`` for an SGP4/TLE OMM; for a Keplerian
    OMM that states only ``SEMI_MAJOR_AXIS`` it is derived from the semi-major axis and GM
    (the central-body default when GM is absent). The SGP4 drag terms ride along from the
    TLE-parameters block when present. The whole :class:`OmmFile` is retained as
    ``source_native``.
    """
    md = omm.metadata
    metadata = Metadata(
        object_name=md.object_name,
        object_id=md.object_id,
        originator=omm.originator,
        reference_frame=md.ref_frame,
        central_body=md.center_name,
        time_scale=_canonical_time_scale(md.time_system),
        provenance=Provenance(source_format="ccsds-omm", creation_date=omm.creation_date),
    )
    tle = omm.tle_parameters
    return MeanElementSet(
        metadata=metadata,
        source_native=omm,
        epoch=omm.mean_elements.epoch,
        mean_motion=_mean_motion(omm.mean_elements),
        eccentricity=omm.mean_elements.eccentricity,
        inclination=omm.mean_elements.inclination,
        raan=omm.mean_elements.ra_of_asc_node,
        arg_periapsis=omm.mean_elements.arg_of_pericenter,
        mean_anomaly=omm.mean_elements.mean_anomaly,
        bstar=None if tle is None else tle.bstar,
        mean_motion_dot=None if tle is None else tle.mean_motion_dot,
        mean_motion_ddot=None if tle is None else tle.mean_motion_ddot,
        mean_element_theory=md.mean_element_theory,
    )


def _mean_motion(elements: OmmMeanElements) -> float:
    """The mean motion (rev/day): straight from the file, or derived from SMA + GM."""
    if elements.mean_motion is not None:
        return elements.mean_motion
    assert elements.semi_major_axis is not None  # guaranteed by _build_mean_elements
    gm = elements.gm if elements.gm is not None else _EARTH_GM
    mean_motion_rad_s = float(np.sqrt(gm / elements.semi_major_axis**3))
    return mean_motion_rad_s * 86400.0 / (2.0 * np.pi)


register_reader("ccsds-omm", read_omm)
