"""SP3 reader — the IGS precise GNSS ephemeris (``.sp3``, SP3-c / SP3-d) into a canonical
Ephemeris. Read-only: this milestone reads SP3, it does not write it.

SP3 is a fixed-layout text ephemeris for one *or many* satellites. A header declares the
version (``#c`` / ``#d``), a position-only (``P``) or position-and-velocity (``V``) mode,
the start epoch and epoch count, the reference frame and agency, the GPS week / interval,
the satellite id list with a per-satellite accuracy code, and the **time system** (line
``%c``). The body is a sequence of epochs, each a ``*`` epoch line followed by one ``P``
position record per satellite (km, plus a clock offset in microseconds) and — in ``V``
mode — one ``V`` velocity record (decimetres·s⁻¹, plus a clock rate), terminated by ``EOF``.

The whole file is parsed into a faithful :class:`Sp3File` fidelity model — the header
fields, every satellite's position / velocity / clock series, and the per-satellite
accuracy codes — then **adapted** into the canonical
:class:`~orbit_formats.canonical.ephemeris.Ephemeris`. SP3 is always an Earth-centred,
Earth-fixed product, so the canonical frame is tagged **ITRF** (the specific realisation —
``IGS20``, ``ITR2014`` — is kept on the fidelity model) with **Earth** as the central body;
the time scale is the SP3 time system when the canonical spine carries it (``GPS`` / ``UTC``
/ ``TAI`` / ``TT`` / ``UT1``), else left unset with the raw value on the model. Velocities
are converted decimetres·s⁻¹ → km·s⁻¹; clock offsets and rates ride on the fidelity model
(the canonical ``Ephemeris`` holds position and velocity).

A multi-satellite SP3 maps to a **per-satellite ephemeris set**: the public
:func:`~orbit_formats.read` returns the *first* listed satellite as the canonical
``Ephemeris`` (the whole :class:`Sp3File` rides along as ``source_native``), and
:meth:`Sp3File.ephemerides` materialises every satellite's ``Ephemeris`` keyed by its id.
A position-only (``P``-mode) file fills the canonical velocities with NaN — never a
fabricated value — and a structured
:class:`~orbit_formats.warnings.MissingFieldWarning` names them.

Detection is by the ``#`` + version-letter content signature or the ``.sp3`` extension
(both already catalogued); the reader parses SP3-c and SP3-d and raises
:class:`~orbit_formats.errors.MalformedSourceError` for any other version, a missing or
malformed header, a record with too few columns or a non-numeric value, or a satellite
whose record count disagrees with the epoch count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import TIME_SCALES, Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.registry import register_reader
from orbit_formats.source import Source
from orbit_formats.warnings import MissingFieldWarning, warn_lossy

__all__ = ["Sp3File", "read_sp3"]

# The SP3 versions this reader parses. SP3-c and SP3-d share the system-letter satellite id
# form (``G01``, ``R02``, …); the older SP3-a / SP3-b numeric-PRN forms are out of scope.
_SUPPORTED_VERSIONS = frozenset("cd")

# A satellite id is a one-letter GNSS system code plus a two-digit number (``G01`` GPS,
# ``R02`` GLONASS, ``E03`` Galileo, ``C04`` BeiDou, ``J05`` QZSS, ``I06`` NavIC, ``S07``
# SBAS). Scanning the ``+`` lines for this pattern reads the id list without depending on
# SP3's fixed columns, and never matches the satellite count or the zero fillers beside it.
_SAT_ID_RE = re.compile(r"[A-Z]\d{2}")

# SP3 velocities are decimetres per second; the canonical Ephemeris holds km·s⁻¹.
_DM_S_TO_KM_S = 1e-4

# SP3 is an Earth-centred, Earth-fixed product. The canonical frame is the generic ITRF the
# conversion layer knows (the file's specific realisation stays on the fidelity model).
_ITRF = "ITRF"
_EARTH = "Earth"

_NS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True, eq=False)
class Sp3File(FidelityModel):
    """The faithful SP3 fidelity model: the header, and every satellite's state series.

    ``version`` is the version letter (``"c"`` / ``"d"``); ``mode`` is ``"P"`` (position
    only) or ``"V"`` (position and velocity). The header spine — ``coordinate_system`` (the
    frame realisation, e.g. ``IGS20``), ``orbit_type``, ``agency``, ``data_used``,
    ``gps_week`` / ``seconds_of_week`` / ``epoch_interval`` / ``mjd`` / ``fractional_day``,
    ``file_type``, ``time_system``, the ``%f`` std-dev bases, and the ``/*`` comments — is
    kept verbatim. ``accuracy_codes`` is the per-satellite accuracy exponent from the ``++``
    block, aligned with ``sat_ids``.

    ``epochs`` is ``(n,)`` ``datetime64[ns]``. ``positions`` and ``clocks`` map each
    satellite id to its ``(n, 3)`` km positions and ``(n,)`` microsecond clock offsets;
    ``velocities`` and ``clock_rates`` are the ``(n, 3)`` km·s⁻¹ velocities and ``(n,)`` clock
    rates in ``V`` mode, else ``None``. Use :meth:`ephemerides` for the per-satellite
    canonical set.

    ``raw_bytes`` is the verbatim source, kept only when the read opted in via
    ``retain_source=True`` (otherwise ``None``); it is a reference to the already-loaded
    buffer, not a copy.
    """

    format_name: ClassVar[str] = "sp3"

    version: str
    mode: str
    sat_ids: tuple[str, ...]
    accuracy_codes: tuple[int, ...]
    epochs: NDArray[np.datetime64]
    positions: dict[str, NDArray[np.float64]]
    clocks: dict[str, NDArray[np.float64]]
    velocities: dict[str, NDArray[np.float64]] | None = None
    clock_rates: dict[str, NDArray[np.float64]] | None = None
    coordinate_system: str | None = None
    orbit_type: str | None = None
    agency: str | None = None
    data_used: str | None = None
    file_type: str | None = None
    time_system: str | None = None
    gps_week: int | None = None
    seconds_of_week: float | None = None
    epoch_interval: float | None = None
    mjd: int | None = None
    fractional_day: float | None = None
    std_dev_base_pos: float | None = None
    std_dev_base_clock: float | None = None
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None

    def ephemerides(self) -> dict[str, Ephemeris]:
        """Every satellite's canonical :class:`Ephemeris`, keyed by satellite id.

        Each is tagged ITRF / Earth / the SP3 time scale and carries this whole
        :class:`Sp3File` as ``source_native``; ``object_name`` is the satellite id. The
        position-only velocity-NaN fill (see the module docstring) applies per satellite —
        this accessor does not re-emit the missing-velocity warning the primary
        :func:`read_sp3` already raised.
        """
        return {sat_id: self._satellite_ephemeris(sat_id) for sat_id in self.sat_ids}

    def _satellite_ephemeris(self, sat_id: str) -> Ephemeris:
        positions = self.positions[sat_id]
        if self.velocities is not None:
            velocities = self.velocities[sat_id]
        else:
            velocities = np.full_like(positions, np.nan)
        metadata = Metadata(
            object_name=sat_id,
            reference_frame=_ITRF,
            central_body=_EARTH,
            time_scale=self._canonical_time_scale(),
            provenance=Provenance(source_format="sp3"),
        )
        return Ephemeris(
            metadata=metadata,
            source_native=self,
            epochs=self.epochs,
            positions=positions,
            velocities=velocities,
        )

    def _canonical_time_scale(self) -> str | None:
        """The SP3 time system when the canonical spine carries it, else ``None``.

        ``GPS`` / ``UTC`` / ``TAI`` / ``TT`` / ``UT1`` map straight through; a GNSS system
        time the spine does not model (``GLO`` / ``GAL`` / ``QZS`` / ``BDT`` / ``IRN``) stays
        unset, its raw value preserved as ``time_system`` on this model.
        """
        return self.time_system if self.time_system in TIME_SCALES else None


def read_sp3(source: Source) -> Ephemeris:
    """Read an SP3 (``.sp3``) precise ephemeris into a canonical :class:`Ephemeris`.

    Parses the header and every satellite's records into an :class:`Sp3File` fidelity model,
    retained as ``source_native``, then returns the **first** listed satellite as the
    canonical ephemeris — tagged ITRF / Earth / the SP3 time scale, with the satellite id as
    ``object_name``. The full per-satellite set is available via
    :meth:`Sp3File.ephemerides`. A position-only file fills the velocities with NaN and a
    :class:`~orbit_formats.warnings.MissingFieldWarning` names them.

    Raises :class:`~orbit_formats.errors.MalformedSourceError` for an unsupported SP3
    version, a missing ``#`` header / satellite list / epochs, a record with too few columns
    or a non-numeric value, or a satellite whose record count disagrees with the epoch count.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model.
    """
    sp3 = _parse(source.read_text().lstrip("﻿").splitlines())
    if source.retain:
        sp3 = replace(sp3, raw_bytes=source.read_bytes())
    primary = sp3.sat_ids[0]
    ephemeris = sp3._satellite_ephemeris(primary)
    if sp3.mode == "P":
        warn_lossy(MissingFieldWarning(("VX", "VY", "VZ"), source_format="sp3"), stacklevel=3)
    return ephemeris


def _parse(lines: list[str]) -> Sp3File:
    """Scan the SP3 lines once into the faithful :class:`Sp3File` model."""
    parser = _Sp3Parser()
    for index, raw in enumerate(lines, start=1):
        parser.feed(raw, index)
    return parser.finish()


class _Sp3Parser:
    """A single-pass SP3 scanner, dispatching each line by its leading marker."""

    def __init__(self) -> None:
        self.version: str | None = None
        self.mode: str | None = None
        self.sat_ids: list[str] = []
        self.accuracy_codes: list[int] = []
        self.coordinate_system: str | None = None
        self.orbit_type: str | None = None
        self.agency: str | None = None
        self.data_used: str | None = None
        self.file_type: str | None = None
        self.time_system: str | None = None
        self.gps_week: int | None = None
        self.seconds_of_week: float | None = None
        self.epoch_interval: float | None = None
        self.mjd: int | None = None
        self.fractional_day: float | None = None
        self.std_dev_base_pos: float | None = None
        self.std_dev_base_clock: float | None = None
        self.comments: list[str] = []
        self._seen_c = False
        self._seen_f = False
        self.epochs: list[np.datetime64] = []
        self.positions: dict[str, list[list[float]]] = {}
        self.clocks: dict[str, list[float]] = {}
        self.velocities: dict[str, list[list[float]]] = {}
        self.clock_rates: dict[str, list[float]] = {}
        self._eof = False

    def feed(self, raw: str, index: int) -> None:
        line = raw.rstrip()
        if not line:
            return
        if self._eof:
            raise MalformedSourceError(
                f"line {index}: content after the SP3 'EOF' marker: {line!r}"
            )
        if line == "EOF":
            self._eof = True
        elif line.startswith("##"):
            self._header_line2(line, index)
        elif line.startswith("#"):
            self._header_line1(line, index)
        elif line.startswith("++"):
            self.accuracy_codes.extend(int(token) for token in re.findall(r"-?\d+", line[2:]))
        elif line.startswith("+"):
            self.sat_ids.extend(_SAT_ID_RE.findall(line[1:]))
        elif line.startswith("%c"):
            self._percent_c(line)
        elif line.startswith("%f"):
            self._percent_f(line)
        elif line.startswith("%i"):
            return
        elif line.startswith("/*"):
            self.comments.append(line[2:].strip())
        elif line.startswith("*"):
            self.epochs.append(_parse_epoch(line, index))
        elif line.startswith("P"):
            self._position_record(line, index)
        elif line.startswith("V"):
            self._velocity_record(line, index)
        else:
            raise MalformedSourceError(f"line {index}: unrecognised SP3 line {line!r}")

    def _header_line1(self, line: str, index: int) -> None:
        if self.version is not None:
            raise MalformedSourceError(f"line {index}: a second SP3 '#' header line {line!r}")
        if len(line) < 8:
            raise MalformedSourceError(f"line {index}: truncated SP3 header line {line!r}")
        version = line[1]
        if version not in _SUPPORTED_VERSIONS:
            raise MalformedSourceError(
                f"line {index}: unsupported SP3 version {version!r}; this reader parses "
                "SP3-c and SP3-d"
            )
        mode = line[2]
        if mode not in ("P", "V"):
            raise MalformedSourceError(
                f"line {index}: SP3 mode flag must be 'P' or 'V', got {mode!r}"
            )
        self.version = version
        self.mode = mode
        rest = line[7:].split()
        # rest: month day hour minute second num_epochs data_used coord_sys orbit_type agency
        if len(rest) >= 6:
            self.data_used = rest[6] if len(rest) > 6 else None
            self.coordinate_system = rest[7] if len(rest) > 7 else None
            self.orbit_type = rest[8] if len(rest) > 8 else None
            self.agency = rest[9] if len(rest) > 9 else None

    def _header_line2(self, line: str, index: int) -> None:
        tokens = line[2:].split()
        try:
            if len(tokens) > 0:
                self.gps_week = int(tokens[0])
            if len(tokens) > 1:
                self.seconds_of_week = float(tokens[1])
            if len(tokens) > 2:
                self.epoch_interval = float(tokens[2])
            if len(tokens) > 3:
                self.mjd = int(tokens[3])
            if len(tokens) > 4:
                self.fractional_day = float(tokens[4])
        except ValueError as exc:
            raise MalformedSourceError(
                f"line {index}: malformed SP3 '##' header line: {exc}"
            ) from exc

    def _percent_c(self, line: str) -> None:
        if self._seen_c:
            return  # only the first %c line carries the file type and time system
        self._seen_c = True
        tokens = line.split()
        if len(tokens) > 1:
            self.file_type = tokens[1]
        if len(tokens) > 3:
            self.time_system = tokens[3]

    def _percent_f(self, line: str) -> None:
        if self._seen_f:
            return  # only the first %f line carries the std-dev bases
        self._seen_f = True
        tokens = line.split()
        try:
            if len(tokens) > 1:
                self.std_dev_base_pos = float(tokens[1])
            if len(tokens) > 2:
                self.std_dev_base_clock = float(tokens[2])
        except ValueError:
            self.std_dev_base_pos = None
            self.std_dev_base_clock = None

    def _position_record(self, line: str, index: int) -> None:
        sat_id, values = _parse_state_record(line, index, "position")
        self.positions.setdefault(sat_id, []).append(values[:3])
        self.clocks.setdefault(sat_id, []).append(values[3])

    def _velocity_record(self, line: str, index: int) -> None:
        sat_id, values = _parse_state_record(line, index, "velocity")
        velocity = [component * _DM_S_TO_KM_S for component in values[:3]]
        self.velocities.setdefault(sat_id, []).append(velocity)
        self.clock_rates.setdefault(sat_id, []).append(values[3])

    def finish(self) -> Sp3File:
        if self.version is None or self.mode is None:
            raise MalformedSourceError("not an SP3 file: the '#' version header is missing")
        if not self.sat_ids:
            raise MalformedSourceError("the SP3 header lists no satellites")
        if not self.epochs:
            raise MalformedSourceError("the SP3 file has no epochs")
        n = len(self.epochs)
        epochs = np.array(self.epochs, dtype="datetime64[ns]")
        positions = {sat: _state_matrix(self.positions, sat, n, "position") for sat in self.sat_ids}
        clocks = {sat: _clock_vector(self.clocks, sat, n) for sat in self.sat_ids}
        velocities: dict[str, NDArray[np.float64]] | None = None
        clock_rates: dict[str, NDArray[np.float64]] | None = None
        if self.mode == "V":
            velocities = {
                sat: _state_matrix(self.velocities, sat, n, "velocity") for sat in self.sat_ids
            }
            clock_rates = {sat: _clock_vector(self.clock_rates, sat, n) for sat in self.sat_ids}
        return Sp3File(
            version=self.version,
            mode=self.mode,
            sat_ids=tuple(self.sat_ids),
            accuracy_codes=tuple(self.accuracy_codes[: len(self.sat_ids)]),
            epochs=epochs,
            positions=positions,
            clocks=clocks,
            velocities=velocities,
            clock_rates=clock_rates,
            coordinate_system=self.coordinate_system,
            orbit_type=self.orbit_type,
            agency=self.agency,
            data_used=self.data_used,
            file_type=self.file_type,
            time_system=self.time_system,
            gps_week=self.gps_week,
            seconds_of_week=self.seconds_of_week,
            epoch_interval=self.epoch_interval,
            mjd=self.mjd,
            fractional_day=self.fractional_day,
            std_dev_base_pos=self.std_dev_base_pos,
            std_dev_base_clock=self.std_dev_base_clock,
            comments=tuple(self.comments),
        )


def _parse_epoch(line: str, index: int) -> np.datetime64:
    """Parse a ``*`` epoch line — ``* YYYY MM DD HH MM SS.SSSSSSSS`` — to ``datetime64[ns]``."""
    tokens = line[1:].split()
    if len(tokens) != 6:
        raise MalformedSourceError(
            f"line {index}: expected an SP3 epoch '* YYYY MM DD HH MM SS', got {line!r}"
        )
    try:
        year, month, day = int(tokens[0]), int(tokens[1]), int(tokens[2])
        hours, minutes, seconds = int(tokens[3]), int(tokens[4]), float(tokens[5])
        base = np.datetime64(f"{year:04d}-{month:02d}-{day:02d}", "ns")
    except (ValueError, TypeError) as exc:
        raise MalformedSourceError(f"line {index}: unparseable SP3 epoch {line!r}: {exc}") from exc
    offset = hours * 3600 + minutes * 60 + seconds
    return base + np.timedelta64(round(offset * _NS_PER_SECOND), "ns")


def _parse_state_record(line: str, index: int, kind: str) -> tuple[str, list[float]]:
    """Parse a ``P``/``V`` record into ``(satellite id, [x, y, z, clock])``.

    The record type letter is fused to the id (``PG01``); the first four numeric columns are
    the state and the clock offset (rate). Any trailing std-dev / event-flag columns are
    tolerated and not retained — this milestone reads SP3, it does not re-emit it.
    """
    tokens = line.split()
    sat_id = tokens[0][1:]
    if not sat_id:
        raise MalformedSourceError(f"line {index}: SP3 {kind} record has no satellite id: {line!r}")
    if len(tokens) < 5:
        raise MalformedSourceError(
            f"line {index}: SP3 {kind} record for {sat_id!r} has {len(tokens) - 1} value "
            f"column(s), expected at least 4 (x y z clock)"
        )
    try:
        values = [float(token) for token in tokens[1:5]]
    except ValueError as exc:
        raise MalformedSourceError(
            f"line {index}: non-numeric value in the SP3 {kind} record {line!r}"
        ) from exc
    return sat_id, values


def _state_matrix(
    series: dict[str, list[list[float]]], sat_id: str, n: int, kind: str
) -> NDArray[np.float64]:
    """Stack one satellite's ``(n, 3)`` state, checking its record count matches the epochs."""
    rows = series.get(sat_id, [])
    if len(rows) != n:
        raise MalformedSourceError(
            f"satellite {sat_id!r} has {len(rows)} {kind} record(s) but the SP3 file declares "
            f"{n} epoch(s)"
        )
    return np.array(rows, dtype=np.float64).reshape(n, 3)


def _clock_vector(series: dict[str, list[float]], sat_id: str, n: int) -> NDArray[np.float64]:
    """Stack one satellite's ``(n,)`` clock series (already validated against the epochs)."""
    return np.array(series.get(sat_id, []), dtype=np.float64).reshape(n)


register_reader("sp3", read_sp3)
