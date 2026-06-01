"""The reserved category types that are declared but not yet implemented.

``Attitude`` graduated to a real category with the CCSDS AEM / APM work (see
``tests/test_attitude.py``); ``Conjunction`` and ``Tracking`` stay forward stubs until the
CDM and TDM messages land.
"""

from __future__ import annotations

import pytest

from orbit_formats import Conjunction, Tracking


@pytest.mark.parametrize("category", [Conjunction, Tracking])
def test_reserved_categories_are_not_yet_implemented(category: type) -> None:
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        category()
