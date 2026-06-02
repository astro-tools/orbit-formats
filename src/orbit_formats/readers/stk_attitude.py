"""STK attitude reader — AGI's STK text attitude (``.a``) into a canonical Attitude.

STK's ``.a`` is the attitude analogue of its ``.e`` ephemeris and shares that file's frame:
an ``stk.v.X.Y`` banner, optional ``# …`` comments, then a ``BEGIN Attitude`` block of
whitespace-separated ``KEY VALUE`` meta (``ScenarioEpoch``, ``CentralBody``,
``CoordinateAxes``, ``Sequence``, ``NumberOfAttitudePoints``, ``BlockingFactor``,
``InterpolationOrder`` …) followed by an ``AttitudeTime…`` data section whose records are an
offset-from-epoch in seconds plus the attitude components. So this reader borrows STK
ephemeris' banner, ``ScenarioEpoch`` and offset machinery, and borrows the AEM reader's
canonical attitude shape — quaternion (scalar-last ``Q1 Q2 Q3 QC``) or Euler angles.

Two real-world deviations from AGI's published spec shape the parser. First, AGI documents an
``END Attitude`` terminator as required, but STK output in the wild routinely omits it — the
data section simply runs to end-of-file — so the terminator is treated as **optional** (when
present it closes the block and rejects trailing content; when absent EOF ends the data).
Second, the data sections this reader maps are the ones the canonical
:class:`~orbit_formats.canonical.attitude.Attitude` can hold faithfully:
``AttitudeTimeQuaternions`` (scalar-last) and ``AttitudeTimeQuatScalarFirst`` (scalar-first,
reordered to the canonical scalar-last) into ``QUATERNION``, and ``AttitudeTimeEulerAngles``
(with its ``Sequence``) into ``EULER_ANGLE``. STK's YPR, DCM, angular-velocity / rate,
direction-vector and spin variants have no faithful canonical representation here and are
rejected rather than guessed — the same discipline the AEM reader applies to attitude types it
does not model.

The whole faithful :class:`StkAttitudeFile` is retained as ``source_native`` so a same-format
write stays byte-lossless; the canonical :class:`Attitude` is tagged with the reference frame
(``CoordinateAxes`` → ``frame_a``; the body frame STK leaves implicit is ``frame_b = None``),
the central body, and the UTC default time scale (a ``.a`` declares none, as for ``.e``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from orbit_formats.canonical.attitude import ATTITUDE_TYPES, Attitude
from orbit_formats.canonical.fidelity import FidelityModel
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.errors import MalformedSourceError
from orbit_formats.readers.stk_ephemeris import (
    _VERSION_BANNER_RE,
    _absolute_epochs,
    _meta_value,
    _parse_meta_line,
    _parse_scenario_epoch,
)
from orbit_formats.registry import register_reader
from orbit_formats.source import Source

__all__ = ["StkAttitudeFile", "read_stk_attitude"]

# Block markers. ``BEGIN Attitude`` is mandatory; ``END Attitude`` is optional (real STK
# output omits it — see the module docstring), so a file may simply run to end-of-file.
_BEGIN_ATTITUDE = "BEGIN Attitude"
_END_ATTITUDE = "END Attitude"

# The STK attitude data sections this reader maps, each to its canonical attitude type and the
# quaternion scalar position. ``AttitudeTimeQuaternions`` is scalar-last (``Q1 Q2 Q3 QC`` — the
# canonical order); ``AttitudeTimeQuatScalarFirst`` writes the scalar first and is reordered.
# ``AttitudeTimeEulerAngles`` needs the ``Sequence`` meta keyword. Sections outside this set
# (YPR, DCM, angular-velocity / rate, direction-vector, spin) are recognised but rejected.
_QUATERNION_LAST = "AttitudeTimeQuaternions"
_QUATERNION_FIRST = "AttitudeTimeQuatScalarFirst"
_EULER_ANGLES = "AttitudeTimeEulerAngles"
_SUPPORTED_SECTIONS: dict[str, tuple[str, str | None]] = {
    _QUATERNION_LAST: ("QUATERNION", "last"),
    _QUATERNION_FIRST: ("QUATERNION", "first"),
    _EULER_ANGLES: ("EULER_ANGLE", None),
}

# Meta keys lifted onto the canonical spine. Every other keyword the file declares survives
# verbatim on ``StkAttitudeFile.meta``; these are the ones the canonical form has a slot for.
_META_CENTRAL_BODY = "CentralBody"
_META_COORDINATE_AXES = "CoordinateAxes"
_META_SCENARIO_EPOCH = "ScenarioEpoch"
_META_SEQUENCE = "Sequence"

# A ``.a`` declares no time scale; UTC is STK's default, as for the ``.e`` ephemeris.
_DEFAULT_TIME_SCALE = "UTC"


@dataclass(frozen=True, eq=False)
class StkAttitudeFile(FidelityModel):
    """The faithful STK attitude fidelity model: banner, comments, meta, and records.

    Holds every field a same-format STK-attitude write reconstructs from: ``version`` is the
    ``stk.v.X.Y`` banner, ``header_comments`` the ``# …`` lines above ``BEGIN Attitude``,
    ``data_section`` the ``AttitudeTime…`` header the records were written under, and ``meta``
    every ``BEGIN Attitude`` ``KEY VALUE`` pair in file order (original-case key, verbatim
    value — ``ScenarioEpoch``, ``CentralBody``, ``CoordinateAxes``, ``Sequence``, and every
    keyword this reader does not specially interpret). ``has_end_marker`` records whether the
    source closed the block with ``END Attitude`` so a content-lossless re-serialise reproduces
    that choice.

    ``attitude_type`` is the canonical type (``QUATERNION`` / ``EULER_ANGLE``); ``records`` is
    ``(n, k)`` in the canonical column order (quaternions scalar-last, regardless of the source
    section's ordering). ``epochs`` is ``(n,)`` ``datetime64[ns]`` — the record offsets made
    absolute against ``scenario_epoch``, the offset origin.

    ``raw_bytes`` is the verbatim source, kept only when the read opted in via
    ``retain_source=True`` (otherwise ``None``); the writer echoes it for a byte-identical
    same-format re-emit, and re-serialises this structured model (content-lossless) without it.
    """

    format_name: ClassVar[str] = "stk-attitude"

    version: str
    scenario_epoch: np.datetime64
    attitude_type: str
    data_section: str
    epochs: NDArray[np.datetime64]
    records: NDArray[np.float64]
    meta: tuple[tuple[str, str], ...] = ()
    header_comments: tuple[str, ...] = ()
    has_end_marker: bool = True
    raw_bytes: bytes | None = None

    def meta_value(self, key: str) -> str | None:
        """The value of meta keyword ``key`` (first match, case-sensitive), or ``None``."""
        return _meta_value(list(self.meta), key)


def read_stk_attitude(source: Source) -> Attitude:
    """Read an STK attitude (``.a``) into a canonical :class:`Attitude`.

    Parses the banner, header comments, ``BEGIN Attitude`` meta block, and the
    ``AttitudeTime…`` records into an :class:`StkAttitudeFile` fidelity model, retained as
    ``source_native``, then adapts the records into one canonical attitude tagged with the
    reference frame (``CoordinateAxes``), central body, time scale (UTC — see the module
    docstring), and Euler sequence where present. Raises
    :class:`~orbit_formats.errors.MalformedSourceError` for a missing banner / ``BEGIN
    Attitude`` / ``ScenarioEpoch`` / data section, an unsupported ``AttitudeTime…`` section, an
    Euler section without a ``Sequence``, a record with the wrong column count or a non-numeric
    value, an unparseable ``ScenarioEpoch``, or content after ``END Attitude``.

    When the source opted into retention (``read(..., retain_source=True)``), the verbatim
    bytes are kept on the fidelity model so a same-format write can reproduce them exactly.
    """
    stk = _parse(source.read_text().lstrip("﻿").splitlines())
    if source.retain:
        stk = replace(stk, raw_bytes=source.read_bytes())
    return _to_attitude(stk)


def _parse(lines: list[str]) -> StkAttitudeFile:
    """Scan the ``.a`` lines once into the faithful :class:`StkAttitudeFile` model."""
    version = ""
    comments: list[str] = []
    meta: list[tuple[str, str]] = []
    offsets: list[float] = []
    rows: list[list[float]] = []
    data_section: str | None = None
    attitude_type: str | None = None
    quaternion_pos: str | None = None
    width = 0

    in_attitude = False
    in_data = False
    seen_end = False

    for index, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if seen_end:
            raise MalformedSourceError(f"line {index}: content after END Attitude: {line!r}")

        if not in_attitude:
            # Pre-``BEGIN Attitude``: the version banner first, then optional ``# …`` comments.
            if line == _BEGIN_ATTITUDE:
                if not version:
                    raise MalformedSourceError(
                        f"line {index}: BEGIN Attitude before the stk.v.X.Y banner"
                    )
                in_attitude = True
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
                f"'BEGIN Attitude', got {line!r}"
            )

        if line == _END_ATTITUDE:
            seen_end = True
            in_data = False
            continue

        if not in_data:
            # Inside the block, before the data section: the ``AttitudeTime…`` marker (mapped or
            # rejected), or a meta line.
            if _looks_like_attitude_section(line):
                spec = _SUPPORTED_SECTIONS.get(line)
                if spec is None:
                    raise MalformedSourceError(
                        f"line {index}: unsupported STK attitude section {line!r}; "
                        f"orbit-formats supports {', '.join(_SUPPORTED_SECTIONS)}"
                    )
                data_section = line
                attitude_type, quaternion_pos = spec
                width = len(ATTITUDE_TYPES[attitude_type])
                in_data = True
                continue
            meta.append(_parse_meta_line(line, index))
            continue

        assert attitude_type is not None  # in_data is only set once a section is assigned
        offset, components = _parse_record(line, index, attitude_type, quaternion_pos, width)
        offsets.append(offset)
        rows.append(components)

    if not version:
        raise MalformedSourceError(
            "not an STK attitude file: the stk.v.X.Y version banner is missing"
        )
    if not in_attitude:
        raise MalformedSourceError(
            "not an STK attitude file: the 'BEGIN Attitude' block is missing"
        )
    if data_section is None or attitude_type is None:
        raise MalformedSourceError(
            f"the STK attitude file has no data section (expected one of "
            f"{', '.join(_SUPPORTED_SECTIONS)})"
        )
    scenario_raw = _meta_value(meta, _META_SCENARIO_EPOCH)
    if scenario_raw is None:
        raise MalformedSourceError(
            f"the STK attitude meta block is missing the required {_META_SCENARIO_EPOCH!r}"
        )
    if attitude_type == "EULER_ANGLE" and _meta_value(meta, _META_SEQUENCE) is None:
        raise MalformedSourceError(
            f"{_EULER_ANGLES} requires a {_META_SEQUENCE!r} meta keyword naming the rotation order"
        )
    scenario_epoch = _parse_scenario_epoch(scenario_raw)
    return StkAttitudeFile(
        version=version,
        scenario_epoch=scenario_epoch,
        attitude_type=attitude_type,
        data_section=data_section,
        epochs=_absolute_epochs(scenario_epoch, offsets),
        records=_records_matrix(rows, width),
        meta=tuple(meta),
        header_comments=tuple(comments),
        has_end_marker=seen_end,
    )


def _looks_like_attitude_section(line: str) -> bool:
    """Whether a lone ``AttitudeTime…`` token is a data-section header (so it is not meta)."""
    return line.startswith("AttitudeTime") and len(line.split()) == 1


def _parse_record(
    line: str, index: int, attitude_type: str, quaternion_pos: str | None, width: int
) -> tuple[float, list[float]]:
    """Parse one data record: an offset plus the ``width`` attitude components for the section."""
    tokens = line.split()
    if len(tokens) != width + 1:
        raise MalformedSourceError(
            f"line {index}: expected an offset plus {width} {attitude_type} component(s), "
            f"got {len(tokens) - 1}: {line!r}"
        )
    try:
        values = [float(token) for token in tokens]
    except ValueError as exc:
        raise MalformedSourceError(
            f"line {index}: non-numeric value in the STK attitude record {line!r}"
        ) from exc
    components = values[1:]
    if attitude_type == "QUATERNION" and quaternion_pos == "first":
        # The section writes the scalar first (QC Q1 Q2 Q3); store the canonical scalar-last order.
        components = [components[1], components[2], components[3], components[0]]
    return values[0], components


def _records_matrix(rows: list[list[float]], width: int) -> NDArray[np.float64]:
    if not rows:
        return np.empty((0, width), dtype=np.float64)
    return np.array(rows, dtype=np.float64)


def _to_attitude(stk: StkAttitudeFile) -> Attitude:
    """Adapt an :class:`StkAttitudeFile` into the canonical :class:`Attitude`.

    Tags the spine from the meta block — the reference frame (``CoordinateAxes`` → ``frame_a``;
    the implicit body frame is ``frame_b = None``), the central body, the UTC default scale, and
    the Euler ``Sequence`` — and carries the whole fidelity model as ``source_native``.
    """
    metadata = Metadata(
        central_body=stk.meta_value(_META_CENTRAL_BODY),
        time_scale=_DEFAULT_TIME_SCALE,
        provenance=Provenance(source_format="stk-attitude"),
    )
    euler_rot_seq = stk.meta_value(_META_SEQUENCE) if stk.attitude_type == "EULER_ANGLE" else None
    return Attitude(
        metadata=metadata,
        source_native=stk,
        attitude_type=stk.attitude_type,
        epochs=stk.epochs,
        records=stk.records,
        frame_a=stk.meta_value(_META_COORDINATE_AXES),
        frame_b=None,
        euler_rot_seq=euler_rot_seq,
    )


register_reader("stk-attitude", read_stk_attitude)
