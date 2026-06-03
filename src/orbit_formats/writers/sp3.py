"""SP3 writer — byte-lossless (opt-in), content-lossless, and synthesised paths.

Mirrors the STK / OEM ephemeris writers' three tiers, picked automatically from what the
canonical object carries:

1. An ``Ephemeris`` whose ``source_native`` is a
   :class:`~orbit_formats.readers.sp3.Sp3File` **with retained bytes** (the read opted in via
   ``retain_source=True``) → the verbatim bytes are echoed, so the same-format round trip is
   **byte-identical** by construction.
2. An ``Ephemeris`` with an ``Sp3File`` ``source_native`` **without** retained bytes → the
   structured fidelity model is re-serialised: **content-lossless** (every satellite's
   position / velocity / clock series, the per-satellite accuracy codes, and the whole header
   preserved), canonically formatted in the SP3 fixed-column layout.
3. Any other ``Ephemeris`` (synthesised or cross-format, no SP3 ``source_native``) → a
   single-satellite **SP3-d** file is built from the canonical fields, warning (via the
   lossy-warning framework) for each SP3-required field the canonical form cannot supply — the
   satellite clock columns (the canonical ``Ephemeris`` holds no clock), the satellite id when
   ``object_name`` is not a system+PRN id, and the coordinate system / time system when the
   metadata omits them — and for any value truncated to SP3's fixed field width.

SP3 has a single text notation, so the destination extension only selects the format, never a
notation; the ``suffix`` argument is accepted (for the writer protocol) and ignored. The
serialiser follows the SP3-c / SP3-d fixed-column record formats; SP3-d reuses SP3-c's record
columns and only relaxes the fixed header-line counts.
"""

from __future__ import annotations

import re

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.sp3 import Sp3File
from orbit_formats.registry import register_writer
from orbit_formats.warnings import (
    DroppedField,
    LossyConversionWarning,
    PrecisionLossWarning,
    warn_dropped_maneuvers,
    warn_lossy,
)

__all__ = ["write_sp3"]

# A canonical SP3 satellite id is a one-letter system code plus a two-digit number (``G01``).
_SAT_ID_RE = re.compile(r"^[A-Z]\d{2}$")
# The id a synthesised file writes when ``object_name`` is not a usable SP3 satellite id: SP3
# is a GNSS product and has no slot for an arbitrary object name.
_PLACEHOLDER_SAT_ID = "L00"

# The SP3 "value not available" sentinel for a clock offset / rate (microseconds): a synthesised
# file writes it for every record, since the canonical Ephemeris carries no satellite clock.
_MISSING_CLOCK = 999999.999999

# A state column is F14.6 (14 chars, 6 decimals). SP3 velocities are decimetres·s⁻¹; the
# canonical Ephemeris holds km·s⁻¹.
_STATE_WIDTH = 14
_STATE_DP = 6
_KM_S_TO_DM_S = 1e4

# Defaults the synthesised path writes into the descriptive (non-orbital) header fields. These
# carry no canonical information, so writing a default does not drop anything.
_SYNTH_VERSION = "d"
_DEFAULT_DATA_USED = "ORBIT"
_DEFAULT_ORBIT_TYPE = "FIT"
_DEFAULT_AGENCY = "ORBF"
_DEFAULT_FILE_TYPE = "M"
_DEFAULT_TIME_SYSTEM = "UTC"
_PLACEHOLDER_FRAME = "UNKN"
_DEFAULT_STD_BASE_POS = 1.25
_DEFAULT_STD_BASE_CLOCK = 1.025
_SYNTH_COMMENT = "synthesised by orbit-formats from a canonical ephemeris"

# Reserved header lines a complete SP3 file carries. The reader ignores them; the writer emits
# them verbatim so the output is a structurally complete, valid SP3 file and re-reads to the
# same fidelity model (the round trip is a fixed point).
_RESERVED_C2 = "%c cc cc ccc ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc"
_RESERVED_F2 = "%f  0.0000000  0.000000000  0.00000000000  0.000000000000000"
_RESERVED_I = "%i    0    0    0    0      0      0      0      0         0"

# Epoch anchors for the derived ``##`` time header and the empty-ephemeris fallback.
_GPS_EPOCH = np.datetime64("1980-01-06T00:00:00", "ns")
_MJD_EPOCH = np.datetime64("1858-11-17", "D")
_FALLBACK_EPOCH = np.datetime64("2000-01-01T12:00:00", "ns")
_SECONDS_PER_WEEK = 7 * 86400


def write_sp3(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (an :class:`Ephemeris`) to SP3 (``.sp3``) bytes.

    Picks the byte-identical, content-lossless, or synthesised path automatically — see the
    module docstring. ``suffix`` (the destination extension) is ignored: SP3 has a single text
    notation. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not
    an ``Ephemeris`` — SP3 is an ephemeris format, and converting another canonical form to it
    is the conversion layer's job, not the writer's.
    """
    if not isinstance(obj, Ephemeris):
        raise UnsupportedConversionError(type(obj).__name__, "sp3", "ephemeris")
    native = obj.source_native
    if isinstance(native, Sp3File):
        if native.raw_bytes is not None:
            return native.raw_bytes
        return _serialize(native)
    # SP3 has no maneuver block: any canonical maneuvers the ephemeris carries are reported dropped.
    warn_dropped_maneuvers(obj.maneuvers, target_format="sp3")
    return _serialize(_sp3file_from_ephemeris(obj))


def _sp3file_from_ephemeris(eph: Ephemeris) -> Sp3File:
    """Build a single-satellite SP3-d :class:`Sp3File` from a canonical ``Ephemeris``.

    Each SP3-required field the canonical form cannot supply is filled with a sentinel /
    placeholder and reported through :func:`~orbit_formats.warnings.warn_lossy`, so a synthesised
    SP3 file is structurally valid yet never silently incomplete. The GPS-week / MJD time header
    is *derived* from the epochs (not a loss), and the descriptive header fields take neutral
    defaults.
    """
    sat_id = _resolve_sat_id(eph.metadata.object_name)
    count = len(eph)
    if not count:
        _warn_missing(
            "start epoch",
            "the canonical ephemeris has no epochs to derive the SP3 start time from",
        )
    positions = {sat_id: eph.positions}
    if count:
        _warn_missing(
            "clock",
            f"the canonical ephemeris carries no satellite clock; wrote the SP3 "
            f"missing-value {_MISSING_CLOCK}",
        )
    clocks = {sat_id: np.full(count, _MISSING_CLOCK)}
    if count and not np.isnan(eph.velocities).all():
        mode = "V"
        velocities: dict[str, NDArray[np.float64]] | None = {sat_id: eph.velocities}
        clock_rates: dict[str, NDArray[np.float64]] | None = {
            sat_id: np.full(count, _MISSING_CLOCK)
        }
    else:
        mode = "P"
        velocities = None
        clock_rates = None
    week, sow, interval, mjd, fractional_day = _derive_time_header(eph.epochs)
    return Sp3File(
        version=_SYNTH_VERSION,
        mode=mode,
        sat_ids=(sat_id,),
        accuracy_codes=(0,),
        epochs=eph.epochs,
        positions=positions,
        clocks=clocks,
        velocities=velocities,
        clock_rates=clock_rates,
        coordinate_system=_resolve_required("coordinate system", eph.metadata.reference_frame),
        orbit_type=_DEFAULT_ORBIT_TYPE,
        agency=_DEFAULT_AGENCY,
        data_used=_DEFAULT_DATA_USED,
        file_type=sat_id[0],
        time_system=_resolve_time_system(eph.metadata.time_scale),
        gps_week=week,
        seconds_of_week=sow,
        epoch_interval=interval,
        mjd=mjd,
        fractional_day=fractional_day,
        std_dev_base_pos=_DEFAULT_STD_BASE_POS,
        std_dev_base_clock=_DEFAULT_STD_BASE_CLOCK,
        comments=(_SYNTH_COMMENT,),
    )


def _resolve_sat_id(object_name: str | None) -> str:
    """The ``object_name`` if it is already a system+PRN id, else a placeholder (warning)."""
    if object_name is not None and _SAT_ID_RE.match(object_name):
        return object_name
    _warn_missing(
        "satellite id",
        f"object_name {object_name!r} is not a valid SP3 system+PRN id; wrote the "
        f"placeholder {_PLACEHOLDER_SAT_ID!r}",
    )
    return _PLACEHOLDER_SAT_ID


def _resolve_required(field: str, value: str | None) -> str:
    """Return ``value`` if present, else warn that the SP3-required field is unavailable."""
    if value is not None:
        return value
    _warn_missing(field, "the canonical ephemeris did not carry it")
    return _PLACEHOLDER_FRAME


def _resolve_time_system(time_scale: str | None) -> str:
    """Return ``time_scale`` if present, else warn and default to UTC."""
    if time_scale is not None:
        return time_scale
    _warn_missing(
        "time system",
        f"the canonical ephemeris did not carry a time scale; wrote {_DEFAULT_TIME_SYSTEM!r}",
    )
    return _DEFAULT_TIME_SYSTEM


def _warn_missing(field: str, reason: str) -> None:
    warn_lossy(
        LossyConversionWarning(
            f"the ephemeris does not supply the SP3-required {field}",
            dropped=(DroppedField(field, reason),),
        ),
        stacklevel=4,
    )


def _derive_time_header(
    epochs: NDArray[np.datetime64],
) -> tuple[int, float, float, int, float]:
    """Derive the ``##`` line's GPS week / seconds-of-week / interval / MJD / fractional day.

    All five follow from the epochs, so they are computed rather than warned as missing. With no
    epochs they fall back to the SP3 J2000 anchor.
    """
    start = epochs[0] if epochs.shape[0] else _FALLBACK_EPOCH
    since_gps = (start - _GPS_EPOCH) / np.timedelta64(1, "s")
    week = int(since_gps // _SECONDS_PER_WEEK)
    seconds_of_week = since_gps - week * _SECONDS_PER_WEEK
    day = start.astype("datetime64[D]")
    mjd = int((day - _MJD_EPOCH) / np.timedelta64(1, "D"))
    fractional_day = float((start - day.astype("datetime64[ns]")) / np.timedelta64(1, "D"))
    interval = (
        float((epochs[1] - epochs[0]) / np.timedelta64(1, "s")) if epochs.shape[0] > 1 else 0.0
    )
    return week, float(seconds_of_week), interval, mjd, fractional_day


# --- serialisation (shared by the content-lossless and synthesised tiers) --------------


def _serialize(sp3: Sp3File) -> bytes:
    """Serialise an :class:`Sp3File` to canonical SP3 fixed-column bytes.

    Reproduces the header (version line, ``##`` time line, ``+`` satellite and ``++`` accuracy
    blocks, the ``%c`` / ``%f`` / ``%i`` lines, and the ``/*`` comments), then one ``*`` epoch
    record followed by a ``P`` position record (and, in ``V`` mode, a ``V`` velocity record) per
    satellite. A value that overflows SP3's fixed field width is truncated and named once in a
    :class:`~orbit_formats.warnings.PrecisionLossWarning`; a non-finite component (NaN / inf — a
    velocity sample the canonical ephemeris left absent) has no SP3 representation, is written as
    zero, and is named once in a :class:`~orbit_formats.warnings.LossyConversionWarning` — never a
    silent loss.
    """
    truncated: set[str] = set()
    nonfinite: set[str] = set()
    lines: list[str] = [_header_line1(sp3), _header_line2(sp3)]
    lines.extend(_satellite_block(sp3.sat_ids))
    lines.extend(_accuracy_block(sp3.sat_ids, sp3.accuracy_codes))
    lines.append(_percent_c(sp3))
    lines.append(_RESERVED_C2)
    lines.append(_percent_f(sp3))
    lines.append(_RESERVED_F2)
    lines.append(_RESERVED_I)
    lines.append(_RESERVED_I)
    lines.extend(f"/* {comment}" for comment in sp3.comments)
    for index in range(sp3.epochs.shape[0]):
        lines.append(_epoch_line(sp3.epochs[index]))
        for sat_id in sp3.sat_ids:
            lines.append(_position_record(sp3, sat_id, index, truncated, nonfinite))
            if sp3.mode == "V" and sp3.velocities is not None:
                lines.append(_velocity_record(sp3, sat_id, index, truncated, nonfinite))
    lines.append("EOF")
    if nonfinite:
        warn_lossy(
            LossyConversionWarning(
                "non-finite state components have no SP3 representation and were written as zero",
                dropped=tuple(
                    DroppedField(label, "a non-finite (NaN / inf) value was written as 0.000000")
                    for label in sorted(nonfinite)
                ),
            ),
            stacklevel=3,
        )
    if truncated:
        warn_lossy(
            PrecisionLossWarning(
                ", ".join(sorted(truncated)),
                target_format="sp3",
                detail="narrowed to fit SP3's fixed F14.6 field width",
            ),
            stacklevel=3,
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _header_line1(sp3: Sp3File) -> str:
    start = sp3.epochs[0] if sp3.epochs.shape[0] else _FALLBACK_EPOCH
    year, month, day, hour, minute, second = _decompose(start)
    data_used = sp3.data_used or _DEFAULT_DATA_USED
    coord = sp3.coordinate_system or _PLACEHOLDER_FRAME
    orbit_type = sp3.orbit_type or _DEFAULT_ORBIT_TYPE
    agency = sp3.agency or _DEFAULT_AGENCY
    return (
        f"#{sp3.version}{sp3.mode}{year:4d} {month:2d} {day:2d} {hour:2d} {minute:2d} "
        f"{second:11.8f} {sp3.epochs.shape[0]:7d} {data_used:>5} {coord:>5} "
        f"{orbit_type:>3} {agency:>4}"
    )


def _header_line2(sp3: Sp3File) -> str:
    week = sp3.gps_week if sp3.gps_week is not None else 0
    sow = sp3.seconds_of_week if sp3.seconds_of_week is not None else 0.0
    interval = sp3.epoch_interval if sp3.epoch_interval is not None else 0.0
    mjd = sp3.mjd if sp3.mjd is not None else 0
    fractional_day = sp3.fractional_day if sp3.fractional_day is not None else 0.0
    return f"## {week:4d} {sow:15.8f} {interval:14.8f} {mjd:5d} {fractional_day:15.13f}"


def _satellite_block(sat_ids: tuple[str, ...]) -> list[str]:
    """The ``+`` lines: the satellite count then the id list, 17 per line, ``  0``-padded."""
    return _id_block(sat_ids, sat_ids, marker="+", first_count=len(sat_ids))


def _accuracy_block(sat_ids: tuple[str, ...], codes: tuple[int, ...]) -> list[str]:
    """The ``++`` lines: the per-satellite accuracy exponents, aligned with the id list."""
    slots = tuple(f"{code:3d}" for code in codes)
    return _id_block(sat_ids, slots, marker="++", first_count=None)


def _id_block(
    sat_ids: tuple[str, ...], slots: tuple[str, ...], *, marker: str, first_count: int | None
) -> list[str]:
    """Render a ``+`` / ``++`` block: ``max(5, ceil(n/17))`` lines of 17 three-column slots."""
    line_count = max(5, -(-len(sat_ids) // 17)) if sat_ids else 5
    lines: list[str] = []
    for line_index in range(line_count):
        if marker == "+":
            prefix = f"+   {first_count:2d}   " if line_index == 0 else "+" + " " * 8
        else:
            prefix = "++" + " " * 7
        cells = []
        for slot_index in range(17):
            position = line_index * 17 + slot_index
            cells.append(slots[position] if position < len(slots) else "  0")
        lines.append(prefix + "".join(cells))
    return lines


def _percent_c(sp3: Sp3File) -> str:
    file_type = sp3.file_type or _DEFAULT_FILE_TYPE
    time_system = sp3.time_system or _DEFAULT_TIME_SYSTEM
    return f"%c {file_type:<2} cc {time_system:<3} ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc"


def _percent_f(sp3: Sp3File) -> str:
    base_pos = sp3.std_dev_base_pos if sp3.std_dev_base_pos is not None else _DEFAULT_STD_BASE_POS
    base_clock = (
        sp3.std_dev_base_clock if sp3.std_dev_base_clock is not None else _DEFAULT_STD_BASE_CLOCK
    )
    return f"%f {base_pos:10.7f} {base_clock:12.9f} {0.0:14.11f} {0.0:18.15f}"


def _epoch_line(epoch: np.datetime64) -> str:
    year, month, day, hour, minute, second = _decompose(epoch)
    return f"*  {year:4d} {month:2d} {day:2d} {hour:2d} {minute:2d} {second:11.8f}"


def _position_record(
    sp3: Sp3File, sat_id: str, index: int, truncated: set[str], nonfinite: set[str]
) -> str:
    x, y, z = sp3.positions[sat_id][index]
    clock = sp3.clocks[sat_id][index]
    body = "".join(_state(value, "position", truncated, nonfinite) for value in (x, y, z)) + _state(
        clock, "clock", truncated, nonfinite
    )
    return f"P{sat_id}{body}"


def _velocity_record(
    sp3: Sp3File, sat_id: str, index: int, truncated: set[str], nonfinite: set[str]
) -> str:
    assert sp3.velocities is not None
    vx, vy, vz = (component * _KM_S_TO_DM_S for component in sp3.velocities[sat_id][index])
    rate = sp3.clock_rates[sat_id][index] if sp3.clock_rates is not None else _MISSING_CLOCK
    body = "".join(
        _state(value, "velocity", truncated, nonfinite) for value in (vx, vy, vz)
    ) + _state(rate, "clock rate", truncated, nonfinite)
    return f"V{sat_id}{body}"


def _state(value: float, label: str, truncated: set[str], nonfinite: set[str]) -> str:
    """Format one state column as F14.6.

    A non-finite component (NaN / inf) has no SP3 representation, so it is written as zero and
    recorded under ``label`` for one no-silent-loss warning. An overflow of the fixed F14.6 width
    is narrowed and likewise recorded under ``label`` for one precision warning.
    """
    if not np.isfinite(value):
        nonfinite.add(label)
        value = 0.0
    text = f"{float(value):{_STATE_WIDTH}.{_STATE_DP}f}"
    if len(text) <= _STATE_WIDTH:
        return text
    truncated.add(label)
    for decimals in range(_STATE_DP - 1, -1, -1):
        text = f"{float(value):.{decimals}f}"
        if len(text) <= _STATE_WIDTH:
            return text.rjust(_STATE_WIDTH)
    return text[:_STATE_WIDTH]


def _decompose(epoch: np.datetime64) -> tuple[int, int, int, int, int, float]:
    """Split a ``datetime64`` into ``(year, month, day, hour, minute, second-with-fraction)``."""
    iso = str(np.datetime_as_string(epoch, unit="ns"))
    date_part, _, time_part = iso.partition("T")
    year, month, day = (int(token) for token in date_part.split("-"))
    hour_str, minute_str, second_str = time_part.split(":")
    return year, month, day, int(hour_str), int(minute_str), float(second_str)


register_writer("sp3", write_sp3)
