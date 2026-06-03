"""The canonical :class:`Maneuver` sub-record — construction, validation, value equality.

A ``Maneuver`` rides on the :class:`StateVector` an OPM reads into and the :class:`Ephemeris`
an OCM reads into; the format-specific read paths are covered in ``test_ccsds_opm`` /
``test_ccsds_ocm``. Here we exercise the record itself and that the two carriers fold it into
their value equality.
"""

from __future__ import annotations

import numpy as np
import pytest

from orbit_formats import Ephemeris, Maneuver, Metadata, StateVector


def _maneuver(**overrides: object) -> Maneuver:
    base: dict[str, object] = {
        "epoch_ignition": np.datetime64("2024-03-05T10:31:36.871", "ns"),
        "ref_frame": "RTN",
        "duration": 286.0,
        "delta_v": [0.0, 0.0, -0.001],
        "delta_mass": -3.0,
    }
    base.update(overrides)
    return Maneuver(**base)  # type: ignore[arg-type]


def test_maneuver_coerces_its_fields() -> None:
    man = _maneuver(comments=["orbit-raising"])
    assert man.epoch_ignition.dtype == np.dtype("datetime64[ns]")
    assert isinstance(man.duration, float)
    assert isinstance(man.delta_v, np.ndarray)
    assert man.delta_v.shape == (3,)
    assert man.delta_v.dtype == np.float64
    assert isinstance(man.delta_mass, float)
    assert man.comments == ("orbit-raising",)


def test_an_impulsive_maneuver_takes_lean_defaults() -> None:
    man = Maneuver(epoch_ignition=np.datetime64("2024-01-01T00:00:00", "ns"), ref_frame="EME2000")
    assert man.duration == 0.0  # 0 ⇒ impulsive
    assert man.delta_v is None
    assert man.delta_mass is None
    assert man.comments == ()


def test_maneuver_rejects_a_misshaped_delta_v() -> None:
    with pytest.raises(ValueError, match="delta_v must have shape"):
        _maneuver(delta_v=[1.0, 2.0])


def test_value_equality_compares_content() -> None:
    assert _maneuver() == _maneuver()
    assert _maneuver() != _maneuver(duration=287.0)
    assert _maneuver() != _maneuver(ref_frame="EME2000")
    assert _maneuver() != _maneuver(delta_mass=-2.0)
    assert _maneuver(delta_v=[1.0, 0.0, 0.0]) != _maneuver(delta_v=[2.0, 0.0, 0.0])


def test_equality_handles_an_unset_delta_v() -> None:
    epoch = np.datetime64("2024-01-01T00:00:00", "ns")
    bare_a = Maneuver(epoch_ignition=epoch, ref_frame="RTN")
    bare_b = Maneuver(epoch_ignition=epoch, ref_frame="RTN")
    assert bare_a == bare_b  # both delta_v unset
    assert bare_a != _maneuver()  # one carries a delta_v, the other does not


def test_a_maneuver_is_not_equal_to_a_non_maneuver() -> None:
    assert _maneuver() != object()


def test_state_vector_equality_folds_in_maneuvers() -> None:
    def _state(maneuvers: tuple[Maneuver, ...]) -> StateVector:
        return StateVector(
            metadata=Metadata(reference_frame="EME2000"),
            epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
            position=np.array([7000.0, 0.0, 0.0]),
            velocity=np.array([0.0, 7.5, 0.0]),
            maneuvers=maneuvers,
        )

    assert _state((_maneuver(),)) == _state((_maneuver(),))
    assert _state((_maneuver(),)) != _state(())
    assert _state((_maneuver(),)) != _state((_maneuver(duration=1.0),))


def test_ephemeris_equality_folds_in_maneuvers() -> None:
    def _eph(maneuvers: tuple[Maneuver, ...]) -> Ephemeris:
        return Ephemeris(
            metadata=Metadata(reference_frame="EME2000"),
            epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
            positions=np.array([[7000.0, 0.0, 0.0]]),
            velocities=np.array([[0.0, 7.5, 0.0]]),
            maneuvers=maneuvers,
        )

    assert _eph((_maneuver(),)) == _eph((_maneuver(),))
    assert _eph((_maneuver(),)) != _eph(())
