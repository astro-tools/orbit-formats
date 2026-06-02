"""OMM writers for the Celestrak / Space-Track JSON and CSV encodings.

Both serialise a canonical :class:`~orbit_formats.canonical.elements.MeanElementSet` to the flat
operational OMM field set — the columns Celestrak's GP query and Space-Track's OMM share — in one
of two notations. Three tiers, picked automatically (as for the CCSDS OMM writer):

1. A ``MeanElementSet`` whose ``source_native`` is an
   :class:`~orbit_formats.readers.omm_tabular.OmmCatalog` with retained bytes → the verbatim bytes
   are echoed when the notation matches (**byte-identical**); otherwise its records are
   re-serialised (**content-lossless**), so reading a catalogue and writing it back reproduces the
   whole catalogue.
2. A ``MeanElementSet`` whose ``source_native`` is a single
   :class:`~orbit_formats.readers.ccsds_omm.OmmFile` → that one record is re-serialised.
3. Any other ``MeanElementSet`` → an :class:`OmmFile` is synthesised from the canonical mean
   elements (reusing the CCSDS OMM writer's builder, so a TLE source is enriched with its
   identifiers and drag terms — the TLE → OMM map), then serialised as one record.

The encoding records an SGP4 / TEME mean set, so ``REF_FRAME`` / ``TIME_SYSTEM`` /
``MEAN_ELEMENT_THEORY`` / ``CENTER_NAME`` / ``CCSDS_OMM_VERS`` are *implied* (TEME / UTC / SGP4 /
EARTH / 2.0) and not written; a non-default value, the creation-date / originator header, comments,
covariance, spacecraft parameters, user-defined keys, or the Keplerian ``SEMI_MAJOR_AXIS`` / ``GM``
the flat columns cannot hold are each named in a :class:`LossyConversionWarning` rather than dropped
silently.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Literal

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.elements import MeanElementSet, ensure_convertible_to_mean_format
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_omm import OmmFile, _mean_motion
from orbit_formats.readers.omm_tabular import (
    DEFAULT_CCSDS_VERSION,
    DEFAULT_CENTER_NAME,
    DEFAULT_MEAN_ELEMENT_THEORY,
    DEFAULT_REF_FRAME,
    DEFAULT_TIME_SYSTEM,
    OmmCatalog,
)
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.oem import _format_epoch, _format_float
from orbit_formats.writers.omm import _ommfile_from_mean_elements

__all__ = ["write_omm_csv", "write_omm_json"]

# The flat OMM columns this encoding carries, the fixed CSV header in Celestrak / Space-Track
# order. JSON emits only the columns a record holds; CSV emits them all, blank where absent.
_COLUMNS: tuple[str, ...] = (
    "OBJECT_NAME",
    "OBJECT_ID",
    "EPOCH",
    "MEAN_MOTION",
    "ECCENTRICITY",
    "INCLINATION",
    "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER",
    "MEAN_ANOMALY",
    "EPHEMERIS_TYPE",
    "CLASSIFICATION_TYPE",
    "NORAD_CAT_ID",
    "ELEMENT_SET_NO",
    "REV_AT_EPOCH",
    "BSTAR",
    "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
)


def write_omm_json(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`MeanElementSet`) to an OMM JSON array of records."""
    return _write(obj, "json")


def write_omm_csv(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`MeanElementSet`) to an OMM CSV table (header + one row each)."""
    return _write(obj, "csv")


def _write(obj: Canonical, notation: Literal["json", "csv"]) -> bytes:
    format_id = f"omm-{notation}"
    if not isinstance(obj, MeanElementSet):
        raise UnsupportedConversionError(type(obj).__name__, format_id, "mean-elements")
    ensure_convertible_to_mean_format(obj, format_id)
    native = obj.source_native
    if isinstance(native, OmmCatalog):
        if native.raw_bytes is not None and native.serialization == notation:
            return native.raw_bytes
        records = list(native.records)
    elif isinstance(native, OmmFile):
        records = [native]
    else:
        records = [_ommfile_from_mean_elements(obj)]
    rows = [_record_fields(record) for record in records]
    return _serialize_json(rows) if notation == "json" else _serialize_csv(rows)


def _record_fields(omm: OmmFile) -> dict[str, object]:
    """Project an :class:`OmmFile` onto the flat OMM columns, warning on what it cannot hold."""
    _warn_unholdable(omm)
    elements = omm.mean_elements
    fields: dict[str, object] = {
        "OBJECT_NAME": omm.metadata.object_name,
        "OBJECT_ID": omm.metadata.object_id,
        "EPOCH": _format_epoch(elements.epoch),
        "MEAN_MOTION": _mean_motion(elements),
        "ECCENTRICITY": elements.eccentricity,
        "INCLINATION": elements.inclination,
        "RA_OF_ASC_NODE": elements.ra_of_asc_node,
        "ARG_OF_PERICENTER": elements.arg_of_pericenter,
        "MEAN_ANOMALY": elements.mean_anomaly,
    }
    tle = omm.tle_parameters
    if tle is not None:
        _put(fields, "EPHEMERIS_TYPE", tle.ephemeris_type)
        _put(fields, "CLASSIFICATION_TYPE", tle.classification_type)
        _put(fields, "NORAD_CAT_ID", tle.norad_cat_id)
        _put(fields, "ELEMENT_SET_NO", tle.element_set_no)
        _put(fields, "REV_AT_EPOCH", tle.rev_at_epoch)
        _put(fields, "BSTAR", tle.bstar)
        fields["MEAN_MOTION_DOT"] = tle.mean_motion_dot  # mandatory whenever the block exists
        _put(fields, "MEAN_MOTION_DDOT", tle.mean_motion_ddot)
    return fields


def _put(fields: dict[str, object], key: str, value: object) -> None:
    if value is not None:
        fields[key] = value


def _warn_unholdable(omm: OmmFile) -> None:
    """Warn, once per record, for any OMM content the flat operational columns cannot carry."""
    dropped: list[DroppedField] = []
    if omm.creation_date is not None:
        dropped.append(DroppedField("CREATION_DATE", "the flat OMM encoding has no header"))
    if omm.originator is not None:
        dropped.append(DroppedField("ORIGINATOR", "the flat OMM encoding has no header"))
    for keyword, value, default in (
        ("CCSDS_OMM_VERS", omm.ccsds_version, DEFAULT_CCSDS_VERSION),
        ("CENTER_NAME", omm.metadata.center_name, DEFAULT_CENTER_NAME),
        ("REF_FRAME", omm.metadata.ref_frame, DEFAULT_REF_FRAME),
        ("TIME_SYSTEM", omm.metadata.time_system, DEFAULT_TIME_SYSTEM),
        ("MEAN_ELEMENT_THEORY", omm.metadata.mean_element_theory, DEFAULT_MEAN_ELEMENT_THEORY),
    ):
        if value.upper() != default:
            dropped.append(
                DroppedField(keyword, f"the flat OMM encoding implies {default!r}, got {value!r}")
            )
    if omm.metadata.ref_frame_epoch is not None:
        dropped.append(DroppedField("REF_FRAME_EPOCH", "no column for a reference-frame epoch"))
    if omm.mean_elements.semi_major_axis is not None:
        dropped.append(
            DroppedField("SEMI_MAJOR_AXIS", "the encoding records MEAN_MOTION, not the SMA")
        )
    if omm.mean_elements.gm is not None:
        dropped.append(DroppedField("GM", "no column for the gravitational parameter"))
    if omm.tle_parameters is not None:
        if omm.tle_parameters.bterm is not None:
            dropped.append(DroppedField("BTERM", "no column for the ballistic B-term"))
        if omm.tle_parameters.agom is not None:
            dropped.append(DroppedField("AGOM", "no column for the SRP A-gamma-over-m term"))
    if omm.spacecraft_parameters is not None:
        dropped.append(
            DroppedField("SPACECRAFT_PARAMETERS", "no columns for spacecraft parameters")
        )
    if omm.covariance is not None:
        dropped.append(DroppedField("COVARIANCE", "no columns for the covariance matrix"))
    if omm.user_defined:
        dropped.append(DroppedField("USER_DEFINED", "no columns for user-defined keys"))
    if _has_comments(omm):
        dropped.append(DroppedField("COMMENT", "the flat OMM encoding has no comment column"))
    if dropped:
        warn_lossy(
            LossyConversionWarning(
                "the OMM JSON / CSV encoding holds only the flat operational fields; "
                f"{len(dropped)} field(s) the source carried could not be written",
                dropped=tuple(dropped),
            ),
            stacklevel=4,
        )


def _has_comments(omm: OmmFile) -> bool:
    blocks = (
        omm.comments,
        omm.metadata.comments,
        omm.mean_elements.comments,
        omm.user_defined_comments,
    )
    if any(blocks):
        return True
    if omm.tle_parameters is not None and omm.tle_parameters.comments:
        return True
    if omm.spacecraft_parameters is not None and omm.spacecraft_parameters.comments:
        return True
    return omm.covariance is not None and bool(omm.covariance.comments)


def _serialize_json(rows: list[dict[str, object]]) -> bytes:
    """Serialise the records as a JSON array, omitting columns a record does not carry."""
    return (json.dumps(rows, indent=2) + "\n").encode("utf-8")


def _serialize_csv(rows: list[dict[str, object]]) -> bytes:
    """Serialise the records as a CSV table with the fixed operational header (LF-terminated)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_COLUMNS)
    for row in rows:
        writer.writerow([_csv_cell(row.get(column)) for column in _COLUMNS])
    return buffer.getvalue().encode("utf-8")


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int)):
        return str(value)
    return _format_float(float(value))  # type: ignore[arg-type]


register_writer("omm-json", write_omm_json)
register_writer("omm-csv", write_omm_csv)
