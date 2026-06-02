"""RINEX navigation reader — the GNSS broadcast ephemeris (``.rnx`` / ``.nav`` / ``.NNn``)
into the canonical form. Read-only: this milestone reads RINEX navigation, it does not
write it.

A RINEX navigation file is a fixed-layout text message: a header (``RINEX VERSION / TYPE``,
``PGM / RUN BY / DATE``, optional ionospheric and time-system corrections, leap seconds,
comments) closed by ``END OF HEADER``, then a sequence of per-satellite broadcast-ephemeris
records. Each record opens with an *epoch line* — the satellite id (system letter + PRN), the
record epoch (the time of clock, ``Toc``), and the three SV-clock polynomial terms — followed
by the constellation's *broadcast-orbit* lines (each up to four ``D19.12`` fields).

The constellations split into two **categories** by how they parameterise the orbit:

- **Keplerian** (GPS ``G``, Galileo ``E``, BeiDou ``C``, QZSS ``J``, NavIC/IRNSS ``I``) carry
  quasi-Keplerian parameters (``sqrt(A)``, ``e``, ``i0``, ``Omega0``, ``omega``, ``M0``, plus
  ``Delta n`` and the harmonic corrections) over seven broadcast-orbit lines. These adapt to a
  canonical :class:`~orbit_formats.canonical.elements.MeanElementSet` — the headline mean
  elements, with the mean motion derived from ``sqrt(A)`` and ``Delta n`` via the
  constellation's gravitational parameter. The set is tagged
  :data:`~orbit_formats.canonical.elements.BROADCAST_MEAN_ELEMENT_THEORY`: these are *broadcast*
  elements (Toe-referenced, Earth-fixed), **not** SGP4/TEME elements, so the conversion layer
  refuses converting them to a TLE / OMM (that would need a propagate-and-refit).
- **Cartesian** (GLONASS ``R``, SBAS ``S``) carry an Earth-fixed position / velocity /
  acceleration over three broadcast-orbit lines. These adapt to a canonical
  :class:`~orbit_formats.canonical.state.StateVector` (position and velocity; the acceleration
  rides on the fidelity model).

Every record is parsed into a faithful :class:`RinexNav` fidelity model — the header and every
record's verbatim clock and broadcast-orbit fields — then **adapted**. RINEX navigation is an
Earth-centred, Earth-fixed product, so the canonical frame is tagged **ITRF** (the specific
datum — WGS-84, PZ-90, GTRF, CGCS2000 — is constellation-specific and inferable from the
satellite id) with **Earth** as the central body; the time scale is the constellation's epoch
time system when the canonical spine carries it (GPS → ``GPS``, GLONASS → ``UTC``), else left
unset (Galileo / BeiDou / QZSS / NavIC system time the spine does not model). Constellation-
specific fields the canonical form has no slot for — the harmonic corrections, ``Toe`` and the
broadcast week, health, group delays, the clock polynomial — are preserved on the fidelity
model, never dropped.

A multi-record file maps to a **record set**: the public :func:`~orbit_formats.read` returns the
*first* record as its canonical object (the whole :class:`RinexNav` rides along as
``source_native``), and :meth:`RinexNav.to_canonical` materialises every record's canonical
object in file order.

Detection is by the ``RINEX VERSION / TYPE`` content signature or the ``.rnx`` / ``.nav`` /
``.NNn`` extension (both already catalogued); the reader parses RINEX **3.x** and raises
:class:`~orbit_formats.errors.MalformedSourceError` for RINEX 2.x / 4.x, a missing or malformed
header, an unknown constellation, a truncated record, or a non-numeric field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import ClassVar

import numpy as np

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.elements import BROADCAST_MEAN_ELEMENT_THEORY, MeanElementSet
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.canonical.state import StateVector
from orbit_formats.errors import MalformedSourceError
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["BroadcastEphemeris", "RinexNav", "read_rinex_nav"]

# RINEX navigation is an Earth-centred, Earth-fixed product. The canonical frame is the
# generic ITRF the conversion layer knows; the specific datum (WGS-84 for GPS, PZ-90 for
# GLONASS, GTRF for Galileo, CGCS2000 for BeiDou) follows from the constellation.
_ITRF = "ITRF"
_EARTH = "Earth"
_SOURCE_FORMAT = "rinex-nav"

_NS_PER_SECOND = 1_000_000_000
_SECONDS_PER_DAY = 86_400.0
_TWO_PI = 2.0 * np.pi

# The number of broadcast-orbit lines that follow a record's epoch line, per constellation.
# The Keplerian constellations carry seven; the Cartesian (GLONASS / SBAS) carry three.
_KEPLERIAN_SYSTEMS = frozenset("GECJI")
_CARTESIAN_SYSTEMS = frozenset("RS")
_ORBIT_LINES = {sys: 7 for sys in _KEPLERIAN_SYSTEMS} | {sys: 3 for sys in _CARTESIAN_SYSTEMS}

# Gravitational parameters (m^3/s^2) each constellation's broadcast user algorithm assumes.
# GPS / QZSS / NavIC use the GPS (WGS-84) value; Galileo and BeiDou use the slightly different
# value from their respective interface control documents.
_GM_M3_S2 = {
    "G": 3.986005e14,
    "J": 3.986005e14,
    "I": 3.986005e14,
    "E": 3.986004418e14,
    "C": 3.986004418e14,
}

# The positions of named fields in a flattened broadcast-orbit tuple (four fields per line, in
# file order). The Keplerian layout is shared by GPS / Galileo / BeiDou / QZSS / NavIC; the
# Cartesian layout by GLONASS / SBAS. Only the orbit-determining fields are named — the rest
# (codes, week, health, group delays) ride on the tuple by index, preserved verbatim.
_KEPLERIAN_FIELDS = {
    "IODE": 0, "Crs": 1, "delta_n": 2, "M0": 3,
    "Cuc": 4, "e": 5, "Cus": 6, "sqrt_a": 7,
    "Toe": 8, "Cic": 9, "Omega0": 10, "Cis": 11,
    "i0": 12, "Crc": 13, "omega": 14, "OmegaDot": 15,
    "IDOT": 16,
}  # fmt: skip
_CARTESIAN_FIELDS = {
    "X": 0, "VX": 1, "AX": 2, "health": 3,
    "Y": 4, "VY": 5, "AY": 6, "freq_number": 7,
    "Z": 8, "VZ": 9, "AZ": 10, "age": 11,
}  # fmt: skip

_SAT_ID_RE = re.compile(r"^[A-Z]\d{2}$")
# Header lines carry their label in columns 61-80 (a fixed-format key); the content is 1-60.
_LABEL_COL = 60


@dataclass(frozen=True, slots=True)
class BroadcastEphemeris:
    """One broadcast-ephemeris record: the satellite, the epoch, and its verbatim fields.

    ``system`` is the one-letter constellation code (``"G"`` GPS, ``"R"`` GLONASS, ``"E"``
    Galileo, ``"C"`` BeiDou, ``"J"`` QZSS, ``"I"`` NavIC, ``"S"`` SBAS); ``sat_id`` is the
    full id (``"G01"``). ``epoch`` is the record's time of clock (``Toc``) as
    ``datetime64[ns]``, in the constellation's epoch time system. ``clock`` is the three
    SV-clock polynomial terms from the epoch line — for the Keplerian systems the clock bias /
    drift / drift-rate (``af0`` / ``af1`` / ``af2``); for GLONASS ``-TauN`` / ``+GammaN`` /
    the message frame time. ``orbit`` is the flattened broadcast-orbit fields verbatim, in file
    order, with a blank field kept as ``NaN``.

    :meth:`field` reads a named field (``"sqrt_a"``, ``"M0"``, ``"X"`` …) by the constellation's
    layout; the harmonic corrections, week, health, and group delays the canonical form has no
    slot for stay here on ``orbit`` rather than being dropped.
    """

    system: str
    sat_id: str
    epoch: np.datetime64
    clock: tuple[float, float, float]
    orbit: tuple[float, ...]

    @property
    def is_keplerian(self) -> bool:
        """Whether this record carries Keplerian elements (adapts to a ``MeanElementSet``)."""
        return self.system in _KEPLERIAN_SYSTEMS

    @property
    def is_cartesian(self) -> bool:
        """Whether this record carries an Earth-fixed state (adapts to a ``StateVector``)."""
        return self.system in _CARTESIAN_SYSTEMS

    def field(self, name: str) -> float:
        """The named broadcast field for this constellation's layout, e.g. ``field("sqrt_a")``.

        Raises :class:`KeyError` for a name the constellation's layout does not define.
        """
        layout = _KEPLERIAN_FIELDS if self.is_keplerian else _CARTESIAN_FIELDS
        return self.orbit[layout[name]]


@dataclass(frozen=True, eq=False)
class RinexNav(FidelityModel):
    """The faithful RINEX-navigation fidelity model: the header and every broadcast record.

    ``version`` is the RINEX version string (``"3.04"``); ``file_type`` is the version line's
    type character (``"N"`` for navigation); ``satellite_system`` is its system character
    (``"M"`` for a mixed file, else the single constellation). ``program`` / ``run_by`` /
    ``date`` come from the ``PGM / RUN BY / DATE`` line; ``leap_seconds`` from ``LEAP SECONDS``;
    ``ionospheric_corrections`` and ``time_system_corrections`` keep the raw ``IONOSPHERIC CORR``
    / ``TIME SYSTEM CORR`` lines verbatim; ``comments`` the header ``COMMENT`` lines.
    ``records`` is every broadcast-ephemeris record in file order.

    ``raw_bytes`` is the verbatim source, kept only when the read opted in via
    ``retain_source=True`` (otherwise ``None``).
    """

    format_name: ClassVar[str] = "rinex-nav"

    version: str
    file_type: str
    satellite_system: str
    records: tuple[BroadcastEphemeris, ...]
    program: str | None = None
    run_by: str | None = None
    date: str | None = None
    leap_seconds: int | None = None
    ionospheric_corrections: tuple[str, ...] = ()
    time_system_corrections: tuple[str, ...] = ()
    comments: tuple[str, ...] = ()
    raw_bytes: bytes | None = None

    def to_canonical(self) -> list[Canonical]:
        """Every record's canonical object — a ``MeanElementSet`` or ``StateVector`` — in order.

        Each carries this whole :class:`RinexNav` as its ``source_native`` handle; the Keplerian
        records come back tagged with the broadcast mean-element theory, the Cartesian ones as
        Earth-fixed states.
        """
        return [self._record_to_canonical(record) for record in self.records]

    def _record_to_canonical(self, record: BroadcastEphemeris) -> Canonical:
        if record.is_keplerian:
            return self._mean_element_set(record)
        return self._state_vector(record)

    def _mean_element_set(self, record: BroadcastEphemeris) -> MeanElementSet:
        sqrt_a = record.field("sqrt_a")
        eccentricity = record.field("e")
        if not np.isfinite(sqrt_a) or sqrt_a <= 0.0:
            raise MalformedSourceError(
                f"broadcast record {record.sat_id!r} has an invalid sqrt(A): {sqrt_a!r}"
            )
        if not 0.0 <= eccentricity < 1.0:
            raise MalformedSourceError(
                f"broadcast record {record.sat_id!r} has an eccentricity outside [0, 1): "
                f"{eccentricity!r}"
            )
        semi_major_axis = sqrt_a * sqrt_a
        mean_motion_rad_s = np.sqrt(_GM_M3_S2[record.system] / semi_major_axis**3)
        corrected = mean_motion_rad_s + record.field("delta_n")
        metadata = Metadata(
            object_name=record.sat_id,
            object_id=record.sat_id,
            reference_frame=_ITRF,
            central_body=_EARTH,
            time_scale=_canonical_time_scale(record.system),
            provenance=Provenance(source_format=_SOURCE_FORMAT),
        )
        return MeanElementSet(
            metadata=metadata,
            source_native=self,
            epoch=record.epoch,
            mean_motion=float(corrected * _SECONDS_PER_DAY / _TWO_PI),
            eccentricity=float(eccentricity),
            inclination=float(np.degrees(record.field("i0"))),
            raan=float(np.degrees(record.field("Omega0"))),
            arg_periapsis=float(np.degrees(record.field("omega"))),
            mean_anomaly=float(np.degrees(record.field("M0"))),
            mean_element_theory=BROADCAST_MEAN_ELEMENT_THEORY,
        )

    def _state_vector(self, record: BroadcastEphemeris) -> StateVector:
        position = np.array(
            [record.field("X"), record.field("Y"), record.field("Z")], dtype=np.float64
        )
        velocity = np.array(
            [record.field("VX"), record.field("VY"), record.field("VZ")], dtype=np.float64
        )
        metadata = Metadata(
            object_name=record.sat_id,
            object_id=record.sat_id,
            reference_frame=_ITRF,
            central_body=_EARTH,
            time_scale=_canonical_time_scale(record.system),
            provenance=Provenance(source_format=_SOURCE_FORMAT),
        )
        return StateVector(
            metadata=metadata,
            source_native=self,
            epoch=record.epoch,
            position=position,
            velocity=velocity,
        )


def _canonical_time_scale(system: str) -> str | None:
    """The constellation's epoch time scale when the canonical spine carries it, else ``None``.

    GPS epochs are in GPS time and GLONASS epochs in UTC — both carried by the spine. Galileo,
    BeiDou, QZSS, and NavIC use a system time the spine does not model; those stay unset, the
    same conservative rule the SP3 reader follows for its GNSS time systems.
    """
    if system == "G":
        return "GPS"
    if system == "R":
        return "UTC"
    return None


def read_rinex_nav(source: Source) -> Canonical:
    """Read a RINEX navigation file into the canonical form.

    Parses the header and every broadcast record into a :class:`RinexNav` fidelity model,
    retained as ``source_native``, then returns the **first** record's canonical object — a
    :class:`~orbit_formats.canonical.elements.MeanElementSet` for a Keplerian constellation
    (GPS / Galileo / BeiDou / QZSS / NavIC) or a
    :class:`~orbit_formats.canonical.state.StateVector` for a Cartesian one (GLONASS / SBAS),
    tagged ITRF / Earth and the constellation's epoch time system. The full record set is
    available via :meth:`RinexNav.to_canonical`.

    Raises :class:`~orbit_formats.errors.MalformedSourceError` for RINEX 2.x / 4.x, a missing
    or malformed header, an unknown constellation, a truncated record, a non-numeric field, or
    a file with no broadcast records. When the source opted into retention
    (``read(..., retain_source=True)``), the verbatim bytes are kept on the fidelity model.
    """
    rinex = _parse(source.read_text().lstrip("﻿").splitlines())
    if source.retain:
        rinex = replace(rinex, raw_bytes=source.read_bytes())
    if not rinex.records:
        raise MalformedSourceError("the RINEX navigation file has no broadcast records")
    return rinex._record_to_canonical(rinex.records[0])


def _parse(lines: list[str]) -> RinexNav:
    """Scan the RINEX navigation lines into the faithful :class:`RinexNav` model."""
    header, body_start = _parse_header(lines)
    records = _parse_records(lines, body_start)
    return replace(header, records=tuple(records))


def _parse_header(lines: list[str]) -> tuple[RinexNav, int]:
    """Parse the header lines into a record-less :class:`RinexNav`, and the body start index."""
    if not lines:
        raise MalformedSourceError("not a RINEX file: the input is empty")
    version, file_type, satellite_system = _parse_version_line(lines[0])
    program = run_by = date = None
    leap_seconds: int | None = None
    ionospheric: list[str] = []
    time_system: list[str] = []
    comments: list[str] = []
    for index, raw in enumerate(lines[1:], start=2):
        label = raw[_LABEL_COL:].strip()
        content = raw[:_LABEL_COL]
        if label == "END OF HEADER":
            body_start = index  # 1-based line number of END OF HEADER; body is the next line
            break
        if label == "PGM / RUN BY / DATE":
            program = content[0:20].strip() or None
            run_by = content[20:40].strip() or None
            date = content[40:60].strip() or None
        elif label == "COMMENT":
            comments.append(content.rstrip())
        elif label == "IONOSPHERIC CORR":
            ionospheric.append(content.rstrip())
        elif label == "TIME SYSTEM CORR":
            time_system.append(content.rstrip())
        elif label == "LEAP SECONDS":
            leap_seconds = _parse_leap_seconds(content)
    else:
        raise MalformedSourceError("the RINEX header has no 'END OF HEADER' line")
    header = RinexNav(
        version=version,
        file_type=file_type,
        satellite_system=satellite_system,
        records=(),
        program=program,
        run_by=run_by,
        date=date,
        leap_seconds=leap_seconds,
        ionospheric_corrections=tuple(ionospheric),
        time_system_corrections=tuple(time_system),
        comments=tuple(comments),
    )
    return header, body_start


def _parse_version_line(line: str) -> tuple[str, str, str]:
    """Parse the ``RINEX VERSION / TYPE`` line into (version, file type, satellite system)."""
    if line[_LABEL_COL:].strip() != "RINEX VERSION / TYPE":
        raise MalformedSourceError("not a RINEX file: the first line is not 'RINEX VERSION / TYPE'")
    version = line[0:9].strip()
    try:
        version_number = float(version)
    except ValueError as exc:
        raise MalformedSourceError(f"unparseable RINEX version {version!r}") from exc
    if not 3.0 <= version_number < 4.0:
        raise MalformedSourceError(
            f"unsupported RINEX version {version!r}; this reader parses RINEX 3.x navigation"
        )
    file_type = line[20:21].strip().upper()
    if file_type != "N":
        raise MalformedSourceError(
            f"not a RINEX navigation file: expected file type 'N', got {file_type!r}"
        )
    satellite_system = line[40:41].strip().upper() or "G"
    return version, file_type, satellite_system


def _parse_leap_seconds(content: str) -> int | None:
    tokens = content.split()
    if not tokens:
        return None
    try:
        return int(tokens[0])
    except ValueError:
        return None


def _parse_records(lines: list[str], body_start: int) -> list[BroadcastEphemeris]:
    """Read the body into broadcast records, consuming each record's continuation lines."""
    records: list[BroadcastEphemeris] = []
    index = body_start  # 0-based index of the first body line (END OF HEADER was 1-based)
    total = len(lines)
    while index < total:
        if not lines[index].strip():
            index += 1
            continue
        record, index = _parse_record(lines, index)
        records.append(record)
    return records


def _parse_record(lines: list[str], start: int) -> tuple[BroadcastEphemeris, int]:
    """Parse one record (epoch line + the constellation's orbit lines), returning the next index."""
    epoch_line = lines[start]
    sat_id = epoch_line[0:3].strip()
    if not _SAT_ID_RE.match(sat_id):
        raise MalformedSourceError(
            f"line {start + 1}: expected a broadcast epoch line (a satellite id), got "
            f"{epoch_line[0:3]!r}"
        )
    system = sat_id[0]
    if system not in _ORBIT_LINES:
        raise MalformedSourceError(f"line {start + 1}: unknown RINEX constellation {system!r}")
    epoch = _parse_epoch(epoch_line, start + 1)
    clock = _parse_fields(epoch_line, start + 1, count=3)
    n_orbit = _ORBIT_LINES[system]
    last = start + n_orbit
    if last >= len(lines):
        raise MalformedSourceError(
            f"line {start + 1}: broadcast record {sat_id!r} is truncated; expected "
            f"{n_orbit} broadcast-orbit line(s)"
        )
    orbit: list[float] = []
    for offset in range(1, n_orbit + 1):
        orbit.extend(_parse_fields(lines[start + offset], start + 1 + offset, count=4))
    record = BroadcastEphemeris(
        system=system,
        sat_id=sat_id,
        epoch=epoch,
        clock=(clock[0], clock[1], clock[2]),
        orbit=tuple(orbit),
    )
    return record, last + 1


def _parse_epoch(line: str, line_number: int) -> np.datetime64:
    """Parse a record's epoch (``Toc``) from the epoch line's ``yyyy mm dd hh mm ss`` field."""
    tokens = line[3:23].split()
    if len(tokens) != 6:
        raise MalformedSourceError(
            f"line {line_number}: expected a 'yyyy mm dd hh mm ss' epoch, got {line[3:23]!r}"
        )
    try:
        year, month, day = int(tokens[0]), int(tokens[1]), int(tokens[2])
        hours, minutes, seconds = int(tokens[3]), int(tokens[4]), float(tokens[5])
        base = np.datetime64(f"{year:04d}-{month:02d}-{day:02d}", "ns")
    except (ValueError, TypeError) as exc:
        raise MalformedSourceError(
            f"line {line_number}: unparseable RINEX epoch {line[3:23]!r}: {exc}"
        ) from exc
    offset = hours * 3600 + minutes * 60 + seconds
    return base + np.timedelta64(round(offset * _NS_PER_SECOND), "ns")


def _parse_fields(line: str, line_number: int, *, count: int) -> list[float]:
    """Parse ``count`` fixed-width ``D19.12`` float fields from a clock or broadcast-orbit line.

    Fields sit at columns 24-42, 43-61, 62-80 (a clock line), preceded by 5-23 (an orbit line).
    Fixed-width slicing — not whitespace splitting — is mandatory: two negative ``D19.12``
    values abut with no separating space. A blank field is kept as ``NaN``; a non-numeric field
    raises :class:`~orbit_formats.errors.MalformedSourceError`.
    """
    # An orbit line has a leading 5-23 field; a clock line's three fields start at 24.
    starts = (4, 23, 42, 61) if count == 4 else (23, 42, 61)
    values: list[float] = []
    for begin in starts:
        values.append(_parse_float(line[begin : begin + 19], line_number))
    return values


def _parse_float(field: str, line_number: int) -> float:
    """Parse one RINEX ``D``-exponent float field; a blank field is ``NaN``."""
    text = field.strip()
    if not text:
        return float("nan")
    try:
        return float(text.replace("D", "E").replace("d", "e"))
    except ValueError as exc:
        raise MalformedSourceError(
            f"line {line_number}: non-numeric RINEX field {field!r}"
        ) from exc


register_reader("rinex-nav", read_rinex_nav)
