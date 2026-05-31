"""The v0.2 category types are declared but not yet implemented."""

from __future__ import annotations

import pytest

from orbit_formats import Attitude, Conjunction, Tracking


@pytest.mark.parametrize("category", [Attitude, Conjunction, Tracking])
def test_reserved_categories_are_not_yet_implemented(category: type) -> None:
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        category()
