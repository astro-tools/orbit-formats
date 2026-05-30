"""The typed error hierarchy the public surface raises.

Every error orbit-formats raises on purpose descends from :class:`OrbitFormatsError`, so a
caller can catch the whole family with one ``except``. Detection failures
(:class:`FormatDetectionError` and its two subtypes) are separated from operational
failures (:class:`UnsupportedFormatError`, :class:`UnsupportedConversionError`) so a
caller can tell "I could not work out *what* this is" from "I know what it is but cannot
do *that* with it".
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "AmbiguousFormatError",
    "FormatDetectionError",
    "FrameRotationUnsupportedError",
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
            f"(which expects a {target_form}); only same-form conversion is supported"
        )


class FrameRotationUnsupportedError(OrbitFormatsError):
    """A conversion would require rotating between two distinct reference frames.

    v0.1 tags and preserves reference frames but does not rotate between them (frame
    rotation is deferred to a later version). A conversion that would need a rotation
    raises this rather than performing a naive one. ``source_frame`` and ``target_frame``
    name the two frames that differ.
    """

    def __init__(self, source_frame: str, target_frame: str) -> None:
        self.source_frame = source_frame
        self.target_frame = target_frame
        super().__init__(
            f"converting from frame {source_frame!r} to {target_frame!r} would require a "
            "frame rotation, which is not supported; only same-frame conversion is "
            "available in this version"
        )
