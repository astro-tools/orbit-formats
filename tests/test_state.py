"""Tests for ``StateVector`` and ``KeplerianElements``."""

from __future__ import annotations

import numpy as np
import pytest

from orbit_formats import KeplerianElements, Metadata, StateVector


def _state(**overrides: object) -> StateVector:
    kwargs: dict[str, object] = dict(
        metadata=Metadata(object_name="SAT", reference_frame="J2000", time_scale="UTC"),
        epoch=np.datetime64("2026-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 1.0, 2.0]),
        velocity=np.array([0.0, 7.5, 0.1]),
    )
    kwargs.update(overrides)
    return StateVector(**kwargs)  # type: ignore[arg-type]


def test_construct_and_access() -> None:
    sv = _state()
    assert sv.position.dtype == np.float64
    assert sv.velocity.shape == (3,)
    assert sv.keplerian is None


def test_epoch_is_coerced_to_nanoseconds() -> None:
    sv = _state(epoch=np.datetime64("2026-01-01", "D"))
    assert sv.epoch.dtype == np.dtype("datetime64[ns]")


def test_position_coerced_from_list() -> None:
    sv = _state(position=[7000, 0, 0])  # runtime coercion net for non-array input
    assert isinstance(sv.position, np.ndarray)
    assert sv.position.dtype == np.float64


def test_bad_position_shape_raises() -> None:
    with pytest.raises(ValueError, match="position must have shape"):
        _state(position=np.array([1.0, 2.0]))


def test_bad_velocity_shape_raises() -> None:
    with pytest.raises(ValueError, match="velocity must have shape"):
        _state(velocity=np.zeros((3, 2)))


def test_optional_keplerian_is_held_verbatim() -> None:
    kep = KeplerianElements(
        semi_major_axis=7000.0,
        eccentricity=0.001,
        inclination=51.6,
        raan=120.0,
        arg_periapsis=30.0,
        true_anomaly=10.0,
    )
    sv = _state(keplerian=kep)
    assert sv.keplerian == kep


def test_equality_compares_content_and_ignores_type_mismatch() -> None:
    assert _state() == _state()
    assert _state() != _state(position=np.array([1.0, 2.0, 3.0]))
    assert _state() != "not a state vector"


def test_to_dataframe_is_one_row_state_frame() -> None:
    df = _state().to_dataframe()
    assert list(df.columns) == ["Epoch", "X", "Y", "Z", "VX", "VY", "VZ"]
    assert len(df) == 1
    assert df["X"].iloc[0] == 7000.0
    assert df.attrs["object_name"] == "SAT"
    assert df.attrs["coordinate_system"] == "J2000"


def test_dataframe_round_trip_without_drift() -> None:
    sv = _state()
    assert StateVector.from_dataframe(sv.to_dataframe()) == sv


def test_from_dataframe_rejects_multi_row_frame() -> None:
    eph_like = _state().to_dataframe()
    doubled = eph_like.iloc[[0, 0]].reset_index(drop=True)
    doubled.attrs = eph_like.attrs
    with pytest.raises(ValueError, match="exactly one row"):
        StateVector.from_dataframe(doubled)
