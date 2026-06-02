"""TLE writer — verbatim echo, or element-level reconstruction of the two element lines.

Two paths:

1. A ``MeanElementSet`` whose ``source_native`` is a
   :class:`~orbit_formats.readers.tle.TleRecord` → the verbatim lines are echoed
   (**byte-identical** for a normalised TLE).
2. Any other ``MeanElementSet`` (the OMM → TLE direction, where ``source_native`` is an
   :class:`~orbit_formats.readers.ccsds_omm.OmmFile`, or a bare set) → line 1 and line 2 are
   **reconstructed** from the mean elements and the TLE bookkeeping, with fresh checksums. The
   reconstruction is *element-level* lossless — a re-read reproduces the same mean elements to
   the TLE's representable precision — and warns, through the lossy-conversion framework, for
   each TLE identifier the source could not supply.

TLE is a mean-element format; a Cartesian state or ephemeris cannot become one without orbit
determination, so a non-``MeanElementSet`` input is rejected.
"""

from __future__ import annotations

import math

import numpy as np

from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.elements import MeanElementSet, ensure_convertible_to_mean_format
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.ccsds_omm import OmmFile, OmmTleParameters
from orbit_formats.readers.tle import TleRecord
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy

__all__ = ["write_tle"]

_TLE_LINE_LEN = 69


def write_tle(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (a :class:`MeanElementSet`) to TLE / 3LE bytes.

    Echoes the verbatim lines when ``obj`` came from a TLE; otherwise reconstructs them from
    the mean elements (the OMM → TLE direction). Raises
    :class:`~orbit_formats.errors.UnsupportedConversionError` if ``obj`` is not a
    ``MeanElementSet`` — a TLE is a mean-element set, and fitting one to a state is orbit
    determination, not a format conversion. ``suffix`` is unused (TLE has one notation).
    """
    del suffix
    if not isinstance(obj, MeanElementSet):
        raise UnsupportedConversionError(type(obj).__name__, "tle", "mean-elements")
    ensure_convertible_to_mean_format(obj, "tle")
    native = obj.source_native
    if isinstance(native, TleRecord):
        return _echo(native)
    return _reconstruct(obj, native.tle_parameters if isinstance(native, OmmFile) else None)


def _echo(record: TleRecord) -> bytes:
    """Reproduce the source TLE / 3LE lines verbatim (byte-identical for a normalised TLE)."""
    lines = [record.name] if record.name else []
    lines.extend((record.line1, record.line2))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _reconstruct(meanset: MeanElementSet, tle: OmmTleParameters | None) -> bytes:
    """Build line 1 and line 2 from the mean elements and the TLE bookkeeping, with checksums."""
    catalog = _catalog_number(meanset, tle)
    classification = (tle.classification_type if tle is not None else None) or "U"
    designator = _international_designator(meanset.metadata.object_id)
    ephemeris_type = tle.ephemeris_type if tle is not None and tle.ephemeris_type is not None else 0
    element_set_no = _element_set_no(tle)
    rev_at_epoch = tle.rev_at_epoch if tle is not None and tle.rev_at_epoch is not None else 0

    line1 = (
        f"1 {catalog:>5}{classification:1} {designator:<8} "
        f"{_format_epoch(meanset.epoch)} "
        f"{_format_first_derivative(meanset.mean_motion_dot)} "
        f"{_format_exponential(meanset.mean_motion_ddot)} "
        f"{_format_exponential(meanset.bstar)} "
        f"{ephemeris_type:1} {element_set_no:>4}"
    )
    line2 = (
        f"2 {catalog:>5} "
        f"{_format_angle(meanset.inclination)} "
        f"{_format_angle(meanset.raan)} "
        f"{_format_eccentricity(meanset.eccentricity)} "
        f"{_format_angle(meanset.arg_periapsis)} "
        f"{_format_angle(meanset.mean_anomaly)} "
        f"{_format_mean_motion(meanset.mean_motion)}{rev_at_epoch:>5}"
    )
    line1 = _with_checksum(line1)
    line2 = _with_checksum(line2)
    name = meanset.metadata.object_name
    lines = [name] if name else []
    lines.extend((line1, line2))
    return ("\n".join(lines) + "\n").encode("utf-8")


# --- field formatters ------------------------------------------------------------------


def _catalog_number(meanset: MeanElementSet, tle: OmmTleParameters | None) -> int:
    if tle is not None and tle.norad_cat_id is not None:
        return tle.norad_cat_id
    object_id = meanset.metadata.object_id
    if object_id is not None and object_id.isdigit():
        return int(object_id)
    _warn_dropped("NORAD_CAT_ID", "the source supplied no catalog number; wrote 0")
    return 0


def _element_set_no(tle: OmmTleParameters | None) -> int:
    if tle is not None and tle.element_set_no is not None:
        return tle.element_set_no
    _warn_dropped("ELEMENT_SET_NO", "the source supplied no element-set number; wrote 0")
    return 0


def _international_designator(object_id: str | None) -> str:
    """The TLE launch-designator field (``98067A``) from the OMM ``OBJECT_ID`` (``1998-067A``)."""
    if object_id is not None and "-" in object_id:
        year, _, rest = object_id.partition("-")
        if len(year) == 4 and year.isdigit():
            return f"{year[2:]}{rest}"
    if object_id is not None and object_id.isdigit():
        # A bare catalog number is not a launch designator; the field is left blank.
        _warn_dropped(
            "OBJECT_ID", "the source object id is not an international designator; left blank"
        )
        return ""
    return object_id or ""


def _format_epoch(epoch: np.datetime64) -> str:
    """Format an epoch as the TLE ``YYDDD.dddddddd`` field (14 characters)."""
    moment = epoch.astype("datetime64[ns]")
    year = int(moment.astype("datetime64[Y]").astype(int)) + 1970
    year_start = np.datetime64(f"{year:04d}-01-01", "ns")
    seconds_into_year = (moment - year_start).astype("timedelta64[ns]").astype(np.int64) / 1e9
    day_of_year = seconds_into_year / 86400.0 + 1.0
    return f"{year % 100:02d}{day_of_year:012.8f}"


def _format_first_derivative(value: float | None) -> str:
    """The ndot/2 field (cols 34-43): a signed decimal fraction, ``-.00002182`` (10 chars)."""
    number = 0.0 if value is None else value
    sign = "-" if number < 0 else " "
    body = f"{abs(number):.8f}"[1:]  # drop the leading "0": "0.00002182" -> ".00002182"
    return f"{sign}{body}"


def _format_exponential(value: float | None) -> str:
    """A TLE assumed-decimal exponential field (8 chars): ``-11606-4`` is ``-0.11606e-4``."""
    number = 0.0 if value is None else value
    if number == 0.0:
        return " 00000-0"
    sign = "-" if number < 0 else " "
    magnitude = abs(number)
    exponent = math.floor(math.log10(magnitude)) + 1
    mantissa = round(magnitude / 10.0**exponent * 1e5)
    if mantissa >= 100000:  # a rounding carry (0.999995 -> 1.00000) bumps the exponent
        mantissa //= 10
        exponent += 1
    exp_sign = "-" if exponent < 0 else "+"
    return f"{sign}{mantissa:05d}{exp_sign}{abs(exponent)}"


def _format_angle(value: float) -> str:
    """An angle field (8 chars): ``NNN.NNNN``, e.g. ``247.4627``."""
    return f"{value % 360.0:8.4f}"


def _format_eccentricity(value: float) -> str:
    """The eccentricity field (7 chars): assumed-decimal digits, ``0006703`` is ``0.0006703``."""
    return f"{round(value * 1e7):07d}"


def _format_mean_motion(value: float) -> str:
    """The mean-motion field (11 chars): ``NN.NNNNNNNN`` rev/day, e.g. ``15.72125391``."""
    return f"{value:11.8f}"


def _with_checksum(line: str) -> str:
    """Pad ``line`` to 68 characters and append its modulo-10 checksum digit."""
    body = f"{line:<68}"[:68]
    total = sum(int(ch) if ch.isdigit() else 1 if ch == "-" else 0 for ch in body)
    return f"{body}{total % 10}"


def _warn_dropped(field: str, reason: str) -> None:
    warn_lossy(
        LossyConversionWarning(
            f"reconstructing a TLE: {reason}",
            dropped=(DroppedField(field, reason),),
        ),
        stacklevel=3,
    )


register_writer("tle", write_tle)
