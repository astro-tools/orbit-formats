"""The canonical :class:`Conjunction` category — construction, validation, value equality."""

from __future__ import annotations

import numpy as np
import pytest

from orbit_formats import Conjunction, ConjunctionObject, Metadata


def _object(label: str = "OBJECT1", designator: str = "12345") -> ConjunctionObject:
    return ConjunctionObject(
        label=label,
        object_designator=designator,
        ref_frame="EME2000",
        state=np.arange(6, dtype=np.float64),
        covariance=np.eye(6, dtype=np.float64),
    )


def _conjunction(**overrides: object) -> Conjunction:
    base: dict[str, object] = {
        "metadata": Metadata(time_scale="UTC"),
        "tca": np.datetime64("2024-03-13T22:37:52", "ns"),
        "miss_distance": 715.0,
        "objects": (_object("OBJECT1", "12345"), _object("OBJECT2", "30337")),
    }
    base.update(overrides)
    return Conjunction(**base)  # type: ignore[arg-type]


def test_conjunction_coerces_tca_and_relative_vectors() -> None:
    conj = _conjunction(
        relative_position=[27.4, -70.2, 711.8],
        relative_velocity=(-7.2, -14692.0, -1437.2),
    )
    assert conj.tca.dtype == np.dtype("datetime64[ns]")
    assert isinstance(conj.relative_position, np.ndarray)
    assert isinstance(conj.relative_velocity, np.ndarray)
    assert conj.relative_position.shape == (3,)
    np.testing.assert_allclose(conj.relative_velocity, [-7.2, -14692.0, -1437.2])


def test_conjunction_requires_exactly_two_objects() -> None:
    with pytest.raises(ValueError, match="exactly two objects"):
        Conjunction(
            metadata=Metadata(time_scale="UTC"),
            tca=np.datetime64("2024-03-13T00:00:00", "ns"),
            miss_distance=1.0,
            objects=(_object(),),  # type: ignore[arg-type]
        )


def test_conjunction_rejects_a_misshaped_relative_vector() -> None:
    with pytest.raises(ValueError, match="relative_position must have shape"):
        _conjunction(relative_position=[1.0, 2.0])


def test_object_rejects_a_misshaped_state_or_covariance() -> None:
    with pytest.raises(ValueError, match="state must have shape"):
        ConjunctionObject(
            label="OBJECT1",
            object_designator="1",
            ref_frame="EME2000",
            state=np.zeros(5),
            covariance=np.eye(6),
        )
    with pytest.raises(ValueError, match="covariance must have shape"):
        ConjunctionObject(
            label="OBJECT1",
            object_designator="1",
            ref_frame="EME2000",
            state=np.zeros(6),
            covariance=np.eye(5),
        )


def test_value_equality_compares_content_and_ignores_source_native() -> None:
    a = _conjunction(relative_position=[1.0, 2.0, 3.0])
    b = _conjunction(relative_position=[1.0, 2.0, 3.0])
    assert a == b
    a.source_native = object()  # type: ignore[assignment]
    assert a == b  # equality is by canonical content, not the native handle


def test_value_inequality_on_a_differing_object_or_miss_distance() -> None:
    assert _conjunction(miss_distance=715.0) != _conjunction(miss_distance=716.0)
    other = _conjunction(objects=(_object("OBJECT1", "999"), _object("OBJECT2", "30337")))
    assert _conjunction() != other


def test_conjunctions_are_unhashable_value_objects() -> None:
    with pytest.raises(TypeError):
        hash(_conjunction())
