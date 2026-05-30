"""Tests for ``Ephemeris`` and its gmat-run-identical DataFrame projection."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from orbit_formats import DEFAULT_UNITS, Ephemeris, Metadata


def _epochs(n: int) -> np.ndarray:
    base = np.datetime64("2026-01-01T00:00:00", "ns")
    return base + np.arange(n) * np.timedelta64(60, "s")


def _ephemeris(*, metadata: Metadata | None = None, n: int = 3, **overrides: object) -> Ephemeris:
    kwargs: dict[str, object] = dict(
        metadata=metadata
        if metadata is not None
        else Metadata(
            object_name="SAT", central_body="EARTH", reference_frame="J2000", time_scale="UTC"
        ),
        epochs=_epochs(n),
        positions=np.arange(n * 3, dtype=float).reshape(n, 3),
        velocities=np.arange(n * 3, dtype=float).reshape(n, 3) + 0.5,
        interpolation="Lagrange",
        interpolation_degree=5,
    )
    kwargs.update(overrides)
    return Ephemeris(**kwargs)  # type: ignore[arg-type]


def test_len_and_field_dtypes() -> None:
    eph = _ephemeris(n=4)
    assert len(eph) == 4
    assert eph.epochs.dtype == np.dtype("datetime64[ns]")
    assert eph.positions.dtype == np.float64


def test_epochs_must_be_one_dimensional() -> None:
    with pytest.raises(ValueError, match="epochs must be 1-D"):
        _ephemeris(epochs=_epochs(3).reshape(3, 1))


def test_position_length_must_match_epochs() -> None:
    with pytest.raises(ValueError, match=r"positions must have shape \(3, 3\)"):
        _ephemeris(positions=np.zeros((2, 3)))


def test_velocity_length_must_match_epochs() -> None:
    with pytest.raises(ValueError, match=r"velocities must have shape \(3, 3\)"):
        _ephemeris(velocities=np.zeros((4, 3)))


def test_to_dataframe_matches_gmat_run_schema() -> None:
    df = _ephemeris().to_dataframe()
    assert list(df.columns) == ["Epoch", "X", "Y", "Z", "VX", "VY", "VZ"]
    assert str(df["Epoch"].dtype) == "datetime64[ns]"
    assert all(str(df[c].dtype) == "float64" for c in ["X", "Y", "Z", "VX", "VY", "VZ"])
    # flat spine attrs under gmat-run's names, plus the units / interpolation extensions
    assert df.attrs["object_name"] == "SAT"
    assert df.attrs["central_body"] == "EARTH"
    assert df.attrs["coordinate_system"] == "J2000"  # reference_frame -> coordinate_system
    assert df.attrs["time_scale"] == "UTC"
    assert df.attrs["epoch_scales"] == {"Epoch": "UTC"}
    assert df.attrs["units"] == {"length": "km", "speed": "km/s", "angle": "deg", "time": "s"}
    assert df.attrs["interpolation"] == "Lagrange"
    assert df.attrs["interpolation_degree"] == 5


def test_to_dataframe_leaks_no_astropy_or_object_dtypes() -> None:
    df = _ephemeris().to_dataframe()
    for column in df.columns:
        kind = df[column].dtype.kind
        assert kind in {"f", "M"}, f"{column} has non-plain dtype {df[column].dtype}"
    # attrs are plain Python / numpy scalars and containers, never astropy objects
    for value in df.attrs.values():
        assert isinstance(value, (str, int, float, dict))


def test_to_dataframe_omits_unknown_spine_keys() -> None:
    df = _ephemeris(
        metadata=Metadata(), interpolation=None, interpolation_degree=None
    ).to_dataframe()
    for absent in [
        "object_name",
        "central_body",
        "coordinate_system",
        "time_scale",
        "epoch_scales",
        "interpolation",
        "interpolation_degree",
    ]:
        assert absent not in df.attrs
    # units are always materialised, even on a bare metadata spine
    assert df.attrs["units"]["length"] == "km"


def test_dataframe_round_trip_without_drift() -> None:
    eph = _ephemeris()
    restored = Ephemeris.from_dataframe(eph.to_dataframe())
    assert restored == eph


def test_round_trip_preserves_interpolation_degree_as_int() -> None:
    restored = Ephemeris.from_dataframe(_ephemeris().to_dataframe())
    assert restored.interpolation_degree == 5
    assert isinstance(restored.interpolation_degree, int)


def test_from_dataframe_requires_state_columns() -> None:
    bad = pd.DataFrame({"Epoch": _epochs(2), "X": [0.0, 1.0]})
    with pytest.raises(ValueError, match="missing required state columns"):
        Ephemeris.from_dataframe(bad)


def test_equality_requires_matching_metadata() -> None:
    base = _ephemeris()
    relabelled = _ephemeris(
        metadata=Metadata(
            object_name="OTHER", central_body="EARTH", reference_frame="J2000", time_scale="UTC"
        )
    )
    # identical numeric payload, different spine -> not equal
    assert base != relabelled


def test_from_dataframe_defaults_units_when_attr_absent() -> None:
    df = _ephemeris().to_dataframe()
    del df.attrs["units"]
    assert Ephemeris.from_dataframe(df).metadata.units == DEFAULT_UNITS
