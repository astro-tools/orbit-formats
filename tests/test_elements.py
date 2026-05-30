"""Tests for ``MeanElementSet`` (TLE / OMM mean elements)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from orbit_formats import MeanElementSet, Metadata


def _elements(**overrides: object) -> MeanElementSet:
    kwargs: dict[str, object] = dict(
        metadata=Metadata(
            object_name="ISS", object_id="25544", reference_frame="TEME", time_scale="UTC"
        ),
        epoch=np.datetime64("2026-01-01T00:00:00", "ns"),
        mean_motion=15.5,
        eccentricity=0.0006,
        inclination=51.6,
        raan=120.0,
        arg_periapsis=30.0,
        mean_anomaly=10.0,
    )
    kwargs.update(overrides)
    return MeanElementSet(**kwargs)  # type: ignore[arg-type]


def test_construct_and_optional_drag_terms() -> None:
    mes = _elements(bstar=1.2e-4, mean_motion_dot=1e-7, mean_motion_ddot=0.0)
    assert mes.metadata.object_id == "25544"
    assert mes.bstar == 1.2e-4
    bare = _elements()
    assert bare.bstar is None and bare.mean_motion_dot is None and bare.mean_motion_ddot is None


def test_epoch_coerced_to_nanoseconds() -> None:
    assert _elements(epoch=np.datetime64("2026-01-01", "D")).epoch.dtype == np.dtype(
        "datetime64[ns]"
    )


@pytest.mark.parametrize("ecc", [1.0, 1.5, -0.1])
def test_eccentricity_must_be_in_unit_interval(ecc: float) -> None:
    with pytest.raises(ValueError, match="eccentricity must be in"):
        _elements(eccentricity=ecc)


def test_equality() -> None:
    assert _elements(bstar=1e-4) == _elements(bstar=1e-4)
    assert _elements(bstar=1e-4) != _elements(bstar=2e-4)


# Round-trips compare projected content: object_id / originator / provenance are
# off-projection (the DataFrame carries only the gmat-run spine), so the round-tripped
# metadata holds the projected fields only — see test_object_id_is_off_projection.
_PROJECTED_META = Metadata(object_name="ISS", reference_frame="TEME", time_scale="UTC")


def test_dataframe_round_trip_with_drag_terms() -> None:
    mes = _elements(
        metadata=_PROJECTED_META, bstar=1.2e-4, mean_motion_dot=1e-7, mean_motion_ddot=3e-10
    )
    df = mes.to_dataframe()
    assert df.attrs["coordinate_system"] == "TEME"
    assert MeanElementSet.from_dataframe(df) == mes


def test_dataframe_round_trip_without_drag_terms() -> None:
    mes = _elements(metadata=_PROJECTED_META)
    assert MeanElementSet.from_dataframe(mes.to_dataframe()) == mes


def test_object_id_is_off_projection() -> None:
    # NORAD id lives on the canonical object (and its source_native), not in the lossy
    # DataFrame edge form, which mirrors gmat-run's object_name-only spine.
    mes = _elements()  # metadata.object_id == "25544"
    assert "object_id" not in mes.to_dataframe().attrs
    assert MeanElementSet.from_dataframe(mes.to_dataframe()).metadata.object_id is None


def test_from_dataframe_maps_nan_drag_terms_to_none() -> None:
    df = _elements(bstar=1.2e-4).to_dataframe()
    df["BStar"] = np.nan  # a producer that encodes "no drag term" as NaN
    assert MeanElementSet.from_dataframe(df).bstar is None


def test_from_dataframe_rejects_missing_columns() -> None:
    df = _elements().to_dataframe().drop(columns=["MeanMotion"])
    with pytest.raises(ValueError, match="missing required mean-element columns"):
        MeanElementSet.from_dataframe(df)


def test_from_dataframe_rejects_multi_row_frame() -> None:
    one = _elements().to_dataframe()
    two = pd.concat([one, one], ignore_index=True)
    with pytest.raises(ValueError, match="exactly one row"):
        MeanElementSet.from_dataframe(two)
