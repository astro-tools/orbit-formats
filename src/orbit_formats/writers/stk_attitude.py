"""STK attitude writer — byte-lossless (opt-in), content-lossless, and synthesised paths.

Mirrors the STK ephemeris and AEM writers' three tiers, picked automatically from what the
canonical object carries:

1. An ``Attitude`` whose ``source_native`` is a
   :class:`~orbit_formats.readers.stk_attitude.StkAttitudeFile` **with retained bytes** (the
   read opted in via ``retain_source=True``) → the verbatim bytes are echoed, so the
   same-format round trip is **byte-identical** by construction.
2. An ``Attitude`` with an ``StkAttitudeFile`` ``source_native`` **without** retained bytes →
   the structured fidelity model is re-serialised: **content-lossless** (the banner, every
   comment and meta keyword, the data section and the records preserved), canonically
   formatted. A scalar-first quaternion source is re-emitted scalar-first, matching its
   declared section.
3. Any other ``Attitude`` (synthesised or cross-format, no STK ``source_native``) → an STK
   attitude file is built from the canonical fields, warning (via the lossy-warning framework)
   for each ``.a``-required field the canonical form cannot supply and for each canonical field
   STK's ``.a`` structurally cannot hold (the object name / id and the named body frame).

Only the quaternion and Euler-angle representations the canonical
:class:`~orbit_formats.canonical.attitude.Attitude` models are writable; a spin attitude has no
STK section in this writer's supported set and is refused. STK attitude has a single text
notation, so the destination extension only selects the format, never a notation; the
``suffix`` argument is accepted (for the writer protocol) and ignored.
"""

from __future__ import annotations

import numpy as np

from orbit_formats.canonical.attitude import Attitude
from orbit_formats.canonical.base import Canonical
from orbit_formats.errors import UnsupportedConversionError
from orbit_formats.readers.stk_attitude import StkAttitudeFile
from orbit_formats.registry import register_writer
from orbit_formats.warnings import DroppedField, LossyConversionWarning, warn_lossy
from orbit_formats.writers.stk_ephemeris import (
    _format_float,
    _format_scenario_epoch,
    _offset_seconds,
)

__all__ = ["write_stk_attitude"]

# Block markers and the STK version banner a synthesised file declares.
_BEGIN_ATTITUDE = "BEGIN Attitude"
_END_ATTITUDE = "END Attitude"
_STK_VERSION = "stk.v.11.0"
_PLACEHOLDER = "UNKNOWN"

# The ScenarioEpoch a synthesised file falls back to when the attitude carries no epoch to derive
# it from (an empty attitude). Unlike the textual placeholder it is a real instant in the valid
# Gregorian form, so the output stays a structurally valid, re-readable ``.a``; it is otherwise
# unused — an empty attitude has no records to offset against it. Mirrors the SP3 writer's fallback.
_SENTINEL_EPOCH = np.datetime64("2000-01-01T12:00:00", "ns")

# The data section each writable canonical attitude type is serialised under. A synthesised
# quaternion is written scalar-last (AttitudeTimeQuaternions) — the canonical records' own
# order — so no quaternion is reordered. ``AttitudeTimeQuatScalarFirst`` is reached only on the
# content-lossless path, re-emitting a scalar-first source under its original section.
_QUATERNION_LAST = "AttitudeTimeQuaternions"
_QUATERNION_FIRST = "AttitudeTimeQuatScalarFirst"
_EULER_ANGLES = "AttitudeTimeEulerAngles"
_SECTION_FOR_TYPE = {"QUATERNION": _QUATERNION_LAST, "EULER_ANGLE": _EULER_ANGLES}


def write_stk_attitude(obj: Canonical, suffix: str | None = None) -> bytes:
    """Serialise ``obj`` (an :class:`Attitude`) to STK attitude (``.a``) bytes.

    Picks the byte-identical, content-lossless, or synthesised path automatically — see the
    module docstring. ``suffix`` (the destination extension) is ignored: STK attitude has a
    single text notation. Raises :class:`~orbit_formats.errors.UnsupportedConversionError` if
    ``obj`` is not an ``Attitude``, or if it is an attitude whose representation (e.g. a spin
    state) has no STK section in this writer's supported set.
    """
    if not isinstance(obj, Attitude):
        raise UnsupportedConversionError(type(obj).__name__, "stk-attitude", "attitude")
    native = obj.source_native
    if isinstance(native, StkAttitudeFile):
        if native.raw_bytes is not None:
            return native.raw_bytes
        return _serialize(native)
    return _serialize(_stkfile_from_attitude(obj))


def _stkfile_from_attitude(att: Attitude) -> StkAttitudeFile:
    """Build an :class:`StkAttitudeFile` from a canonical ``Attitude``, warning on gaps.

    Each ``.a``-required field the canonical form cannot supply is written as a placeholder and
    reported; each canonical field the ``.a`` cannot hold at all (object identity, the named
    body frame) is reported as dropped. So a synthesised STK attitude file is structurally valid
    yet never silently incomplete. Raises
    :class:`~orbit_formats.errors.UnsupportedConversionError` for an attitude representation with
    no STK section here (a spin attitude).
    """
    if att.attitude_type not in _SECTION_FOR_TYPE:
        raise UnsupportedConversionError(att.attitude_type, "stk-attitude", "attitude")
    _warn_unrepresentable(att)

    count = len(att)
    meta: list[tuple[str, str]] = [("NumberOfAttitudePoints", str(count))]
    if count:
        scenario_epoch = att.epochs[0]
        meta.append(("ScenarioEpoch", _format_scenario_epoch(scenario_epoch)))
    else:
        # With no records there is no epoch to derive ScenarioEpoch from. STK requires the field,
        # so write a sentinel instant in the valid Gregorian form (so the file stays structurally
        # valid and re-reads) and warn that the real epoch was unavailable. The sentinel is
        # otherwise unused — there are no records to offset against it.
        scenario_epoch = _SENTINEL_EPOCH
        sentinel = _format_scenario_epoch(scenario_epoch)
        _warn_missing(
            "ScenarioEpoch",
            f"the canonical attitude has no epochs to derive it from; "
            f"wrote the sentinel {sentinel}",
        )
        meta.append(("ScenarioEpoch", sentinel))
    meta.append(("CentralBody", _resolve_required("CentralBody", att.metadata.central_body)))
    meta.append(("CoordinateAxes", _resolve_required("CoordinateAxes", att.frame_a)))
    if att.attitude_type == "EULER_ANGLE":
        meta.append(("Sequence", _resolve_required("Sequence", att.euler_rot_seq)))
    return StkAttitudeFile(
        version=_STK_VERSION,
        scenario_epoch=scenario_epoch,
        attitude_type=att.attitude_type,
        data_section=_SECTION_FOR_TYPE[att.attitude_type],
        epochs=att.epochs,
        records=att.records,
        meta=tuple(meta),
        header_comments=(),
        has_end_marker=True,
    )


def _warn_unrepresentable(att: Attitude) -> None:
    """Warn for each canonical field STK's ``.a`` structurally has no slot for."""
    dropped: list[DroppedField] = []
    if att.metadata.object_name is not None:
        dropped.append(
            DroppedField(
                "OBJECT_NAME",
                "STK .a has no object-name field (it is a scenario-level property in STK)",
            )
        )
    if att.metadata.object_id is not None:
        dropped.append(DroppedField("OBJECT_ID", "STK .a has no object-id field"))
    if att.frame_b is not None:
        dropped.append(
            DroppedField(
                "REF_FRAME_B",
                f"STK .a names only the reference axes (CoordinateAxes); the body frame "
                f"{att.frame_b!r} stays implicit and is not written",
            )
        )
    if dropped:
        warn_lossy(
            LossyConversionWarning(
                "the STK attitude file cannot hold some fields the canonical attitude carries",
                dropped=tuple(dropped),
            ),
            stacklevel=4,
        )


def _resolve_required(keyword: str, value: str | None) -> str:
    """Return ``value`` if present, else warn that the ``.a``-required field is unavailable."""
    if value is not None:
        return value
    _warn_missing(keyword, "the canonical attitude did not carry it")
    return _PLACEHOLDER


def _warn_missing(keyword: str, reason: str) -> None:
    warn_lossy(
        LossyConversionWarning(
            f"the attitude does not supply the STK-required {keyword}; "
            f"wrote the placeholder {_PLACEHOLDER!r}",
            dropped=(DroppedField(keyword, reason),),
        ),
        stacklevel=4,
    )


def _serialize(stk: StkAttitudeFile) -> bytes:
    """Serialise an :class:`StkAttitudeFile` to canonical STK attitude bytes (lossless)."""
    lines: list[str] = [stk.version, ""]
    if stk.header_comments:
        lines.extend(stk.header_comments)
        lines.append("")
    lines.append(_BEGIN_ATTITUDE)
    lines.append("")
    lines.extend(f"{key} {value}" for key, value in stk.meta)
    lines.append("")
    lines.append(stk.data_section)
    lines.append("")
    lines.extend(_serialize_record(stk, index) for index in range(len(stk.epochs)))
    if stk.has_end_marker:
        lines.append("")
        lines.append(_END_ATTITUDE)
    return ("\n".join(lines) + "\n").encode("utf-8")


def _serialize_record(stk: StkAttitudeFile, index: int) -> str:
    components = stk.records[index]
    if stk.data_section == _QUATERNION_FIRST:
        # The canonical record is scalar-last (Q1 Q2 Q3 QC); this section writes the scalar first.
        components = np.array(
            [components[3], components[0], components[1], components[2]], dtype=np.float64
        )
    parts = [_format_float(_offset_seconds(stk.epochs[index], stk.scenario_epoch))]
    parts.extend(_format_float(value) for value in components)
    return " ".join(parts)


register_writer("stk-attitude", write_stk_attitude)
