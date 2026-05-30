"""Time-scale conversion: every scale checked against astropy reference values, round-trips,
GPS as a TAI offset, shape preservation, and rejection of an unknown scale."""

from __future__ import annotations

import numpy as np
import pytest

from orbit_formats.canonical.metadata import TIME_SCALES
from orbit_formats.convert.time import convert_time_scale

# A 2020 epoch sits well inside astropy's bundled IERS-B coverage, so the UT1 conversion
# is deterministic without any network access.
EPOCHS = np.array(["2020-06-01T00:00:00", "2020-06-01T12:00:00"], dtype="datetime64[ns]")


def _astropy_reference(epochs: np.ndarray, from_scale: str, to_scale: str) -> np.ndarray:
    """The expected result computed straight from astropy, the reference the DoD names."""
    from astropy.time import Time, TimeDelta
    from astropy.utils import iers

    offset = TimeDelta(19.0, format="sec")
    astropy_scale = {"UTC": "utc", "TAI": "tai", "TT": "tt", "TDB": "tdb", "UT1": "ut1"}
    with iers.conf.set_temp("auto_download", False):
        if from_scale == "GPS":
            tai = Time(epochs, format="datetime64", scale="tai") + offset
        else:
            tai = Time(epochs, format="datetime64", scale=astropy_scale[from_scale]).tai
        if to_scale == "GPS":
            out = (tai - offset).to_value("datetime64")
        else:
            out = getattr(tai, astropy_scale[to_scale]).to_value("datetime64")
    return np.asarray(out, dtype="datetime64[ns]")


@pytest.mark.parametrize("to_scale", sorted(TIME_SCALES))
def test_from_utc_matches_astropy(to_scale: str) -> None:
    result = convert_time_scale(EPOCHS, "UTC", to_scale)
    np.testing.assert_array_equal(result, _astropy_reference(EPOCHS, "UTC", to_scale))


@pytest.mark.parametrize("from_scale", sorted(TIME_SCALES))
def test_to_utc_matches_astropy(from_scale: str) -> None:
    result = convert_time_scale(EPOCHS, from_scale, "UTC")
    np.testing.assert_array_equal(result, _astropy_reference(EPOCHS, from_scale, "UTC"))


def test_identity_conversion_returns_epochs_unchanged() -> None:
    result = convert_time_scale(EPOCHS, "TT", "TT")
    np.testing.assert_array_equal(result, EPOCHS)


def test_utc_to_tai_applies_the_leap_second_offset() -> None:
    # 2020 carries 37 leap seconds: TAI runs exactly 37 s ahead of UTC.
    result = convert_time_scale(EPOCHS, "UTC", "TAI")
    assert (result - EPOCHS == np.timedelta64(37, "s")).all()


def test_gps_is_tai_minus_nineteen_seconds() -> None:
    tai = convert_time_scale(EPOCHS, "UTC", "TAI")
    gps = convert_time_scale(EPOCHS, "UTC", "GPS")
    assert (tai - gps == np.timedelta64(19, "s")).all()


@pytest.mark.parametrize(
    ("from_scale", "to_scale"),
    [("UTC", "TAI"), ("UTC", "GPS"), ("TT", "UT1"), ("GPS", "TDB")],
)
def test_round_trip_returns_to_the_source(from_scale: str, to_scale: str) -> None:
    forward = convert_time_scale(EPOCHS, from_scale, to_scale)
    back = convert_time_scale(forward, to_scale, from_scale)
    # Sub-nanosecond float jitter through astropy's day-based internals, so allow 1 ns.
    assert (np.abs(back - EPOCHS) <= np.timedelta64(1, "ns")).all()


def test_a_scalar_epoch_returns_a_scalar() -> None:
    scalar = np.datetime64("2020-06-01T00:00:00", "ns")
    result = convert_time_scale(scalar, "UTC", "TAI")
    assert result.shape == ()
    assert result == scalar + np.timedelta64(37, "s")


def test_unknown_scale_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown time scale"):
        convert_time_scale(EPOCHS, "UTC", "BOGUS")
    with pytest.raises(ValueError, match="unknown time scale"):
        convert_time_scale(EPOCHS, "TWERK", "UTC")
