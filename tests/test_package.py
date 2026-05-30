"""Smoke tests for the orbit-formats package skeleton."""

import orbit_formats


def test_version_is_nonempty_string() -> None:
    assert isinstance(orbit_formats.__version__, str)
    assert orbit_formats.__version__
