"""The typed error hierarchy the public surface raises.

Every error orbit-formats raises on purpose descends from :class:`OrbitFormatsError`, so a
caller can catch the whole family with one ``except``. Detection failures
(:class:`FormatDetectionError` and its two subtypes) are separated from operational
failures (:class:`UnsupportedFormatError`, :class:`UnsupportedConversionError`) and from a
parse failure on otherwise-recognised content (:class:`MalformedSourceError`), so a caller
can tell "I could not work out *what* this is" from "I know what it is but cannot do
*that* with it" from "I know what it is but its content is broken".
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "AmbiguousFormatError",
    "FormatDetectionError",
    "FrameRotationUnsupportedError",
    "IncompatibleMeanElementTheoryError",
    "MalformedSourceError",
    "MissingOptionalDependencyError",
    "OrbitFormatsError",
    "UnknownFormatError",
    "UnsupportedConversionError",
    "UnsupportedFormatError",
]


class OrbitFormatsError(Exception):
    """Base class for every error orbit-formats raises deliberately."""


class FormatDetectionError(OrbitFormatsError):
    """Auto-detection could not settle on a single format."""


class UnknownFormatError(FormatDetectionError):
    """No signature matched, or an explicitly requested format id is not recognised.

    Covers both "I read the bytes and nothing matched" and "you passed ``format='foo'``
    and ``'foo'`` is not a format I know".
    """


class AmbiguousFormatError(FormatDetectionError):
    """More than one signature matched and no tiebreaker resolved it.

    ``candidates`` holds the matching format ids so a caller can disambiguate by passing
    an explicit ``format=``.
    """

    def __init__(self, candidates: Iterable[str]) -> None:
        self.candidates: tuple[str, ...] = tuple(candidates)
        joined = ", ".join(self.candidates)
        super().__init__(
            f"format is ambiguous; signatures matched: {joined}. "
            "Pass an explicit format= to disambiguate."
        )


class UnsupportedFormatError(OrbitFormatsError):
    """A recognised format whose requested operation is not available.

    Raised when no reader or writer is registered for an otherwise-known format, or when
    a write targets a read-only format.
    """


class UnsupportedConversionError(OrbitFormatsError):
    """No available conversion from a source object to the requested target format.

    ``source_form`` is the source object's canonical form, ``target_format`` the
    requested format id, and ``target_form`` the canonical form that format expects.
    """

    def __init__(self, source_form: str, target_format: str, target_form: str) -> None:
        self.source_form = source_form
        self.target_format = target_format
        self.target_form = target_form
        super().__init__(
            f"no conversion path from a {source_form} to {target_format!r} "
            f"(which expects a {target_form})"
        )


class IncompatibleMeanElementTheoryError(UnsupportedConversionError):
    """A mean-element set whose theory the target mean-element format cannot represent.

    Source and target share the ``mean-elements`` canonical form, so the form-keyed graph
    would pass the object straight through — but the *theory* behind the elements differs.
    A GNSS broadcast-navigation set (quasi-Keplerian parameters referenced to the time of
    ephemeris in an Earth-fixed datum, evaluated by the constellation's user algorithm) is
    not an SGP4/TEME mean-element set: writing it as a TLE or OMM would relabel numbers that
    mean different things. A faithful conversion would have to propagate the broadcast model
    and refit SGP4 elements — a propagation plus an orbit fit, both out of scope — so the
    conversion is refused rather than producing a syntactically valid but physically wrong
    message. ``source_theory`` is the source set's theory; ``target_format`` the refused
    target. Subclasses :class:`UnsupportedConversionError`, so an existing
    ``except UnsupportedConversionError`` still catches it.
    """

    def __init__(self, source_theory: str, target_format: str) -> None:
        self.source_theory = source_theory
        self.source_form = "mean-elements"
        self.target_format = target_format
        self.target_form = "mean-elements"
        OrbitFormatsError.__init__(
            self,
            f"a {source_theory!r} mean-element set cannot be converted to {target_format!r}: "
            f"that format expects SGP4/TEME mean elements, and reconciling broadcast elements "
            "with the SGP4 theory needs a propagation and an orbit fit, which are out of scope",
        )


class MissingOptionalDependencyError(OrbitFormatsError):
    """A feature behind an optional extra was used without its dependency installed.

    orbit-formats keeps heavy or niche backends behind optional extras so the base install
    stays lightweight and fully permissive. Reaching for such a feature — SPK read/write,
    which needs ``spiceypy`` from the ``[spk]`` extra — without the extra installed raises
    this, naming the ``pip install`` that resolves it. ``dependency`` is the missing import
    name and ``extra`` the extra that provides it.
    """

    def __init__(self, dependency: str, *, extra: str) -> None:
        self.dependency = dependency
        self.extra = extra
        super().__init__(
            f"{dependency!r} is required for this feature but is not installed; "
            f"install it with: pip install orbit-formats[{extra}]"
        )


class MalformedSourceError(OrbitFormatsError):
    """Recognised as a known format, but its content could not be parsed.

    The format id is settled (detected or supplied) — this is not a detection failure —
    but the bytes are broken for that format: a TLE with an invalid checksum, a record
    missing a required line, internally inconsistent fields. Distinct from
    :class:`UnsupportedFormatError` (the format is fine, the *operation* is unavailable).
    """


class FrameRotationUnsupportedError(OrbitFormatsError):
    """A requested frame rotation could not be performed.

    This is raised either because one side names a reference frame outside the
    supported set, or because the canonical form carries no Cartesian state to
    rotate (mean elements, for instance, would first require a propagation).
    ``source_frame`` and ``target_frame`` name the two frames involved.
    """

    def __init__(self, source_frame: str, target_frame: str) -> None:
        self.source_frame = source_frame
        self.target_frame = target_frame
        super().__init__(
            f"could not rotate from frame {source_frame!r} to {target_frame!r}: the two "
            "cannot be related, because a frame is outside the supported set or the "
            "canonical form has no Cartesian state to rotate"
        )
