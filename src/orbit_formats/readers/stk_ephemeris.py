"""STK ephemeris reader — the AGI / STK text ephemeris (``.e``) into a canonical Ephemeris.

GMAT's STK-TimePosVel ephemeris writer (and AGI's STK itself) emits a one-line
``stk.v.X.Y`` version banner, optional ``# …`` comment lines, then a ``BEGIN Ephemeris``
block of whitespace-separated ``KEY VALUE`` metadata followed by an ``EphemerisTimePosVel``
(or ``EphemerisTimePosVelAcc``) data section — each record is an offset-from-epoch in
seconds plus the position / velocity (and, for the ``…Acc`` section, the acceleration)
triplet, in km / km·s⁻¹ (/ km·s⁻²) — terminated by ``END Ephemeris``.

Both data-section variants parse into the *same* faithful :class:`StkEphemerisFile` fidelity
model — the version banner, every header comment, every ``BEGIN Ephemeris`` meta keyword
verbatim, and the records — which is then adapted into a canonical
:class:`~orbit_formats.canonical.ephemeris.Ephemeris`, with the fidelity model retained as
``source_native`` so a same-format write stays byte-lossless. Acceleration columns ride on
the fidelity model only (the canonical ``Ephemeris`` holds position and velocity); they are
preserved, never down-projected — the same treatment the OEM reader gives OEM acceleration.

Records carry an offset from the ``ScenarioEpoch`` meta value, made absolute by adding it. A
``.e`` file declares no time scale, so the canonical time scale is tagged **UTC** — GMAT's
default ``EpochFormat`` for the STK writer, and the only sensible default — while the raw
``ScenarioEpoch`` text is preserved verbatim on the fidelity model so a consumer whose
mission pinned a non-UTC scale can re-interpret it. ``ScenarioEpoch`` itself is parsed
locale-independently: a Gregorian ``DD Mon YYYY HH:MM:SS.fff`` value, or a bare number read
as a GMAT Modified Julian Date (days since 1941-01-05 12:00:00, GMAT's MJD epoch — the same
convention the GMAT-report reader uses).

The frame (``CoordinateSystem``) and central body (``CentralBody``) are tagged from the meta
block where present; frames are tagged, never rotated (the conversion layer's ``frame=`` does
that). Only the ``stk.v.X.Y`` banner, the ``BEGIN Ephemeris`` block, ``ScenarioEpoch`` and a
recognised data-section header are mandatory; header variants across GMAT / STK releases
(with or without ``InterpolationMethod`` / ``InterpolationSamplesM1`` / ``DistanceUnit``,
differing padding) are tolerated, and every keyword this reader does not specially interpret
survives verbatim on the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["StkEphemerisFile", "read_stk_ephemeris"]

# Block markers and the two data-section headers this reader parses. EphemerisTimePosVel
# carries six state components per record; EphemerisTimePosVelAcc adds the acceleration
# triplet (kept on the fidelity model — the canonical Ephemeris holds position and velocity).
_BEGIN_EPHEMERIS = "BEGIN Ephemeris"
_END_EPHEMERIS = "END Ephemeris"
_DATA_POS_VEL = "EphemerisTimePosVel"
_DATA_POS_VEL_ACC = "EphemerisTimePosVelAcc"
_DATA_SECTIONS = (_DATA_POS_VEL, _DATA_POS_VEL_ACC)

# Record column counts: an offset plus the six (pos/vel) or nine (pos/vel/acc) components.
_COLUMNS_POS_VEL = 1 + 6
_COLUMNS_POS_VEL_ACC = 1 + 9

# The ``stk.v.X.Y`` banner; the version number is captured but not validated. One-or-more
# dotted integers are accepted so ``stk.v.11.0`` and the rarer ``stk.v.12`` both match.
_VERSION_BANNER_RE = re.compile(r"^stk\.v\.\d+(?:\.\d+)*$", re.IGNORECASE)

# Meta keys lifted onto the canonical spine. Every other key the file declares survives
# verbatim on ``StkEphemerisFile.meta``; these are the ones the canonical form has a slot for.
_META_CENTRAL_BODY = "CentralBody"
_META_COORDINATE_SYSTEM = "CoordinateSystem"
_META_INTERPOLATION = "InterpolationMethod"
_META_INTERPOLATION_DEGREE = "InterpolationSamplesM1"
_META_SCENARIO_EPOCH = "ScenarioEpoch"

# A ``.e`` declares no time scale; UTC is GMAT's STK-writer default. See the module docstring.
_DEFAULT_TIME_SCALE = "UTC"

# Month abbreviations for the Gregorian ScenarioEpoch, mapped explicitly so parsing is
# locale-independent (``%b`` would depend on the active locale).
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}  # fmt: skip

# GMAT's Modified Julian Date epoch: JD 2430000.0 = 1941-01-05 12:00:00 (not the standard MJD
# origin). The same epoch the GMAT-report reader uses, so numeric ScenarioEpoch values agree.
_GMAT_MJD_EPOCH = np.datetime64("1941-01-05T12:00:00", "ns")
_SECONDS_PER_DAY = 86400.0
_NS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True, eq=False)
class StkEphemerisFile(FidelityModel):
    """The faithful STK ephemeris fidelity model: banner, comments, meta, and records.

    Holds every field a same-format STK write reconstructs from: ``version`` is the
    ``stk.v.X.Y`` banner line, ``header_comments`` the ``# …`` lines above ``BEGIN
    Ephemeris``, ``meta`` every ``BEGIN Ephemeris`` ``KEY VALUE`` pair in file order
    (original-case key, verbatim value — including ``ScenarioEpoch``, ``CentralBody``,
    ``CoordinateSystem``, ``NumberOfEphemerisPoints``, and any keyword this reader does not
    specially interpret), and ``data_section`` the header the records were written under.

    ``epochs`` is ``(n,)`` ``datetime64[ns]`` — the record offsets made absolute against
    ``ScenarioEpoch``; ``positions`` / ``velocities`` are ``(n, 3)`` km / km·s⁻¹.
    ``accelerations`` is ``(n, 3)`` km·s⁻² when the data section is
    ``EphemerisTimePosVelAcc``, else ``None``. ``scenario_epoch`` is the parsed absolute
    ``ScenarioEpoch`` (the record-offset origin); a content-lossless re-serialise recomputes
    each record's offset from it.

    ``raw_bytes`` is the verbatim source, kept only when the read opted in via
    ``retain_source=True`` (otherwise ``None``); it is a reference to the already-loaded
    buffer, not a copy. The writer echoes it for a byte-identical same-format re-emit; with it
    absent, the writer re-serialises this structured model (content-lossless).
    """

    format_name: ClassVar[str] = "stk-ephemeris"

    version: str
    scenario_epoch: np.datetime64
    epochs: NDArray[np.datetime64]
    positions: NDArray[np.float64]
    velocities: NDArray[np.float64]
    accelerations: NDArray[np.float64] | None = None
    data_section: str = _DATA_POS_VEL
    meta: tuple[tuple[str, str], ...] = ()
    header_comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None

    def meta_value(self, key: str) -> str | None:
        """The value of meta keyword ``key`` (first match, case-sensitive), or ``None``."""
        for name, value in self.meta:
            if name == key:
                return value
        return None


def read_stk_ephemeris(source: Source) -> Ephemeris:
    """Read an STK ephemeris (``.e``) into a canonical :class:`Ephemeris`.

    Parses the banner, header comments, ``BEGIN Ephemeris`` meta block, and the
    ``EphemerisTimePosVel`` / ``EphemerisTimePosVelAcc`` records into an
    :class:`StkEphemerisFile` fidelity model, retained as ``source_native``, then adapts the
    records into one canonical ephemeris tagged with the frame (``CoordinateSystem``), central
    body (``CentralBody``), and time scale (UTC — see the module docstring) from the meta.
    Acceleration columns, ``ScenarioEpoch``'s raw text, and every other meta keyword stay on
    the fidelity model. Raises :class:`~orbit_formats.errors.MalformedSourceError` for a
    missing banner / ``BEGIN Ephemeris`` / ``ScenarioEpoch`` / data section, an unsupported
    data section, a record with the wrong column count or a non-numeric value, an unparseable
    ``ScenarioEpoch``, a non-integer ``InterpolationSamplesM1``, or content after ``END
    Ephemeris``.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    stk = _parse(source.read_text().lstrip("﻿").splitlines())
    if source.retain:
        stk = replace(stk, raw_bytes=source.read_bytes())
    return _to_ephemeris(stk)


def _parse(lines: list[str]) -> StkEphemerisFile:
    """Scan the ``.e`` lines once into the faithful :class:`StkEphemerisFile` model."""
    version = ""
    comments: list[str] = []
    meta: list[tuple[str, str]] = []
    offsets: list[float] = []
    positions: list[list[float]] = []
    velocities: list[list[float]] = []
    accelerations: list[list[float]] = []
    data_section: str | None = None

    in_ephemeris = False
    in_data = False
    seen_end = False

    for index, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if seen_end:
            raise MalformedSourceError(f"line {index}: content after END Ephemeris: {line!r}")

        if not in_ephemeris:
            # Pre-``BEGIN Ephemeris``: the version banner first, then optional ``# …`` comments.
            if line == _BEGIN_EPHEMERIS:
                if not version:
                    raise MalformedSourceError(
                        f"line {index}: BEGIN Ephemeris before the stk.v.X.Y banner"
                    )
                in_ephemeris = True
                continue
            if line.startswith("#"):
                comments.append(line)
                continue
            if _VERSION_BANNER_RE.match(line):
                if version:
                    raise MalformedSourceError(f"line {index}: duplicate stk.v.X.Y banner")
                version = line
                continue
            raise MalformedSourceError(
                f"line {index}: expected the stk.v.X.Y banner, a '# …' comment, or "
                f"'BEGIN Ephemeris', got {line!r}"
            )

        if line == _END_EPHEMERIS:
            seen_end = True
            in_data = False
            continue

        if not in_data:
            # Inside the block, before the data section: the data-section marker, or meta lines.
            if line in _DATA_SECTIONS:
                data_section = line
                in_data = True
                continue
            if _looks_like_data_section(line):
                raise MalformedSourceError(
                    f"line {index}: unsupported STK data section {line!r}; this reader parses "
                    f"{_DATA_POS_VEL!r} and {_DATA_POS_VEL_ACC!r}"
                )
            meta.append(_parse_meta_line(line, index))
            continue

        assert data_section is not None  # in_data is only set once data_section is assigned
        offset, position, velocity, acceleration = _parse_record(line, index, data_section)
        offsets.append(offset)
        positions.append(position)
        velocities.append(velocity)
        if acceleration is not None:
            accelerations.append(acceleration)

    if not version:
        raise MalformedSourceError("not an STK ephemeris: the stk.v.X.Y version banner is missing")
    if not in_ephemeris:
        raise MalformedSourceError("not an STK ephemeris: the 'BEGIN Ephemeris' block is missing")
    if data_section is None:
        raise MalformedSourceError(
            f"the STK ephemeris has no data section "
            f"(expected {_DATA_POS_VEL!r} or {_DATA_POS_VEL_ACC!r})"
        )
    scenario_raw = _meta_value(meta, _META_SCENARIO_EPOCH)
    if scenario_raw is None:
        raise MalformedSourceError(
            f"the STK ephemeris meta block is missing the required {_META_SCENARIO_EPOCH!r}"
        )
    scenario_epoch = _parse_scenario_epoch(scenario_raw)
    return StkEphemerisFile(
        version=version,
        scenario_epoch=scenario_epoch,
        epochs=_absolute_epochs(scenario_epoch, offsets),
        positions=_float_matrix(positions),
        velocities=_float_matrix(velocities),
        accelerations=(_float_matrix(accelerations) if data_section == _DATA_POS_VEL_ACC else None),
        data_section=data_section,
        meta=tuple(meta),
        header_comments=tuple(comments),
    )


def _looks_like_data_section(line: str) -> bool:
    """Whether a lone ``Ephemeris…`` token is an STK data-section header (so it is not meta)."""
    return line.startswith("Ephemeris") and len(line.split()) == 1


def _parse_meta_line(line: str, index: int) -> tuple[str, str]:
    """Split a whitespace-separated STK ``KEY VALUE`` meta line (values may contain spaces)."""
    tokens = line.split(maxsplit=1)
    if len(tokens) != 2:
        raise MalformedSourceError(
            f"line {index}: expected an STK 'KEY VALUE' meta line, got {line!r}"
        )
    return tokens[0], tokens[1].strip()


def _parse_record(
    line: str, index: int, data_section: str
) -> tuple[float, list[float], list[float], list[float] | None]:
    """Parse one data record: an offset plus the 6 (pos/vel) or 9 (pos/vel/acc) components."""
    with_accel = data_section == _DATA_POS_VEL_ACC
    expected = _COLUMNS_POS_VEL_ACC if with_accel else _COLUMNS_POS_VEL
    tokens = line.split()
    if len(tokens) != expected:
        kind = "offset + pos/vel/acc" if with_accel else "offset + pos/vel"
        raise MalformedSourceError(
            f"line {index}: expected {expected} columns ({kind}), got {len(tokens)}"
        )
    try:
        values = [float(token) for token in tokens]
    except ValueError as exc:
        raise MalformedSourceError(
            f"line {index}: non-numeric value in the STK data record {line!r}"
        ) from exc
    acceleration = values[7:10] if with_accel else None
    return values[0], values[1:4], values[4:7], acceleration


def _meta_value(meta: list[tuple[str, str]], key: str) -> str | None:
    for name, value in meta:
        if name == key:
            return value
    return None


def _parse_scenario_epoch(value: str) -> np.datetime64:
    """Parse a ``ScenarioEpoch`` value — Gregorian (alphabetic month) or numeric ModJulian."""
    text = value.strip()
    if not text:
        raise MalformedSourceError("the STK ScenarioEpoch value is empty")
    if any(ch.isalpha() for ch in text):
        return _parse_gregorian_epoch(text)
    return _parse_modjulian_epoch(text)


def _parse_gregorian_epoch(text: str) -> np.datetime64:
    """Parse a Gregorian ScenarioEpoch ``DD Mon YYYY HH:MM:SS.fff`` to ``datetime64[ns]``."""
    parts = text.split()
    if len(parts) != 4:
        raise _scenario_error(text, "expected 'DD Mon YYYY HH:MM:SS.fff'")
    day_str, month_str, year_str, time_str = parts
    month = _MONTHS.get(month_str.title())
    if month is None:
        raise _scenario_error(text, f"unknown month {month_str!r}")
    fields = time_str.split(":")
    if len(fields) != 3:
        raise _scenario_error(text, "expected HH:MM:SS in the time of day")
    try:
        year, day = int(year_str), int(day_str)
        hours, minutes, seconds = int(fields[0]), int(fields[1]), float(fields[2])
        base = np.datetime64(f"{year:04d}-{month:02d}-{day:02d}", "ns")
    except (ValueError, TypeError) as exc:
        raise _scenario_error(text, str(exc)) from exc
    offset = hours * 3600 + minutes * 60 + seconds
    return base + np.timedelta64(round(offset * _NS_PER_SECOND), "ns")


def _parse_modjulian_epoch(text: str) -> np.datetime64:
    """Parse a numeric ScenarioEpoch as a GMAT Modified Julian Date (days since 1941-01-05)."""
    try:
        days = float(text)
    except ValueError as exc:
        raise _scenario_error(text, "neither Gregorian nor a numeric ModJulian date") from exc
    return _GMAT_MJD_EPOCH + np.timedelta64(round(days * _SECONDS_PER_DAY * _NS_PER_SECOND), "ns")


def _scenario_error(text: str, detail: str) -> MalformedSourceError:
    return MalformedSourceError(f"could not parse the STK ScenarioEpoch {text!r}: {detail}")


def _absolute_epochs(scenario_epoch: np.datetime64, offsets: list[float]) -> NDArray[np.datetime64]:
    """Make each record's offset-from-epoch absolute by adding ``scenario_epoch``."""
    epochs = [
        scenario_epoch + np.timedelta64(round(offset * _NS_PER_SECOND), "ns") for offset in offsets
    ]
    return np.array(epochs, dtype="datetime64[ns]")


def _float_matrix(rows: list[list[float]]) -> NDArray[np.float64]:
    if not rows:
        return np.empty((0, 3), dtype=np.float64)
    return np.array(rows, dtype=np.float64)


def _to_ephemeris(stk: StkEphemerisFile) -> Ephemeris:
    """Adapt an :class:`StkEphemerisFile` into the canonical :class:`Ephemeris`.

    Tags the spine from the meta block — frame, central body, the UTC default scale, and the
    interpolation hint — and carries the whole fidelity model as ``source_native``.
    """
    metadata = Metadata(
        reference_frame=stk.meta_value(_META_COORDINATE_SYSTEM),
        central_body=stk.meta_value(_META_CENTRAL_BODY),
        time_scale=_DEFAULT_TIME_SCALE,
        provenance=Provenance(source_format="stk-ephemeris"),
    )
    return Ephemeris(
        metadata=metadata,
        source_native=stk,
        epochs=stk.epochs,
        positions=stk.positions,
        velocities=stk.velocities,
        interpolation=stk.meta_value(_META_INTERPOLATION),
        interpolation_degree=_interpolation_degree(stk),
    )


def _interpolation_degree(stk: StkEphemerisFile) -> int | None:
    """The ``InterpolationSamplesM1`` hint as an int, or ``None`` if absent; rejects non-ints."""
    raw = stk.meta_value(_META_INTERPOLATION_DEGREE)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise MalformedSourceError(
            f"{_META_INTERPOLATION_DEGREE} must be an integer, got {raw!r}"
        ) from exc


register_reader("stk-ephemeris", read_stk_ephemeris)
