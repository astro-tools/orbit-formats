"""Structured lossy-conversion warnings.

A conversion that cannot preserve information — covariance a target format cannot hold,
the mean-element semantics of a TLE, a value truncated to a format's field width —
emits a structured, catchable warning naming exactly what was lost, rather than dropping
data silently.

Every warning descends from :class:`LossyConversionWarning`, so a caller catches the
whole family with one ``warnings.catch_warnings`` / ``pytest.warns``. Each instance
carries the dropped information as typed :class:`DroppedField` records, so a caller can
inspect *what* was lost as data rather than scraping a message string. Converters and
writers emit through the single :func:`warn_lossy` seam; nothing drops information by
any other path.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "DroppedField",
    "DroppedFieldWarning",
    "LossyConversionWarning",
    "MissingFieldWarning",
    "ModelApproximationWarning",
    "PrecisionLossWarning",
    "warn_lossy",
]


@dataclass(frozen=True, slots=True)
class DroppedField:
    """One piece of information a conversion could not carry, and why.

    ``name`` is the field that was lost or approximated; ``reason`` says why the target
    could not hold it. The pair is the structured unit every lossy warning is built from.
    """

    name: str
    reason: str


class LossyConversionWarning(UserWarning):
    """Base for every warning a lossy conversion emits — catch this for the whole family.

    Carries the dropped information as structured :class:`DroppedField` records on
    ``dropped``. A lossy warning that names nothing is a contradiction in terms, so
    construction requires at least one dropped field.
    """

    def __init__(self, message: str, *, dropped: Sequence[DroppedField]) -> None:
        fields = tuple(dropped)
        if not fields:
            raise ValueError("a lossy-conversion warning must name at least one dropped field")
        self.dropped: tuple[DroppedField, ...] = fields
        super().__init__(message)

    @property
    def fields(self) -> tuple[str, ...]:
        """The names of the dropped fields, in declaration order."""
        return tuple(field.name for field in self.dropped)


class DroppedFieldWarning(LossyConversionWarning):
    """A field the target format structurally cannot represent.

    The value is dropped outright, not approximated — the archetype is a covariance
    matrix written to a format with no covariance block.
    """

    def __init__(
        self, field: str, *, target_format: str | None = None, reason: str | None = None
    ) -> None:
        where = f" in {target_format}" if target_format else ""
        why = reason or (
            f"{target_format} has no field for it"
            if target_format
            else "the target format has no field for it"
        )
        super().__init__(
            f"{field} cannot be represented{where}; it was dropped",
            dropped=(DroppedField(field, why),),
        )
        self.field = field
        self.target_format = target_format


class PrecisionLossWarning(LossyConversionWarning):
    """A value narrowed to fit a target format's field width or numeric precision.

    The value survives but some digits do not — e.g. an epoch written to a TLE's fixed
    column width.
    """

    def __init__(
        self, field: str, *, target_format: str | None = None, detail: str | None = None
    ) -> None:
        whose = f"{target_format}'s" if target_format else "the target format's"
        why = detail or f"narrowed to fit {whose} field width"
        super().__init__(
            f"{field} was truncated to fit {whose} precision",
            dropped=(DroppedField(field, why),),
        )
        self.field = field
        self.target_format = target_format


class ModelApproximationWarning(LossyConversionWarning):
    """A cross-category conversion that introduces a model step.

    Projecting mean elements (a TLE / OMM) toward a state crosses the mean-element
    semantics: the result is model-dependent, not an exact restatement of the source.
    """

    def __init__(
        self,
        *,
        source_kind: str,
        target_kind: str,
        fields: Sequence[str],
        model: str | None = None,
    ) -> None:
        via = f" via a {model} model step" if model else " via a model step"
        why = f"{source_kind} semantics do not carry over to {target_kind}"
        super().__init__(
            f"converting {source_kind} to {target_kind}{via} is an approximation, "
            "not an exact restatement",
            dropped=tuple(DroppedField(name, why) for name in fields),
        )
        self.source_kind = source_kind
        self.target_kind = target_kind
        self.model = model


class MissingFieldWarning(LossyConversionWarning):
    """A canonical field the source did not provide, filled with NaN rather than fabricated.

    The canonical form has a slot the source format left unpopulated — the archetype is a
    GMAT report (or an SP3 file) that lists position but no velocity. The slot is filled
    with NaN, never a guessed value, and this warning names exactly which fields are absent
    so a caller can decide whether the gap matters. Distinct from
    :class:`DroppedFieldWarning`, where the *target* cannot hold a value the source had;
    here the *source* omitted a value the canonical form has room for.
    """

    def __init__(self, fields: Sequence[str], *, source_format: str | None = None) -> None:
        names = tuple(fields)
        whence = f" from the {source_format} source" if source_format else " from the source"
        verb = "is" if len(names) == 1 else "are"
        why = f"absent{whence.strip()}; filled with NaN, not fabricated"
        super().__init__(
            f"{', '.join(names)} {verb} absent{whence}; filled with NaN rather than fabricated",
            dropped=tuple(DroppedField(name, why) for name in names),
        )
        self.source_format = source_format


def warn_lossy(warning: LossyConversionWarning, *, stacklevel: int = 1) -> None:
    """Emit ``warning`` through the standard warnings machinery — the one sanctioned seam.

    Every converter and writer that drops information routes through here, so the loss is
    always catchable as a :class:`LossyConversionWarning` and the no-silent-loss contract
    has a single point to assert against. ``stacklevel`` counts frames above the caller of
    :func:`warn_lossy`, so the warning is attributed to the conversion, not to this helper.
    """
    warnings.warn(warning, stacklevel=stacklevel + 1)
