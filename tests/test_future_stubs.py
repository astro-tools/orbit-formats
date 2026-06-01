"""The reserved category types that are declared but not yet implemented.

``Attitude`` graduated to a real category with the CCSDS AEM / APM work (see
``tests/test_attitude.py``) and ``Conjunction`` with the CCSDS CDM work (see
``tests/test_conjunction.py``); ``Tracking`` stays a forward stub until the TDM message lands.
"""

from __future__ import annotations

import pytest

from orbit_formats import Tracking


@pytest.mark.parametrize("category", [Tracking])
def test_reserved_categories_are_not_yet_implemented(category: type) -> None:
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        category()
