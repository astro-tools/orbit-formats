"""CCSDS OEM writer — KVN and XML serialisers, generalised from gmat-run's OEM writer.

The writer has three tiers, picked automatically from what the canonical object carries:

1. An ``Ephemeris`` whose ``source_native`` is an :class:`~orbit_formats.readers.ccsds.OemFile`
   **with retained bytes** (the read opted in via ``retain_source=True``) → the verbatim
   bytes are echoed, so the same-format round trip is **byte-identical** by construction.
2. An ``Ephemeris`` with an ``OemFile`` ``source_native`` **without** retained bytes → the
   structured fidelity model is re-serialised: **content-lossless** (every field — accel,
   covariance, the full META, comments — preserved), canonically formatted.
3. Any other ``Ephemeris`` (synthesised or cross-format, no OEM ``source_native``) → an OEM
   is built from the canonical fields, warning (via the lossy-warning framework) for each
   OEM-required field the canonical form cannot supply.

OEM has two notations — KVN and XML — and the writer emits either. The notation is chosen
from the destination extension when :func:`~orbit_formats.write` supplies one (``.xml`` →
XML, ``.oem`` → KVN); failing that, from the source's own notation (so an XML source
round-trips back to XML); failing that, KVN. A byte-identical echo (tier 1) only applies
when the retained bytes are already in the notation being written — a cross-notation write
re-serialises. The XML half lives in :mod:`orbit_formats.adapters.oem_xml`, imported lazily
so a KVN-only write never touches the xsdata bindings.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds import OemCovariance, OemFile, OemSegment, OemSegmentMeta
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy

__all__ = ["write_oem"]

# Destination extensions that pin the OEM notation. Any other extension (or a direct,
# destination-less call) leaves the choice to the source's own notation.
_XML_EXTENSIONS = (".xml",)
_KVN_EXTENSIONS = (".oem", ".kvn")

# The OEM version the synthesised / re-serialised header declares, and the placeholder a
# synthesised file uses where the canonical form cannot supply a required META value.
_OEM_VERSION = "2.0"
_PLACEHOLDER = "UNKNOWN"

# The seven mandatory META keywords, paired with the canonical metadata field each is
# sourced from when synthesising an OEM (START_TIME / STOP_TIME come from the epochs).
_REQUIRED_FROM_METADATA = (
    ("OBJECT_NAME", "object_name"),
    ("OBJECT_ID", "object_id"),
    ("CENTER_NAME", "central_body"),
    ("REF_FRAME", "reference_frame"),
    ("TIME_SYSTEM", "time_scale"),
)


def write_oem(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (an :class:`Ephemeris`) to CCSDS OEM bytes, in KVN or XML.

    Picks the byte-identical, content-lossless, or synthesised path automatically, and the
    KVN or XML notation from ``suffix`` (the destination extension, supplied by
    :func:`~orbit_formats.write`) else the source's own notation else KVN — see the module
    docstring. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is
    not an ``Ephemeris`` — OEM is an ephemeris format, and converting another canonical form
    to it is the conversion layer's job, not the writer's.
    """
    if not isinstance(obj, Ephemeris):
        raise UnsupportedConversionError(type(obj).__name__, "ccsds-oem", "ephemeris")
    requested = _notation_from_suffix(suffix)
    native = obj.source_native
    if isinstance(native, OemFile):
        notation = requested or native.serialization
        # A byte-identical echo is only valid when the retained bytes are already in the
        # notation being written; a cross-notation write must re-serialise the model.
        if native.raw_bytes is not None and notation == native.serialization:
            return native.raw_bytes
        return _serialize_oemfile(native, notation)
    return _serialize_oemfile(_oemfile_from_ephemeris(obj), requested or "kvn")


def _notation_from_suffix(suffix: str | None) -> Literal["kvn", "xml"] | None:
    """The notation a destination extension pins, or ``None`` when it pins neither."""
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _XML_EXTENSIONS:
        return "xml"
    if lowered in _KVN_EXTENSIONS:
        return "kvn"
    return None


def _serialize_oemfile(oem: OemFile, notation: Literal["kvn", "xml"]) -> bytes:
    """Serialise an :class:`OemFile` in the requested notation (content-lossless)."""
    if notation == "xml":
        # Imported lazily so a KVN-only write never pulls in the xsdata binding layer.
        from orbit_formats.adapters.oem_xml import xml_bytes_from_oemfile

        return xml_bytes_from_oemfile(oem)
    return _serialize_oem(oem)


def _oemfile_from_ephemeris(eph: Ephemeris) -> OemFile:
    """Build an :class:`OemFile` from a canonical ``Ephemeris``, warning on missing fields.

    Each OEM-required META field the canonical form cannot supply is written as a
    placeholder and reported through :func:`~orbit_formats.warnings.warn_lossy`, so a
    synthesised OEM is structurally valid yet never silently incomplete.
    """
    md = eph.metadata
    count = len(eph)
    start_time = _format_epoch(eph.epochs[0]) if count else None
    stop_time = _format_epoch(eph.epochs[-1]) if count else None

    resolved: dict[str, str] = {}
    for keyword, attribute in _REQUIRED_FROM_METADATA:
        resolved[keyword] = _resolve_required(keyword, getattr(md, attribute))
    resolved["START_TIME"] = _resolve_required("START_TIME", start_time)
    resolved["STOP_TIME"] = _resolve_required("STOP_TIME", stop_time)

    meta = OemSegmentMeta(
        object_name=resolved["OBJECT_NAME"],
        object_id=resolved["OBJECT_ID"],
        center_name=resolved["CENTER_NAME"],
        ref_frame=resolved["REF_FRAME"],
        time_system=resolved["TIME_SYSTEM"],
        start_time=resolved["START_TIME"],
        stop_time=resolved["STOP_TIME"],
        interpolation=eph.interpolation,
        interpolation_degree=eph.interpolation_degree,
    )
    segment = OemSegment(
        meta=meta, epochs=eph.epochs, positions=eph.positions, velocities=eph.velocities
    )
    return OemFile(
        ccsds_version=_OEM_VERSION,
        segments=(segment,),
        creation_date=md.provenance.creation_date if md.provenance is not None else None,
        originator=md.originator,
    )


def _resolve_required(keyword: str, value: str | None) -> str:
    """Return ``value`` if present, else warn that the OEM-required field is unavailable."""
    if value is not None:
        return value
    warn_lossy(
        LossyConversionWarning(
            f"the ephemeris does not supply the OEM-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, "the canonical ephemeris did not carry it"),),
        ),
        stacklevel=4,
    )
    return _PLACEHOLDER


def _serialize_oem(oem: OemFile) -> bytes:
    """Serialise an :class:`OemFile` to canonical OEM (KVN) bytes (content-lossless)."""
    lines: list[str] = [f"CCSDS_OEM_VERS = {oem.ccsds_version}"]
    if oem.creation_date is not None:
        lines.append(f"CREATION_DATE = {oem.creation_date}")
    if oem.originator is not None:
        lines.append(f"ORIGINATOR = {oem.originator}")
    lines.extend(_comment_lines(oem.comments))
    for segment in oem.segments:
        lines.append("")
        lines.extend(_serialize_segment(segment))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_segment(segment: OemSegment) -> list[str]:
    out: list[str] = ["META_START"]
    out.extend(_comment_lines(segment.meta.comments))
    out.extend(_serialize_meta(segment.meta))
    out.append("META_STOP")
    out.append("")
    out.extend(_comment_lines(segment.comments))
    for index in range(len(segment.epochs)):
        out.append(_serialize_state(segment, index))
    for covariance in segment.covariances:
        out.append("")
        out.extend(_serialize_covariance(covariance))
    return out


def _serialize_meta(meta: OemSegmentMeta) -> list[str]:
    # CCSDS 502.0-B META keyword order; only keywords the segment actually carries are
    # emitted, then any non-standard keywords kept verbatim from the source.
    degree = None if meta.interpolation_degree is None else str(meta.interpolation_degree)
    ordered: tuple[tuple[str, str | None], ...] = (
        ("OBJECT_NAME", meta.object_name),
        ("OBJECT_ID", meta.object_id),
        ("CENTER_NAME", meta.center_name),
        ("REF_FRAME", meta.ref_frame),
        ("REF_FRAME_EPOCH", meta.ref_frame_epoch),
        ("TIME_SYSTEM", meta.time_system),
        ("START_TIME", meta.start_time),
        ("USEABLE_START_TIME", meta.useable_start_time),
        ("USEABLE_STOP_TIME", meta.useable_stop_time),
        ("STOP_TIME", meta.stop_time),
        ("INTERPOLATION", meta.interpolation),
        ("INTERPOLATION_DEGREE", degree),
    )
    out = [f"{key} = {value}" for key, value in ordered if value is not None]
    out.extend(f"{key} = {value}" for key, value in meta.extra)
    return out


def _serialize_state(segment: OemSegment, index: int) -> str:
    parts = [_format_epoch(segment.epochs[index])]
    parts.extend(_format_float(value) for value in segment.positions[index])
    parts.extend(_format_float(value) for value in segment.velocities[index])
    if segment.accelerations is not None:
        parts.extend(_format_float(value) for value in segment.accelerations[index])
    return " ".join(parts)


def _serialize_covariance(covariance: OemCovariance) -> list[str]:
    out: list[str] = ["COVARIANCE_START"]
    out.extend(_comment_lines(covariance.comments))
    out.append(f"EPOCH = {_format_epoch(covariance.epoch)}")
    if covariance.cov_ref_frame is not None:
        out.append(f"COV_REF_FRAME = {covariance.cov_ref_frame}")
    # The 21 elements lay out as the lower triangle: rows of length 1, 2, ... 6.
    start = 0
    for row_length in range(1, 7):
        row = covariance.matrix[start : start + row_length]
        out.append(" ".join(_format_float(value) for value in row))
        start += row_length
    out.append("COVARIANCE_STOP")
    return out


def _comment_lines(comments: tuple[str, ...]) -> list[str]:
    return [f"COMMENT {text}".rstrip() for text in comments]


def _format_epoch(epoch: np.datetime64) -> str:
    """Format a ``datetime64`` as a CCSDS calendar epoch, trimming trailing zero fraction."""
    text = str(np.datetime_as_string(epoch))
    if "." not in text:  # pragma: no cover - datetime64[ns] always carries a fraction
        return text
    head, fraction = text.split(".")
    fraction = fraction.rstrip("0")
    return f"{head}.{fraction}" if fraction else head


def _format_float(value: float) -> str:
    """Shortest decimal string that round-trips to the same float64 — no precision lost."""
    return repr(float(value))


register_writer("ccsds-oem", write_oem)
