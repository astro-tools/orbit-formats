"""CCSDS OMM writer — KVN and XML serialisers for the Orbit Mean-elements Message.

Three tiers, picked automatically (as for the OEM writer):

1. A ``MeanElementSet`` whose ``source_native`` is an
   :class:`~orbit_formats.readers.ccsds_omm.OmmFile` with retained bytes → the verbatim bytes
   are echoed (**byte-identical**).
2. An ``OmmFile`` ``source_native`` without retained bytes → the structured model is
   re-serialised (**content-lossless**).
3. Any other ``MeanElementSet`` → an OMM is built from the canonical mean elements, warning
   for each OMM-required field the source cannot supply. When the source came from a TLE
   (``source_native`` is a :class:`~orbit_formats.readers.tle.TleRecord`), the OMM is enriched
   with the TLE's identifiers and drag terms — the TLE → OMM conversion.

The notation is chosen from the destination extension (``.omm`` → KVN, ``.xml`` → XML), else
the source's own notation, else KVN. The XML half lives in
:mod:`orbit_formats.adapters.omm_xml`, imported lazily.
"""

from __future__ import annotations

from typing import Literal

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.elements import MeanElementSet
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_omm import (
    _COVARIANCE_KEYS,
    OmmCovariance,
    OmmFile,
    OmmMeanElements,
    OmmMetadata,
    OmmSpacecraftParameters,
    OmmTleParameters,
)
from orbit_formats.readers.tle import TleRecord
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _comment_lines, _format_epoch, _format_float

__all__ = ["write_omm"]

# The OMM version the synthesised / re-serialised KVN header declares, and the placeholder a
# synthesised OMM uses where the canonical form cannot supply a required value.
_OMM_VERSION = "2.0"
_PLACEHOLDER = "UNKNOWN"
# The mean-element theory a synthesised OMM declares when the source is (or looks like) an
# SGP4 mean set — a TLE, or a mean set carrying SGP4 drag terms.
_SGP4_THEORY = "SGP4"

_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".omm", ".kvn")


def write_omm(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`MeanElementSet`) to CCSDS OMM bytes, in KVN or XML.

    Picks the byte-identical / content-lossless / synthesised path automatically, and the KVN
    or XML notation from ``suffix`` (the destination extension) else the source's own notation
    else KVN. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is
    not a ``MeanElementSet`` — OMM is a mean-element format.
    """
    if not isinstance(obj, MeanElementSet):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-omm", "mean-elements")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, OmmFile):
        notation = requested or native.serialization
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_ommfile(native, notation)
    return _serialize_ommfile(_ommfile_from_mean_elements(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_ommfile(omm: OmmFile, notation: Literal["kvn", "xml"]) -> bytes:
    if notation == "xml":
        from orbit_formats.adapters.omm_xml import xml_bytes_from_ommfile

        return xml_bytes_from_ommfile(omm)
    return _serialize_omm_kvn(omm)


# --- synthesised OMM from a canonical mean set (incl. the TLE -> OMM map) ---------------


def _ommfile_from_mean_elements(meanset: MeanElementSet) -> OmmFile:
    """Build an :class:`OmmFile` from a canonical ``MeanElementSet``, warning on missing fields.

    When the source came from a TLE, the OMM ``OBJECT_ID`` is the international designator and
    the TLE-parameters block is populated from the TLE's identifiers (catalog number,
    classification, element-set and revolution numbers, ephemeris type) — the TLE → OMM map.
    """
    native = meanset.source_native
    tle = native if isinstance(native, TleRecord) else None
    md = meanset.metadata
    object_id = (tle.international_designator if tle is not None else None) or md.object_id
    metadata = OmmMetadata(
        object_name=_required("OBJECT_NAME", md.object_name),
        object_id=_required("OBJECT_ID", object_id),
        center_name=_required("CENTER_NAME", md.central_body),
        ref_frame=_required("REF_FRAME", md.reference_frame),
        time_system=_required("TIME_SYSTEM", md.time_scale),
        mean_element_theory=_resolved_theory(meanset, tle),
    )
    mean_elements = OmmMeanElements(
        epoch=meanset.epoch,
        eccentricity=meanset.eccentricity,
        inclination=meanset.inclination,
        ra_of_asc_node=meanset.raan,
        arg_of_pericenter=meanset.arg_periapsis,
        mean_anomaly=meanset.mean_anomaly,
        mean_motion=meanset.mean_motion,
    )
    return OmmFile(
        ccsds_version=_OMM_VERSION,
        metadata=metadata,
        mean_elements=mean_elements,
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
        tle_parameters=_tle_parameters_from(meanset, tle),
    )


def _required(keyword: str, value: str | None) -> str:
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the mean-element set does not supply the OMM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical mean-element set did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


def _resolved_theory(meanset: MeanElementSet, tle: TleRecord | None) -> str:
    """The mean-element theory: SGP4 for a TLE or a mean set with drag, else warn + placeholder."""
    has_drag = any(
        value is not None
        for value in (meanset.bstar, meanset.mean_motion_dot, meanset.mean_motion_ddot)
    )
    if tle is not None or has_drag:
        return _SGP4_THEORY
    return _required("MEAN_ELEMENT_THEORY", None)


def _tle_parameters_from(meanset: MeanElementSet, tle: TleRecord | None) -> OmmTleParameters | None:
    has_drag = any(
        value is not None
        for value in (meanset.bstar, meanset.mean_motion_dot, meanset.mean_motion_ddot)
    )
    if tle is None and not has_drag:
        return None
    mean_motion_dot = meanset.mean_motion_dot
    if mean_motion_dot is None:
        warn_lossy(
            LossyConversionWarning(
                "the mean-element set does not supply the OMM-required MEAN_MOTION_DOT; wrote 0.0",
                dropped=(
                    DroppedField(
                        "MEAN_MOTION_DOT", "the canonical mean-element set did not carry it"
                    ),
                ),
            ),
            stacklevel=4,
        )
        mean_motion_dot = 0.0
    return OmmTleParameters(
        mean_motion_dot=mean_motion_dot,
        ephemeris_type=None if tle is None else tle.ephemeris_type,
        classification_type=None if tle is None else tle.classification,
        norad_cat_id=None if tle is None else tle.norad_catalog_number,
        element_set_no=None if tle is None else tle.element_set_number,
        rev_at_epoch=None if tle is None else tle.revolution_number_at_epoch,
        bstar=meanset.bstar,
        mean_motion_ddot=meanset.mean_motion_ddot,
    )


# --- KVN serialisation -----------------------------------------------------------------


def _serialize_omm_kvn(omm: OmmFile) -> bytes:
    """Serialise an :class:`OmmFile` to canonical OMM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_OMM_VERS = {omm.ccsds_version}"]
    lines.extend(_comment_lines(omm.comments))
    if omm.creation_date is not None:
        lines.append(f"CREATION_DATE = {omm.creation_date}")
    if omm.originator is not None:
        lines.append(f"ORIGINATOR = {omm.originator}")

    lines.extend(_comment_lines(omm.metadata.comments))
    lines.extend(_serialize_metadata(omm.metadata))

    lines.extend(_comment_lines(omm.mean_elements.comments))
    lines.extend(_serialize_mean_elements(omm.mean_elements))

    if omm.tle_parameters is not None:
        lines.extend(_comment_lines(omm.tle_parameters.comments))
        lines.extend(_serialize_tle_parameters(omm.tle_parameters))

    if omm.spacecraft_parameters is not None:
        lines.extend(_comment_lines(omm.spacecraft_parameters.comments))
        lines.extend(_serialize_spacecraft(omm.spacecraft_parameters))

    if omm.covariance is not None:
        lines.extend(_comment_lines(omm.covariance.comments))
        lines.extend(_serialize_covariance(omm.covariance))

    if omm.user_defined or omm.user_defined_comments:
        lines.extend(_comment_lines(omm.user_defined_comments))
        lines.extend(f"USER_DEFINED_{key} = {value}" for key, value in omm.user_defined)

    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_metadata(meta: OmmMetadata) -> list[str]:
    ordered: tuple[tuple[str, str | None], ...] = (
        ("OBJECT_NAME", meta.object_name),
        ("OBJECT_ID", meta.object_id),
        ("CENTER_NAME", meta.center_name),
        ("REF_FRAME", meta.ref_frame),
        ("REF_FRAME_EPOCH", meta.ref_frame_epoch),
        ("TIME_SYSTEM", meta.time_system),
        ("MEAN_ELEMENT_THEORY", meta.mean_element_theory),
    )
    return [f"{key} = {value}" for key, value in ordered if value is not None]


def _serialize_mean_elements(elements: OmmMeanElements) -> list[str]:
    ordered: tuple[tuple[str, float | None], ...] = (
        ("SEMI_MAJOR_AXIS", elements.semi_major_axis),
        ("MEAN_MOTION", elements.mean_motion),
        ("ECCENTRICITY", elements.eccentricity),
        ("INCLINATION", elements.inclination),
        ("RA_OF_ASC_NODE", elements.ra_of_asc_node),
        ("ARG_OF_PERICENTER", elements.arg_of_pericenter),
        ("MEAN_ANOMALY", elements.mean_anomaly),
        ("GM", elements.gm),
    )
    out = [f"EPOCH = {_format_epoch(elements.epoch)}"]
    out.extend(f"{key} = {_format_float(value)}" for key, value in ordered if value is not None)
    return out


def _serialize_tle_parameters(tle: OmmTleParameters) -> list[str]:
    out: list[str] = []
    for key, value in (
        ("EPHEMERIS_TYPE", tle.ephemeris_type),
        ("CLASSIFICATION_TYPE", tle.classification_type),
        ("NORAD_CAT_ID", tle.norad_cat_id),
        ("ELEMENT_SET_NO", tle.element_set_no),
        ("REV_AT_EPOCH", tle.rev_at_epoch),
    ):
        if value is not None:
            out.append(f"{key} = {value}")
    if tle.bstar is not None:
        out.append(f"BSTAR = {_format_float(tle.bstar)}")
    if tle.bterm is not None:
        out.append(f"BTERM = {_format_float(tle.bterm)}")
    out.append(f"MEAN_MOTION_DOT = {_format_float(tle.mean_motion_dot)}")
    if tle.mean_motion_ddot is not None:
        out.append(f"MEAN_MOTION_DDOT = {_format_float(tle.mean_motion_ddot)}")
    if tle.agom is not None:
        out.append(f"AGOM = {_format_float(tle.agom)}")
    return out


def _serialize_spacecraft(spacecraft: OmmSpacecraftParameters) -> list[str]:
    ordered: tuple[tuple[str, float | None], ...] = (
        ("MASS", spacecraft.mass),
        ("SOLAR_RAD_AREA", spacecraft.solar_rad_area),
        ("SOLAR_RAD_COEFF", spacecraft.solar_rad_coeff),
        ("DRAG_AREA", spacecraft.drag_area),
        ("DRAG_COEFF", spacecraft.drag_coeff),
    )
    return [f"{key} = {_format_float(value)}" for key, value in ordered if value is not None]


def _serialize_covariance(covariance: OmmCovariance) -> list[str]:
    out: list[str] = []
    if covariance.cov_ref_frame is not None:
        out.append(f"COV_REF_FRAME = {covariance.cov_ref_frame}")
    out.extend(
        f"{key} = {_format_float(value)}"
        for key, value in zip(_COVARIANCE_KEYS, covariance.matrix, strict=True)
    )
    return out


register_writer("ccsds-omm", write_omm)
