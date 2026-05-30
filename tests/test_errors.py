"""The typed error hierarchy callers catch against."""

from __future__ import annotations

from orbit_formats import (
    AmbiguousFormatError,
    FormatDetectionError,
    FrameRotationUnsupportedError,
    OrbitFormatsError,
    UnknownFormatError,
    UnsupportedConversionError,
    UnsupportedFormatError,
)


def test_every_error_descends_from_the_base() -> None:
    assert issubclass(FormatDetectionError, OrbitFormatsError)
    assert issubclass(UnknownFormatError, FormatDetectionError)
    assert issubclass(AmbiguousFormatError, FormatDetectionError)
    assert issubclass(UnsupportedFormatError, OrbitFormatsError)
    assert issubclass(UnsupportedConversionError, OrbitFormatsError)
    assert issubclass(FrameRotationUnsupportedError, OrbitFormatsError)


def test_ambiguous_error_carries_the_candidates() -> None:
    error = AmbiguousFormatError(["ccsds-oem", "ccsds-omm"])
    assert error.candidates == ("ccsds-oem", "ccsds-omm")
    message = str(error)
    assert "ccsds-oem" in message
    assert "ccsds-omm" in message


def test_unsupported_conversion_error_records_forms() -> None:
    error = UnsupportedConversionError("mean-elements", "ccsds-oem", "ephemeris")
    assert error.source_form == "mean-elements"
    assert error.target_format == "ccsds-oem"
    assert error.target_form == "ephemeris"
    message = str(error)
    assert "mean-elements" in message
    assert "ephemeris" in message
