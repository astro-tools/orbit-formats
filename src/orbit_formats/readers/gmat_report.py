"""GMAT report reader — a GMAT ``ReportFile`` table into a canonical state series.

GMAT writes a ``ReportFile`` as whitespace-aligned text: a header row of resource-qualified
parameter names (e.g. ``Sat.EarthMJ2000Eq.X``), followed by data rows in the same column
layout. The column separator is a run of two or more spaces, so a single space inside a
value — the ``UTCGregorian`` epoch ``26 Nov 2026 12:00:00.000`` — never splits a column.
GMAT re-emits the header at mission-sequence segment boundaries; those repeats are skipped.

The whole table is parsed into a faithful :class:`GmatReportFile` fidelity model — every
column, every cell, verbatim strings — then **adapted** into a canonical
:class:`~orbit_formats.canonical.ephemeris.Ephemeris` (or
:class:`~orbit_formats.canonical.state.StateVector` for a single row) by recognising the
epoch column and the first Cartesian state. The report's frame and time scale are tagged
**only where the column names declare them** (the coordinate-system segment, the epoch-scale
suffix); a column GMAT writes without a coordinate system, or in GMAT's ``A1`` scale that the
canonical spine does not carry, leaves that tag unset rather than guessed. Frames are tagged,
never rotated (per the v0.1 scope). Every column the canonical form cannot place — a second
spacecraft, Keplerian elements, mass — is preserved on the fidelity model, never dropped.

The GMAT report has no content signature, so it is detected by its ``.report`` extension or
named with an explicit ``format="gmat-report"``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import ClassVar, Literal

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import TIME_SCALES, Metadata, Provenance
from orbit_formats.canonical.state import StateVector
from orbit_formats.errors import MalformedSourceError
from orbit_formats.registry import register_reader
from orbit_formats.source import Source
from orbit_formats.warnings import MissingFieldWarning, warn_lossy

__all__ = ["GmatReportFile", "read_gmat_report"]

# The column separator GMAT uses: two-or-more whitespace. A single space lives *inside* a
# value (the UTCGregorian epoch), so a greedy ``\s+`` would shred epoch columns.
_COLUMN_SEP = re.compile(r"\s{2,}")

# The six Cartesian state components, in canonical order. A report column whose final dotted
# segment is one of these is a Cartesian state parameter (``Sat.EarthMJ2000Eq.X``, ``ISS.VX``).
_POSITION_COMPONENTS = ("X", "Y", "Z")
_VELOCITY_COMPONENTS = ("VX", "VY", "VZ")
_STATE_COMPONENTS = frozenset(_POSITION_COMPONENTS + _VELOCITY_COMPONENTS)

# GMAT epoch columns are ``{scale}{format}``: five scales crossed with two formats. The scale
# is tagged on the canonical spine only when it is one the spine recognises (see TIME_SCALES);
# GMAT's ``A1`` scale is not, so an A1 column stays untagged with its raw name on the model.
_TIME_SCALES = ("A1", "TAI", "UTC", "TT", "TDB")
_GREGORIAN_SCALES = {f"{scale}Gregorian": scale for scale in _TIME_SCALES}
_MODJULIAN_SCALES = {f"{scale}ModJulian": scale for scale in _TIME_SCALES}

# Month abbreviations for the GMAT Gregorian format, mapped explicitly so parsing is
# locale-independent (``%b`` would depend on the active locale).
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}  # fmt: skip

# GMAT's Modified Julian Date epoch: JD 2430000.0 = 1941-01-05 12:00:00 (not the standard
# MJD origin). Cross-check: GMAT MJD 21545.0 is J2000 (2000-01-01 12:00:00).
_GMAT_MJD_EPOCH = np.datetime64("1941-01-05T12:00:00", "ns")
_SECONDS_PER_DAY = 86400.0
_NS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True, eq=False)
class GmatReportFile(FidelityModel):
    """The faithful GMAT report fidelity model: the header and every data cell, verbatim.

    ``columns`` is the header row's tokens in order; ``rows`` is one tuple of raw string
    cells per data row, every column retained as written. Holding the table verbatim is
    complete fidelity — every column the canonical form cannot place (a second spacecraft,
    Keplerian elements, mass) survives here, and a same-format write reconstructs from it.

    ``raw_bytes`` is the verbatim source, kept only when the read opted in via
    ``retain_source=True`` (otherwise ``None``); it is a reference to the already-loaded
    buffer, not a copy.
    """

    format_name: ClassVar[str] = "gmat-report"

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    raw_bytes: bytes | None = None


@dataclass(frozen=True)
class _EpochColumn:
    """A recognised epoch column: its position, name, canonical scale, and serialisation."""

    index: int
    name: str
    scale: str
    kind: Literal["gregorian", "modjulian"]


@dataclass
class _StateGroup:
    """One ``(resource, coordinate system)`` Cartesian state, and where each component sits.

    ``coordinate_system`` is ``None`` when the report names the component without a coordinate
    system (``LEOsat.X``) — GMAT's default frame, which the report does not declare and v0.1
    does not infer. ``components`` maps each present component (``X`` … ``VZ``) to its column
    index; a component absent from the report is absent from the map.
    """

    resource: str
    coordinate_system: str | None
    components: dict[str, int] = field(default_factory=dict)


def read_gmat_report(source: Source) -> Canonical:
    """Read a GMAT ``ReportFile`` into a canonical :class:`Ephemeris` / :class:`StateVector`.

    Parses the table into a :class:`GmatReportFile` fidelity model, retained as
    ``source_native``, then adapts the first Cartesian state and the epoch column into a
    canonical series — a single row yields a :class:`StateVector`, more rows an
    :class:`Ephemeris`. Frame and time scale are tagged where the column names declare them;
    every other column is preserved on the fidelity model. A component the chosen state omits
    (a position-only report, common from GMAT) is filled with NaN and a structured
    :class:`~orbit_formats.warnings.MissingFieldWarning` names it — never a fabricated value.

    Raises :class:`~orbit_formats.errors.MalformedSourceError` for an empty report, a data
    row whose column count disagrees with the header, no recognised epoch column, no Cartesian
    state (no complete X/Y/Z or VX/VY/VZ triplet), or an unparseable epoch or state value.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    report = _parse(source.read_text().lstrip("﻿"))
    if source.retain:
        report = replace(report, raw_bytes=source.read_bytes())
    return _to_canonical(report)


def _parse(text: str) -> GmatReportFile:
    """Scan the report text into the verbatim :class:`GmatReportFile` table."""
    lines = text.splitlines()
    header_index, header = _find_header(lines)
    header_stripped = header.strip()
    columns = tuple(_COLUMN_SEP.split(header_stripped))
    rows: list[tuple[str, ...]] = []
    for offset, raw in enumerate(lines[header_index + 1 :], start=header_index + 2):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == header_stripped:
            continue  # GMAT re-emits the header at mission-sequence segment boundaries
        tokens = tuple(_COLUMN_SEP.split(stripped))
        if len(tokens) != len(columns):
            raise MalformedSourceError(
                f"GMAT report line {offset} has {len(tokens)} column(s) but the header "
                f"declares {len(columns)}"
            )
        rows.append(tokens)
    return GmatReportFile(columns=columns, rows=tuple(rows))


def _find_header(lines: list[str]) -> tuple[int, str]:
    """Return ``(index, line)`` of the first non-blank line — the header row."""
    for index, line in enumerate(lines):
        if line.strip():
            return index, line
    raise MalformedSourceError("the GMAT report is empty: no header row was found")


def _to_canonical(report: GmatReportFile) -> Canonical:
    """Adapt the report table into the canonical state series.

    Selects the epoch column and the first Cartesian state group, builds the position /
    velocity arrays (NaN-filling and warning for any component the group omits), and returns a
    :class:`StateVector` for a single row or an :class:`Ephemeris` otherwise. The whole
    :class:`GmatReportFile` rides along as ``source_native``.
    """
    epoch_columns = _epoch_columns(report.columns)
    if not epoch_columns:
        raise MalformedSourceError(
            "the GMAT report has no recognised epoch column (expected one named like "
            "'<scale>Gregorian' or '<scale>ModJulian')"
        )
    group = _first_state_group(report.columns)
    if group is None:
        raise MalformedSourceError(
            "the GMAT report has no Cartesian state: no coordinate system has a complete "
            "X/Y/Z or VX/VY/VZ triplet"
        )
    epoch_column = _select_epoch_column(epoch_columns, group.resource)
    epochs = _epoch_array(report, epoch_column)
    positions, missing_position = _state_matrix(report, group, _POSITION_COMPONENTS)
    velocities, missing_velocity = _state_matrix(report, group, _VELOCITY_COMPONENTS)
    missing = missing_position + missing_velocity
    if missing:
        warn_lossy(MissingFieldWarning(missing, source_format="gmat-report"), stacklevel=3)
    metadata = _build_metadata(group, epoch_column)
    if len(report.rows) == 1:
        return StateVector(
            metadata=metadata,
            source_native=report,
            epoch=epochs[0],
            position=positions[0],
            velocity=velocities[0],
        )
    return Ephemeris(
        metadata=metadata,
        source_native=report,
        epochs=epochs,
        positions=positions,
        velocities=velocities,
    )


def _epoch_columns(columns: tuple[str, ...]) -> list[_EpochColumn]:
    """Find every recognised epoch column, in column order."""
    found: list[_EpochColumn] = []
    for index, column in enumerate(columns):
        suffix = column.rsplit(".", 1)[-1]
        if suffix in _GREGORIAN_SCALES:
            found.append(_EpochColumn(index, column, _GREGORIAN_SCALES[suffix], "gregorian"))
        elif suffix in _MODJULIAN_SCALES:
            found.append(_EpochColumn(index, column, _MODJULIAN_SCALES[suffix], "modjulian"))
    return found


def _select_epoch_column(epoch_columns: list[_EpochColumn], resource: str) -> _EpochColumn:
    """Prefer the epoch column belonging to the chosen state's resource, else the first."""
    for epoch_column in epoch_columns:
        if epoch_column.name.rsplit(".", 1)[0] == resource:
            return epoch_column
    return epoch_columns[0]


def _first_state_group(columns: tuple[str, ...]) -> _StateGroup | None:
    """The first ``(resource, coordinate system)`` group with a full position or velocity.

    Groups are discovered in column order; a group qualifies once it has a complete X/Y/Z or
    VX/VY/VZ triplet (a lone component is a scalar, not a state). All later groups are left on
    the fidelity model.
    """
    groups: dict[tuple[str, str | None], _StateGroup] = {}
    order: list[tuple[str, str | None]] = []
    for index, column in enumerate(columns):
        parsed = _parse_state_column(column)
        if parsed is None:
            continue
        resource, coordinate_system, component = parsed
        key = (resource, coordinate_system)
        group = groups.get(key)
        if group is None:
            group = _StateGroup(resource, coordinate_system)
            groups[key] = group
            order.append(key)
        group.components.setdefault(component, index)
    for key in order:
        group = groups[key]
        if _has_triplet(group, _POSITION_COMPONENTS) or _has_triplet(group, _VELOCITY_COMPONENTS):
            return group
    return None


def _parse_state_column(column: str) -> tuple[str, str | None, str] | None:
    """Split a column into ``(resource, coordinate system, component)`` if it is a state column.

    ``Sat.EarthMJ2000Eq.X`` → ``("Sat", "EarthMJ2000Eq", "X")``; ``LEOsat.X`` →
    ``("LEOsat", None, "X")`` (default, undeclared frame). Returns ``None`` for any column
    whose final segment is not a Cartesian state component.
    """
    parts = column.split(".")
    if len(parts) < 2:
        return None
    component = parts[-1]
    if component not in _STATE_COMPONENTS:
        return None
    if len(parts) == 2:
        return parts[0], None, component
    return ".".join(parts[:-2]), parts[-2], component


def _has_triplet(group: _StateGroup, triplet: tuple[str, str, str]) -> bool:
    """Whether the group has all three components of ``triplet``."""
    return all(component in group.components for component in triplet)


def _state_matrix(
    report: GmatReportFile, group: _StateGroup, triplet: tuple[str, str, str]
) -> tuple[NDArray[np.float64], list[str]]:
    """Build the ``(n, 3)`` array for one triplet, NaN-filling components the group omits.

    Returns the array and the list of components that were absent (so the caller can warn).
    """
    n = len(report.rows)
    columns: list[NDArray[np.float64]] = []
    missing: list[str] = []
    for component in triplet:
        index = group.components.get(component)
        if index is None:
            missing.append(component)
            columns.append(np.full(n, np.nan, dtype=np.float64))
        else:
            columns.append(_float_column(report, index))
    return np.column_stack(columns).astype(np.float64), missing


def _float_column(report: GmatReportFile, index: int) -> NDArray[np.float64]:
    """Parse one column's cells to ``float64``, raising on a non-numeric value."""
    name = report.columns[index]
    values: list[float] = []
    for row in report.rows:
        token = row[index]
        try:
            values.append(float(token))
        except ValueError as exc:
            raise MalformedSourceError(
                f"non-numeric value {token!r} in GMAT report column {name!r}"
            ) from exc
    return np.array(values, dtype=np.float64)


def _epoch_array(report: GmatReportFile, epoch_column: _EpochColumn) -> NDArray[np.datetime64]:
    """Parse the epoch column's cells to a ``datetime64[ns]`` array."""
    epochs: list[np.datetime64] = []
    for row in report.rows:
        epochs.append(_parse_epoch(row[epoch_column.index], epoch_column))
    return np.array(epochs, dtype="datetime64[ns]")


def _parse_epoch(token: str, epoch_column: _EpochColumn) -> np.datetime64:
    """Parse one epoch cell according to the column's serialisation."""
    if epoch_column.kind == "modjulian":
        return _parse_modjulian(token, epoch_column.name)
    return _parse_gregorian(token, epoch_column.name)


def _parse_gregorian(token: str, column: str) -> np.datetime64:
    """Parse a GMAT Gregorian epoch ``DD Mon YYYY HH:MM:SS.fff`` to ``datetime64[ns]``."""
    parts = token.split()
    if len(parts) != 4:
        raise _epoch_error(token, column, "expected 'DD Mon YYYY HH:MM:SS.fff'")
    day_str, month_str, year_str, time_str = parts
    month = _MONTHS.get(month_str.title())
    if month is None:
        raise _epoch_error(token, column, f"unknown month {month_str!r}")
    fields = time_str.split(":")
    if len(fields) != 3:
        raise _epoch_error(token, column, "expected HH:MM:SS in the time of day")
    try:
        year, day = int(year_str), int(day_str)
        hours, minutes, seconds = int(fields[0]), int(fields[1]), float(fields[2])
        base = np.datetime64(f"{year:04d}-{month:02d}-{day:02d}", "ns")
    except (ValueError, TypeError) as exc:
        raise _epoch_error(token, column, str(exc)) from exc
    offset = hours * 3600 + minutes * 60 + seconds
    return base + np.timedelta64(round(offset * _NS_PER_SECOND), "ns")


def _parse_modjulian(token: str, column: str) -> np.datetime64:
    """Parse a GMAT Modified Julian Date epoch (days since 1941-01-05 12:00:00)."""
    try:
        days = float(token)
    except ValueError as exc:
        raise _epoch_error(token, column, "not a number") from exc
    nanoseconds = round(days * _SECONDS_PER_DAY * _NS_PER_SECOND)
    return _GMAT_MJD_EPOCH + np.timedelta64(nanoseconds, "ns")


def _epoch_error(token: str, column: str, detail: str) -> MalformedSourceError:
    """A uniform parse error for a bad epoch cell."""
    return MalformedSourceError(
        f"could not parse the GMAT epoch {token!r} in column {column!r}: {detail}"
    )


def _build_metadata(group: _StateGroup, epoch_column: _EpochColumn) -> Metadata:
    """Tag the canonical spine from what the column names declare — frame and scale only.

    ``reference_frame`` is the coordinate-system segment (``None`` when the report omitted
    it); ``time_scale`` is the epoch scale when the canonical spine carries it (GMAT's ``A1``
    is not one, so it stays ``None`` with the raw column name preserved on the fidelity model);
    ``object_name`` is the resource. The central body is not declared by a report and is not
    inferred (v0.1).
    """
    time_scale = epoch_column.scale if epoch_column.scale in TIME_SCALES else None
    return Metadata(
        object_name=group.resource,
        reference_frame=group.coordinate_system,
        time_scale=time_scale,
        provenance=Provenance(source_format="gmat-report"),
    )


register_reader("gmat-report", read_gmat_report)
