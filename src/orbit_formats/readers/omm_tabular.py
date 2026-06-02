"""OMM in the Celestrak / Space-Track JSON and CSV encodings — the flat forms operators
actually consume — into the canonical :class:`~orbit_formats.canonical.elements.MeanElementSet`.

These are not a new format: they are alternative *encodings* of the CCSDS OMM, so each record
parses into the very same :class:`~orbit_formats.readers.ccsds_omm.OmmFile` fidelity model the
KVN / XML reader builds, and adapts through the same OMM ↔ canonical map
(:func:`~orbit_formats.readers.ccsds_omm._to_mean_elements`). The keys are the CCSDS OMM
keywords — ``OBJECT_NAME``, ``EPOCH``, ``MEAN_MOTION``, ``ECCENTRICITY``, ``INCLINATION``,
``RA_OF_ASC_NODE``, ``ARG_OF_PERICENTER``, ``MEAN_ANOMALY``, the ``EPHEMERIS_TYPE`` /
``CLASSIFICATION_TYPE`` / ``NORAD_CAT_ID`` / ``ELEMENT_SET_NO`` / ``REV_AT_EPOCH`` TLE
bookkeeping, and ``BSTAR`` / ``MEAN_MOTION_DOT`` / ``MEAN_MOTION_DDOT`` — so the routing reuses
the KVN scanner's keyword→block map verbatim.

The encoding records the SGP4 / TEME mean set TLEs carry, so the metadata fields a flat OMM
conventionally omits are *implied*: ``REF_FRAME`` TEME, ``TIME_SYSTEM`` UTC,
``MEAN_ELEMENT_THEORY`` SGP4, ``CENTER_NAME`` EARTH, ``CCSDS_OMM_VERS`` 2.0. They are honoured
when a file (Space-Track's fuller OMM) states them and defaulted when it (Celestrak's GP query)
does not. Columns the OMM never defines are ignored, so a Space-Track *GP* record carrying extra
catalogue columns still parses.

A file is a **catalogue**: a JSON object *or* array, and a CSV header row plus one or more data
rows. The public :func:`~orbit_formats.read` returns the *first* record's canonical object, with
the whole :class:`OmmCatalog` riding on ``source_native``; :meth:`OmmCatalog.to_canonical`
materialises every record's :class:`MeanElementSet` in file order. Raises
:class:`~orbit_formats.errors.MalformedSourceError` for malformed JSON / CSV, a record that is
not an object, an empty catalogue, or a record missing the required mean elements.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import ClassVar, Literal

from orbit_formats.canonical.elements import MeanElementSet
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.ccsds_omm import (
    OmmFile,
    OmmMetadata,
    _build_covariance,
    _build_mean_elements,
    _build_spacecraft_parameters,
    _build_tle_parameters,
    _OmmKvnParser,
    _to_mean_elements,
)
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["OmmCatalog", "read_omm_csv", "read_omm_json"]

# The metadata an SGP4 / TEME flat OMM conventionally omits, with the values it implies — the
# same defaults the writer treats as "holdable", so a TEME / UTC / SGP4 set round-trips without
# a warning while a non-default value is flagged as something the encoding cannot carry.
DEFAULT_CCSDS_VERSION = "2.0"
DEFAULT_CENTER_NAME = "EARTH"
DEFAULT_REF_FRAME = "TEME"
DEFAULT_TIME_SYSTEM = "UTC"
DEFAULT_MEAN_ELEMENT_THEORY = "SGP4"
# The placeholder for the object identity an OMM requires but a sparse record might omit.
_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, eq=False)
class OmmCatalog(FidelityModel):
    """A parsed OMM JSON / CSV catalogue — the per-record :class:`OmmFile` models, in order.

    ``serialization`` is the notation the catalogue was read from (``"json"`` or ``"csv"``);
    it distinguishes the two encodings the one model serves, the way ``OmmFile.serialization``
    distinguishes KVN from XML. ``raw_bytes`` is the verbatim source, kept only when the read
    opted in via ``retain_source=True`` so a same-encoding write can echo it byte-for-byte.

    :meth:`to_canonical` adapts every record to a :class:`MeanElementSet`, each carrying its own
    :class:`OmmFile` as ``source_native`` so an individual record round-trips on its own.
    """

    format_name: ClassVar[str] = "omm-json"  # nominal; ``serialization`` carries json vs csv

    records: tuple[OmmFile, ...]
    serialization: Literal["json", "csv"]
    raw_bytes: bytes | None = None

    def to_canonical(self) -> list[MeanElementSet]:
        """Every record's canonical :class:`MeanElementSet`, in file order."""
        source_format = f"omm-{self.serialization}"
        return [
            _to_mean_elements(record, source_format=source_format, source_native=record)
            for record in self.records
        ]


def read_omm_json(source: Source) -> MeanElementSet:
    """Read an OMM JSON catalogue into the first record's canonical :class:`MeanElementSet`.

    Accepts a single JSON object or an array of them; the full sequence is available via
    ``result.source_native.to_canonical()``. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for malformed JSON, a top level that is
    not an object/array, a record that is not an object, an empty catalogue, or a record missing
    the required mean elements.
    """
    catalog = _parse_json(source.read_text())
    if source.retain:
        catalog = replace(catalog, raw_bytes=source.read_bytes())
    return _first_canonical(catalog)


def read_omm_csv(source: Source) -> MeanElementSet:
    """Read an OMM CSV catalogue into the first record's canonical :class:`MeanElementSet`.

    The first non-empty line is the header of CCSDS OMM column names; each subsequent row is a
    record (blank cells are treated as absent). The full sequence is available via
    ``result.source_native.to_canonical()``. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing header, an empty
    catalogue, or a record missing the required mean elements.
    """
    catalog = _parse_csv(source.read_text())
    if source.retain:
        catalog = replace(catalog, raw_bytes=source.read_bytes())
    return _first_canonical(catalog)


def _first_canonical(catalog: OmmCatalog) -> MeanElementSet:
    if not catalog.records:
        raise MalformedSourceError(
            f"the OMM {catalog.serialization.upper()} catalogue has no records"
        )
    return _to_mean_elements(
        catalog.records[0],
        source_format=f"omm-{catalog.serialization}",
        source_native=catalog,
    )


def _parse_json(text: str) -> OmmCatalog:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MalformedSourceError(f"the OMM JSON is not valid JSON: {exc}") from exc
    if isinstance(payload, dict):
        rows: list[object] = [payload]
    elif isinstance(payload, list):
        rows = payload
    else:
        raise MalformedSourceError(
            f"an OMM JSON must be an object or an array of objects, got a {type(payload).__name__}"
        )
    records: list[OmmFile] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise MalformedSourceError(
                f"OMM JSON record {index} is a {type(row).__name__}, not an object"
            )
        fields = {str(key): _stringify(value) for key, value in row.items()}
        records.append(_ommfile_from_flat(fields))
    return OmmCatalog(records=tuple(records), serialization="json")


def _parse_csv(text: str) -> OmmCatalog:
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise MalformedSourceError("the OMM CSV is empty; expected a header row")
    header = [cell.strip() for cell in rows[0]]
    records: list[OmmFile] = []
    for row in rows[1:]:
        fields = {
            header[i]: cell.strip()
            for i, cell in enumerate(row)
            if i < len(header) and cell.strip()
        }
        records.append(_ommfile_from_flat(fields))
    return OmmCatalog(records=tuple(records), serialization="csv")


def _stringify(value: object) -> str | None:
    """Render a JSON value as the string the keyword scanner expects, or ``None`` for null."""
    if value is None:
        return None
    if isinstance(value, bool):  # guard: bool is an int subclass, never an OMM value
        return str(value)
    return str(value)


def _ommfile_from_flat(fields: Mapping[str, str | None]) -> OmmFile:
    """Build an :class:`OmmFile` from a flat ``keyword -> value`` record, reusing the KVN map.

    Routes each recognised CCSDS OMM keyword to its block with the shared keyword scanner, fills
    the SGP4 / TEME metadata a flat OMM implies when absent, and defers to the KVN block builders
    so the mean-element validation and the TLE / spacecraft / covariance assembly are identical to
    the CCSDS OMM reader. Unrecognised keys are ignored — a Space-Track GP record may carry
    catalogue columns the OMM never defines.
    """
    header: dict[str, str] = {}
    meta: dict[str, str] = {}
    elements: dict[str, str] = {}
    tle: dict[str, str] = {}
    spacecraft: dict[str, str] = {}
    cov_frame: dict[str, str] = {}
    cov_values: dict[str, float] = {}
    user_defined: list[tuple[str, str]] = []
    for raw_key, value in fields.items():
        if value is None:
            continue
        key = raw_key.strip().upper()
        if _OmmKvnParser._block_of(key) is None:
            continue
        _OmmKvnParser._route(
            key, value, header, meta, elements, tle, spacecraft, cov_frame, cov_values, user_defined
        )

    metadata = OmmMetadata(
        object_name=meta.get("OBJECT_NAME", _UNKNOWN),
        object_id=meta.get("OBJECT_ID", _UNKNOWN),
        center_name=meta.get("CENTER_NAME", DEFAULT_CENTER_NAME),
        ref_frame=meta.get("REF_FRAME", DEFAULT_REF_FRAME),
        time_system=meta.get("TIME_SYSTEM", DEFAULT_TIME_SYSTEM),
        mean_element_theory=meta.get("MEAN_ELEMENT_THEORY", DEFAULT_MEAN_ELEMENT_THEORY),
        ref_frame_epoch=meta.get("REF_FRAME_EPOCH"),
    )
    return OmmFile(
        ccsds_version=header.get("CCSDS_OMM_VERS", DEFAULT_CCSDS_VERSION),
        metadata=metadata,
        mean_elements=_build_mean_elements(elements, ()),
        creation_date=header.get("CREATION_DATE"),
        originator=header.get("ORIGINATOR"),
        tle_parameters=_build_tle_parameters(tle, ()),
        spacecraft_parameters=_build_spacecraft_parameters(spacecraft, ()),
        covariance=_build_covariance(cov_frame, cov_values, ()),
        user_defined=tuple(user_defined),
        serialization="kvn",  # the per-record model's notation is irrelevant to the catalogue
    )


register_reader("omm-json", read_omm_json)
register_reader("omm-csv", read_omm_csv)
