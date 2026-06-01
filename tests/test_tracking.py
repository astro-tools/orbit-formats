"""The canonical :class:`Tracking` category — construction, validation, value equality."""

from __future__ import annotations

import numpy as np
import pytest

from orbit_formats import Metadata, Tracking, TrackingObservation


def _observation(
    observation_type: str = "RANGE",
    epoch: str = "2005-06-08T17:41:00",
    value: float = 9.0e10,
) -> TrackingObservation:
    return TrackingObservation(observation_type, np.datetime64(epoch, "ns"), value)


def _tracking(**overrides: object) -> Tracking:
    base: dict[str, object] = {
        "metadata": Metadata(time_scale="UTC"),
        "participants": ("DSS-25", "1999-099A"),
        "observations": (
            _observation("RANGE"),
            _observation("DOPPLER_INSTANTANEOUS", value=-1.9e4),
        ),
    }
    base.update(overrides)
    return Tracking(**base)  # type: ignore[arg-type]


def test_observation_coerces_epoch_and_value() -> None:
    obs = TrackingObservation("ANGLE_1", np.datetime64("2005-06-08T18:00:00"), 12)
    assert obs.epoch.dtype == np.dtype("datetime64[ns]")
    assert isinstance(obs.value, float)
    assert obs.value == 12.0


def test_tracking_coerces_participants_and_observations_to_tuples() -> None:
    tracking = _tracking(participants=["A", "B"], observations=[_observation()])
    assert isinstance(tracking.participants, tuple)
    assert isinstance(tracking.observations, tuple)
    assert tracking.participants == ("A", "B")
    assert len(tracking) == 1


def test_tracking_carries_its_observation_types_and_values() -> None:
    tracking = _tracking()
    assert [obs.observation_type for obs in tracking.observations] == [
        "RANGE",
        "DOPPLER_INSTANTANEOUS",
    ]
    assert tracking.observations[1].value == pytest.approx(-1.9e4)


def test_value_equality_compares_content_and_ignores_source_native() -> None:
    a = _tracking()
    b = _tracking()
    assert a == b
    a.source_native = object()  # type: ignore[assignment]
    assert a == b  # equality is by canonical content, not the native handle


def test_value_inequality_on_a_differing_observation_or_participant() -> None:
    assert _tracking() != _tracking(observations=(_observation("RANGE", value=1.0),))
    assert _tracking() != _tracking(participants=("DSS-14", "1999-099A"))


def test_tracking_is_an_unhashable_value_object() -> None:
    with pytest.raises(TypeError):
        hash(_tracking())
