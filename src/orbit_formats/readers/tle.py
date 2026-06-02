"""TLE reader — two-line element sets into a mean-element fidelity model (sgp4-backed).

A TLE is fully defined by its two 69-character lines (plus an optional name line), so the
fidelity model :class:`TleRecord` holds them verbatim: complete fidelity a future
byte-lossless writer can reconstruct from. The mean elements the canonical
:class:`~orbit_formats.canonical.elements.MeanElementSet` exposes are *derived* from those
lines via ``sgp4`` — the elements stay **mean** (TEME / UTC), never osculating. The single
SGP4 state at the TLE epoch is reachable through :meth:`TleRecord.epoch_state`; nothing is
propagated past the epoch (that is a propagation, not a format conversion, and is the
caller's job).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from sgp4.api import Satrec

from orbit_formats.canonical.elements import SGP4_MEAN_ELEMENT_THEORY, MeanElementSet
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.canonical.state import StateVector
from orbit_formats.errors import MalformedSourceError
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["TleRecord", "read_tle"]

# A TLE element line is exactly 69 characters wide, with the line number in column 1.
_TLE_LINE_LEN = 69

# sgp4 stores angular rates internally in rad/min; the TLE (and OMM) convention is
# rev/day. rev/day = rad/min * 1440 (min/day) / 2pi (rad/rev). The derivative fields carry
# one extra 1/min per order, recovered by the matching power of 1440.
_REV_DAY_PER_RAD_MIN = 1440.0 / (2.0 * math.pi)
_MIN_PER_DAY = 1440.0

# Julian Date of the Unix epoch (1970-01-01T00:00:00 UTC), for JD -> datetime64.
_JD_UNIX_EPOCH = 2440587.5

# A TLE is a geocentric, TEME-frame, UTC-epoch mean-element set.
_FRAME = "TEME"
_CENTRAL_BODY = "Earth"
_TIME_SCALE = "UTC"


@dataclass(frozen=True)
class TleRecord(FidelityModel):
    """The faithful TLE fidelity model: the raw element-set lines, kept verbatim.

    ``line1`` / ``line2`` are the two 69-character element lines and ``name`` the optional
    3LE name line. Holding the lines verbatim is complete TLE fidelity, so a same-format
    write can reconstruct the source byte-for-byte. :meth:`epoch_state` exposes the single
    SGP4 Cartesian state at the element-set epoch (TEME / UTC), the one state a TLE can
    yield without propagating.
    """

    format_name: ClassVar[str] = "tle"

    line1: str
    line2: str
    name: str | None = None

    @property
    def norad_catalog_number(self) -> int:
        """The NORAD catalog number (line 1, columns 3-7)."""
        return int(self.line1[2:7])

    @property
    def classification(self) -> str:
        """The security classification character (line 1, column 8) — ``U`` / ``C`` / ``S``."""
        return self.line1[7]

    @property
    def ephemeris_type(self) -> int:
        """The ephemeris type (line 1, column 63); ``0`` for the standard SGP4/SDP4 set."""
        field = self.line1[62].strip()
        return int(field) if field else 0

    @property
    def element_set_number(self) -> int:
        """The element-set number (line 1, columns 65-68)."""
        return int(self.line1[64:68])

    @property
    def revolution_number_at_epoch(self) -> int:
        """The revolution number at the epoch (line 2, columns 64-68)."""
        return int(self.line2[63:68])

    @property
    def international_designator(self) -> str | None:
        """The launch designator in the OMM ``OBJECT_ID`` form (e.g. ``1998-067A``).

        Reformats the TLE's two-digit-year field (line 1, columns 10-17) — ``98067A`` becomes
        ``1998-067A`` — resolving the year by the standard pivot (57-99 → 19xx, 00-56 → 20xx).
        Returns ``None`` when the designator field is blank, as it is for some catalog entries.
        """
        field = self.line1[9:17].strip()
        if not field:
            return None
        year_two_digit = int(field[:2])
        century = 1900 if year_two_digit >= 57 else 2000
        return f"{century + year_two_digit}-{field[2:].strip()}"

    def epoch_state(self) -> StateVector:
        """The single SGP4 Cartesian state at the TLE epoch (TEME, km / km·s⁻¹).

        Evaluates SGP4 at ``tsince = 0`` — the element-set epoch — and no further; turning
        a TLE into a state at any *other* time is a propagation, out of scope for the
        format layer. Raises :class:`~orbit_formats.errors.MalformedSourceError` if SGP4
        cannot evaluate the epoch state.
        """
        satrec = _parse(self.line1, self.line2)
        error, position, velocity = satrec.sgp4(satrec.jdsatepoch, satrec.jdsatepochF)
        if error != 0:  # pragma: no cover - sgp4 does not fail at the epoch of a parseable TLE
            raise MalformedSourceError(
                f"sgp4 could not evaluate the TLE epoch state (error code {error})"
            )
        return StateVector(
            metadata=_tle_metadata(self.name, self.line1),
            epoch=_epoch_datetime64(satrec),
            position=np.array([float(position[0]), float(position[1]), float(position[2])]),
            velocity=np.array([float(velocity[0]), float(velocity[1]), float(velocity[2])]),
        )


def read_tle(source: Source) -> MeanElementSet:
    """Read a TLE / 3LE into a canonical :class:`MeanElementSet` (mean elements, TEME/UTC).

    Parses the two-line (optionally name-prefixed three-line) element set via ``sgp4``,
    retains the raw lines as ``source_native`` (a :class:`TleRecord`), and tags the result
    TEME / UTC / Earth with the NORAD id on ``metadata.object_id``. The elements stay mean;
    the single epoch state is available via ``result.source_native.epoch_state()``.
    Raises :class:`~orbit_formats.errors.MalformedSourceError` for a missing line, an
    invalid checksum, disagreeing satellite numbers, or elements sgp4 rejects.
    """
    name, line1, line2 = _extract_lines(source.read_text())
    _validate(line1, line2)
    satrec = _parse(line1, line2)
    # mean_motion_dot / _ddot are the TLE-printed first-derivative-over-2 and
    # second-derivative-over-6 drag terms, recovered from sgp4's internal rad/min rates.
    return MeanElementSet(
        metadata=_tle_metadata(name, line1),
        source_native=TleRecord(line1=line1, line2=line2, name=name),
        epoch=_epoch_datetime64(satrec),
        mean_motion=float(satrec.no_kozai) * _REV_DAY_PER_RAD_MIN,
        eccentricity=float(satrec.ecco),
        inclination=math.degrees(float(satrec.inclo)),
        raan=math.degrees(float(satrec.nodeo)),
        arg_periapsis=math.degrees(float(satrec.argpo)),
        mean_anomaly=math.degrees(float(satrec.mo)),
        bstar=float(satrec.bstar),
        mean_motion_dot=float(satrec.ndot) * _REV_DAY_PER_RAD_MIN * _MIN_PER_DAY,
        mean_motion_ddot=float(satrec.nddot) * _REV_DAY_PER_RAD_MIN * _MIN_PER_DAY * _MIN_PER_DAY,
        mean_element_theory=SGP4_MEAN_ELEMENT_THEORY,
    )


def _extract_lines(text: str) -> tuple[str | None, str, str]:
    """Pull the (optional name, line 1, line 2) out of TLE / 3LE text.

    The first ``1 ``/``2 `` element lines are the element set; any non-element line before
    them is the 3LE name (a leading ``0 `` line-zero marker is stripped). Trailing content
    is ignored — a single element set is read. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` if a complete pair is not found.
    """
    name: str | None = None
    line1: str | None = None
    line2: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line1 is None and _is_element_line(line, "1"):
            line1 = line
        elif line2 is None and _is_element_line(line, "2"):
            line2 = line
        elif line1 is None and line2 is None:
            name = _strip_name_marker(line)
    if line1 is None or line2 is None:
        raise MalformedSourceError(
            "could not find a complete two-line element set (a 69-character line 1 and line 2)"
        )
    return name, line1, line2


def _is_element_line(line: str, number: str) -> bool:
    """Whether ``line`` is a TLE element line with the given line number in column 1."""
    return len(line) == _TLE_LINE_LEN and line[0] == number and line[1] == " "


def _strip_name_marker(line: str) -> str:
    """Strip the optional ``0 `` line-zero marker from a 3LE name line."""
    return line[2:].strip() if line.startswith("0 ") else line.strip()


def _validate(line1: str, line2: str) -> None:
    """Reject a structurally-located element set whose content is broken."""
    for number, line in ((1, line1), (2, line2)):
        if not _checksum_ok(line):
            raise MalformedSourceError(f"TLE line {number} has an invalid checksum")
    if line1[2:7] != line2[2:7]:
        raise MalformedSourceError(
            f"TLE line 1 and line 2 satellite numbers disagree ({line1[2:7]!r} vs {line2[2:7]!r})"
        )


def _checksum_ok(line: str) -> bool:
    """A TLE line ends with a mod-10 checksum: digits sum to themselves, ``-`` counts 1."""
    check = line[68]
    if not check.isdigit():
        return False
    total = sum(int(ch) if ch.isdigit() else 1 if ch == "-" else 0 for ch in line[:68])
    return total % 10 == int(check)


def _parse(line1: str, line2: str) -> Satrec:
    """Parse two element lines into an sgp4 ``Satrec``, wrapping any parse failure."""
    try:
        satrec = Satrec.twoline2rv(line1, line2)
    except (ValueError, RuntimeError) as exc:  # pragma: no cover - sgp4-internal parse guard
        raise MalformedSourceError(f"sgp4 could not parse the TLE: {exc}") from exc
    if satrec.error != 0:  # pragma: no cover - bad elements are caught upstream by _validate
        raise MalformedSourceError(f"sgp4 rejected the elements (error code {satrec.error})")
    return satrec


def _epoch_datetime64(satrec: Satrec) -> np.datetime64:
    """The element-set epoch (UTC) as ``datetime64[ns]``.

    sgp4 splits the epoch Julian Date into an integer-ish part and a fraction precisely so
    the two can be combined without losing the sub-second digits a single float64 JD would.
    """
    days = (float(satrec.jdsatepoch) - _JD_UNIX_EPOCH) + float(satrec.jdsatepochF)
    nanoseconds = round(days * 86400.0 * 1_000_000_000)
    return np.datetime64(nanoseconds, "ns")


def _tle_metadata(name: str | None, line1: str) -> Metadata:
    """The shared metadata spine for a TLE: TEME / UTC / Earth, NORAD id from line 1."""
    return Metadata(
        object_name=name,
        object_id=line1[2:7].strip(),
        reference_frame=_FRAME,
        central_body=_CENTRAL_BODY,
        time_scale=_TIME_SCALE,
        provenance=Provenance(source_format="tle"),
    )


register_reader("tle", read_tle)
