"""STK ephemeris writer — byte-lossless (opt-in), content-lossless, and synthesised paths.

Mirrors the OEM writer's three tiers, picked automatically from what the canonical object
carries:

1. An ``Ephemeris`` whose ``source_native`` is a
   :class:`~orbit_formats.readers.stk_ephemeris.StkEphemerisFile` **with retained bytes**
   (the read opted in via ``retain_source=True``) → the verbatim bytes are echoed, so the
   same-format round trip is **byte-identical** by construction.
2. An ``Ephemeris`` with an ``StkEphemerisFile`` ``source_native`` **without** retained bytes
   → the structured fidelity model is re-serialised: **content-lossless** (the banner, every
   comment and meta keyword, and the records — acceleration included — preserved), canonically
   formatted.
3. Any other ``Ephemeris`` (synthesised or cross-format, no STK ``source_native``) → an STK
   ephemeris is built from the canonical fields, warning (via the lossy-warning framework) for
   each ``.e``-required field the canonical form cannot supply.

STK ephemeris has a single text notation, so the destination extension only selects the
format, never a notation; the ``suffix`` argument is accepted (for the writer protocol) and
ignored.
"""

from __future__ import annotations

import numpy as np

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.stk_ephemeris import StkEphemerisFile
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy

__all__ = ["write_stk_ephemeris"]

# Block markers and the position/velocity data-section header a synthesised file declares
# (the canonical Ephemeris has no acceleration, so a synthesised file is always pos/vel).
_BEGIN_EPHEMERIS = "BEGIN Ephemeris"
_END_EPHEMERIS = "END Ephemeris"
_DATA_POS_VEL = "EphemerisTimePosVel"

# The STK version banner a synthesised file declares, and the placeholder it writes where the
# canonical form cannot supply a required meta value.
_STK_VERSION = "stk.v.11.0"
_PLACEHOLDER = "UNKNOWN"

# The meta keywords sourced from canonical metadata when synthesising, paired with the
# attribute each comes from. ``ScenarioEpoch`` is derived from the epochs, handled separately.
_REQUIRED_FROM_METADATA = (
    ("CentralBody", "central_body"),
    ("CoordinateSystem", "reference_frame"),
)

# Locale-independent month abbreviations for the Gregorian ScenarioEpoch the writer emits.
_MONTH_ABBR = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)  # fmt: skip
_NS_PER_SECOND = 1_000_000_000


def write_stk_ephemeris(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (an :class:`Ephemeris`) to STK ephemeris (``.e``) bytes.

    Picks the byte-identical, content-lossless, or synthesised path automatically — see the
    module docstring. ``suffix`` (the destination extension) is ignored: STK ephemeris has a
    single text notation. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if
    ``obj`` is not an ``Ephemeris`` — STK ephemeris is an ephemeris format, and converting
    another canonical form to it is the conversion layer's job, not the writer's.
    """
    if not isinstance(obj, Ephemeris):
        raise UnsupportedConversionError(type(obj).__name__, "stk-ephemeris", "ephemeris")
    native = obj.source_native
    if isinstance(native, StkEphemerisFile):
        if native.raw_bytes is not None:
            return native.raw_bytes
        return _serialize(native)
    return _serialize(_stkfile_from_ephemeris(obj))


def _stkfile_from_ephemeris(eph: Ephemeris) -> StkEphemerisFile:
    """Build an :class:`StkEphemerisFile` from a canonical ``Ephemeris``, warning on gaps.

    Each ``.e``-required field the canonical form cannot supply is written as a placeholder
    and reported through :func:`~orbit_formats.warnings.warn_lossy`, so a synthesised STK
    ephemeris is structurally valid yet never silently incomplete.
    """
    count = len(eph)
    meta: list[tuple[str, str]] = [("NumberOfEphemerisPoints", str(count))]
    if count:
        scenario_epoch = eph.epochs[0]
        meta.append(("ScenarioEpoch", _format_scenario_epoch(scenario_epoch)))
    else:
        # With no states, ScenarioEpoch cannot be derived from the epochs; warn and placeholder.
        # The sentinel epoch is unused — there are no records to offset against it.
        _warn_missing("ScenarioEpoch", "the canonical ephemeris has no epochs to derive it from")
        scenario_epoch = np.datetime64("2000-01-01T12:00:00", "ns")
        meta.append(("ScenarioEpoch", _PLACEHOLDER))
    for keyword, attribute in _REQUIRED_FROM_METADATA:
        meta.append((keyword, _resolve_required(keyword, getattr(eph.metadata, attribute))))
    if eph.interpolation is not None:
        meta.append(("InterpolationMethod", eph.interpolation))
    if eph.interpolation_degree is not None:
        meta.append(("InterpolationSamplesM1", str(eph.interpolation_degree)))
    return StkEphemerisFile(
        version=_STK_VERSION,
        scenario_epoch=scenario_epoch,
        epochs=eph.epochs,
        positions=eph.positions,
        velocities=eph.velocities,
        accelerations=None,
        data_section=_DATA_POS_VEL,
        meta=tuple(meta),
        header_comments=(),
    )


def _resolve_required(keyword: str, value: str | None) -> str:
    """Return ``value`` if present, else warn that the STK-required field is unavailable."""
    if value is not None:
        return value
    _warn_missing(keyword, "the canonical ephemeris did not carry it")
    return _PLACEHOLDER


def _warn_missing(keyword: str, reason: str) -> None:
    warn_lossy(
        LossyConversionWarning(
            f"the ephemeris does not supply the STK-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, reason),),
        ),
        stacklevel=4,
    )


def _serialize(stk: StkEphemerisFile) -> bytes:
    """Serialise an :class:`StkEphemerisFile` to canonical STK ephemeris bytes (lossless)."""
    lines: list[str] = [stk.version, ""]
    if stk.header_comments:
        lines.extend(stk.header_comments)
        lines.append("")
    lines.append(_BEGIN_EPHEMERIS)
    lines.append("")
    lines.extend(f"{key} {value}" for key, value in stk.meta)
    lines.append("")
    lines.append(stk.data_section)
    lines.append("")
    lines.extend(_serialize_record(stk, index) for index in range(len(stk.epochs)))
    lines.append("")
    lines.append(_END_EPHEMERIS)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_record(stk: StkEphemerisFile, index: int) -> str:
    parts = [_format_float(_offset_seconds(stk.epochs[index], stk.scenario_epoch))]
    parts.extend(_format_float(value) for value in stk.positions[index])
    parts.extend(_format_float(value) for value in stk.velocities[index])
    if stk.accelerations is not None:
        parts.extend(_format_float(value) for value in stk.accelerations[index])
    return " ".join(parts)


def _offset_seconds(epoch: np.datetime64, scenario_epoch: np.datetime64) -> float:
    """The record offset in seconds: the epoch's distance from the ScenarioEpoch origin."""
    nanoseconds = (epoch - scenario_epoch) / np.timedelta64(1, "ns")
    return float(nanoseconds) / _NS_PER_SECOND


def _format_scenario_epoch(epoch: np.datetime64) -> str:
    """Format a ``datetime64`` as a Gregorian ScenarioEpoch ``DD Mon YYYY HH:MM:SS.fff``.

    Trailing zero fractional digits are trimmed but at least milliseconds are kept, so a
    re-read parses the same instant (sub-second precision survives) yet round seconds stay
    tidy (``…:00.000``).
    """
    iso = str(np.datetime_as_string(epoch))
    date_part, _, time_part = iso.partition("T")
    year_str, month_str, day_str = date_part.split("-")
    clock, _, fraction = time_part.partition(".")
    fraction = fraction.rstrip("0")
    if len(fraction) < 3:
        fraction = fraction.ljust(3, "0")
    month = _MONTH_ABBR[int(month_str) - 1]
    return f"{int(day_str):02d} {month} {int(year_str):04d} {clock}.{fraction}"


def _format_float(value: float) -> str:
    """Shortest decimal string that round-trips to the same float64 — no precision lost."""
    return repr(float(value))


register_writer("stk-ephemeris", write_stk_ephemeris)
