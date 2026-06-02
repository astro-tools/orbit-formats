"""Shared fixtures for the orbit-formats test suite."""

from __future__ import annotations

import warnings
from collections.abc import Callable

import pytest

from orbit_formats.warnings import LossyConversionWarning

# A contract checker: run a conversion and assert it warns about lost information exactly
# when it loses some — and that every such warning is structured. Returns the conversion's
# own result so a test can assert the contract and inspect the output from a single call.
NoSilentLossCheck = Callable[..., object]


@pytest.fixture
def assert_no_silent_loss() -> NoSilentLossCheck:
    """The no-silent-loss contract a converter must satisfy, as a reusable assertion.

    Call ``check(conversion, loses=...)``: it runs ``conversion()`` while capturing
    warnings and asserts a structured :class:`LossyConversionWarning` is emitted exactly
    when ``loses`` is true, and never when it is false. Every emitted lossy warning must
    name at least one dropped field. The conversion's own return value is passed back, so a
    test can assert the contract and inspect the output without calling the writer twice (a
    second, unwrapped call would re-emit the warnings outside the capture). The conversion
    graph and the format writers reuse this fixture on their real converters as they land.
    """

    def check(conversion: Callable[[], object], *, loses: bool) -> object:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = conversion()
        lossy = [
            record.message
            for record in caught
            if isinstance(record.message, LossyConversionWarning)
        ]
        if loses:
            assert lossy, "an information-dropping conversion emitted no warning (silent loss)"
            for warning in lossy:
                assert warning.dropped, "a lossy warning named no dropped field"
        else:
            assert not lossy, f"a lossless conversion emitted lossy warnings: {lossy!r}"
        return result

    return check
