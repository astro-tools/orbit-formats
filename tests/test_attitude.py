"""The canonical ``Attitude`` category — a quaternion / Euler / spin attitude record.

``Attitude`` is the federated category the CCSDS AEM (a time series) and APM (a single
attitude) adapt into, alongside ``Ephemeris`` / ``StateVector`` / ``MeanElementSet``.
"""

from __future__ import annotations

import numpy as np
import pytest

from orbit_formats import Attitude, Metadata
from orbit_formats.canonical.attitude import ATTITUDE_TYPES


def _quaternion_attitude(rows: int = 2) -> Attitude:
    epochs = np.array([f"2024-01-01T00:0{i}:00" for i in range(rows)], dtype="datetime64[ns]")
    records = np.array([[0.1, 0.2, 0.3, 0.927], [0.11, 0.21, 0.31, 0.92]][:rows])
    return Attitude(
        metadata=Metadata(object_name="SAT", time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=epochs,
        records=records,
        frame_a="EME2000",
        frame_b="SC_BODY",
    )


def _euler_attitude(rows: int = 2) -> Attitude:
    epochs = np.array([f"2024-01-01T00:0{i}:00" for i in range(rows)], dtype="datetime64[ns]")
    records = np.array([[35.45, -15.75, 18.80], [35.40, -15.70, 18.75]][:rows])
    return Attitude(
        metadata=Metadata(object_name="SAT", time_scale="UTC"),
        attitude_type="EULER_ANGLE",
        epochs=epochs,
        records=records,
        frame_a="EME2000",
        frame_b="SC_BODY",
        euler_rot_seq="321",
    )


def _spin_attitude(rows: int = 2) -> Attitude:
    epochs = np.array([f"2024-01-01T00:0{i}:00" for i in range(rows)], dtype="datetime64[ns]")
    records = np.array([[10.0, 20.0, 30.0, 0.5], [10.1, 20.1, 30.1, 0.51]][:rows])
    return Attitude(
        metadata=Metadata(object_name="SAT", time_scale="UTC"),
        attitude_type="SPIN",
        epochs=epochs,
        records=records,
        frame_a="EME2000",
        frame_b="SC_BODY",
    )


def test_quaternion_attitude_holds_its_records_and_frames() -> None:
    att = _quaternion_attitude()
    assert len(att) == 2
    assert att.attitude_type == "QUATERNION"
    assert att.columns == ("Q1", "Q2", "Q3", "QC")
    assert att.frame_a == "EME2000"
    assert att.frame_b == "SC_BODY"
    np.testing.assert_allclose(att.records[0], [0.1, 0.2, 0.3, 0.927])


def test_a_single_row_attitude_models_an_apm() -> None:
    att = _quaternion_attitude(rows=1)
    assert len(att) == 1
    assert att.records.shape == (1, 4)


def test_euler_attitude_carries_the_rotation_sequence() -> None:
    att = Attitude(
        metadata=Metadata(),
        attitude_type="EULER_ANGLE",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[35.45, -15.75, 18.80]]),
        frame_a="EME2000",
        frame_b="SC_BODY",
        euler_rot_seq="321",
    )
    assert att.columns == ("ANGLE_1", "ANGLE_2", "ANGLE_3")
    assert att.euler_rot_seq == "321"


def test_every_catalogued_attitude_type_has_a_column_layout() -> None:
    assert set(ATTITUDE_TYPES) == {"QUATERNION", "EULER_ANGLE", "SPIN"}


def test_an_unknown_attitude_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown attitude_type"):
        Attitude(
            metadata=Metadata(),
            attitude_type="QUATERNION/DERIVATIVE",
            epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
            records=np.array([[0.0, 0.0, 0.0, 1.0]]),
        )


def test_records_with_the_wrong_width_are_rejected() -> None:
    with pytest.raises(ValueError, match=r"shape \(N, 4\)"):
        Attitude(
            metadata=Metadata(),
            attitude_type="QUATERNION",
            epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
            records=np.array([[0.0, 0.0, 1.0]]),
        )


def test_epoch_and_record_length_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="disagree on length"):
        Attitude(
            metadata=Metadata(),
            attitude_type="QUATERNION",
            epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
            records=np.array([[0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0]]),
        )


def test_equality_is_by_content_and_ignores_source_native() -> None:
    one = _quaternion_attitude()
    two = _quaternion_attitude()
    assert one == two
    two.source_native = object()  # type: ignore[assignment]
    assert one == two


def test_to_dataframe_quaternion_columns_dtypes_and_attrs() -> None:
    att = _quaternion_attitude()
    df = att.to_dataframe()
    assert list(df.columns) == ["Epoch", "Q1", "Q2", "Q3", "QC"]
    assert str(df["Epoch"].dtype) == "datetime64[ns]"
    assert all(str(df[c].dtype) == "float64" for c in ["Q1", "Q2", "Q3", "QC"])
    assert len(df) == 2
    np.testing.assert_allclose(df[["Q1", "Q2", "Q3", "QC"]].to_numpy(), att.records)
    # the shared metadata spine, materialised under gmat-run's flat-key names
    assert df.attrs["object_name"] == "SAT"
    assert df.attrs["time_scale"] == "UTC"
    assert df.attrs["epoch_scales"] == {"Epoch": "UTC"}
    assert df.attrs["units"] == {"length": "km", "speed": "km/s", "angle": "deg", "time": "s"}
    # attitude-specific attrs
    assert df.attrs["attitude_type"] == "QUATERNION"
    assert df.attrs["frame_a"] == "EME2000"
    assert df.attrs["frame_b"] == "SC_BODY"
    # the frame pair lives on frame_a/frame_b, never the spine's single coordinate_system
    assert "coordinate_system" not in df.attrs
    # a quaternion carries no rotation sequence
    assert "euler_rot_seq" not in df.attrs


def test_to_dataframe_euler_carries_the_rotation_sequence() -> None:
    df = _euler_attitude().to_dataframe()
    assert list(df.columns) == ["Epoch", "ANGLE_1", "ANGLE_2", "ANGLE_3"]
    assert all(str(df[c].dtype) == "float64" for c in ["ANGLE_1", "ANGLE_2", "ANGLE_3"])
    assert df.attrs["attitude_type"] == "EULER_ANGLE"
    assert df.attrs["euler_rot_seq"] == "321"


def test_to_dataframe_spin_columns() -> None:
    df = _spin_attitude().to_dataframe()
    assert list(df.columns) == [
        "Epoch",
        "SPIN_ALPHA",
        "SPIN_DELTA",
        "SPIN_ANGLE",
        "SPIN_ANGLE_VEL",
    ]
    assert df.attrs["attitude_type"] == "SPIN"
    assert "euler_rot_seq" not in df.attrs


def test_to_dataframe_single_epoch_apm_projects_one_row() -> None:
    df = _quaternion_attitude(rows=1).to_dataframe()
    assert len(df) == 1
    assert list(df.columns) == ["Epoch", "Q1", "Q2", "Q3", "QC"]
    np.testing.assert_allclose(df[["Q1", "Q2", "Q3", "QC"]].to_numpy(), [[0.1, 0.2, 0.3, 0.927]])


def test_to_dataframe_of_an_empty_attitude_keeps_the_schema() -> None:
    # A zero-row attitude (no samples) still projects to the right columns, dtypes, and attrs —
    # just with no rows — rather than collapsing to an object/empty frame.
    att = Attitude(
        metadata=Metadata(object_name="SAT", time_scale="UTC"),
        attitude_type="QUATERNION",
        epochs=np.empty(0, dtype="datetime64[ns]"),
        records=np.empty((0, 4), dtype=np.float64),
        frame_a="EME2000",
        frame_b="SC_BODY",
    )
    df = att.to_dataframe()
    assert len(df) == 0
    assert list(df.columns) == ["Epoch", "Q1", "Q2", "Q3", "QC"]
    assert str(df["Epoch"].dtype) == "datetime64[ns]"
    assert all(str(df[c].dtype) == "float64" for c in ["Q1", "Q2", "Q3", "QC"])
    assert df.attrs["attitude_type"] == "QUATERNION"
    assert df.attrs["frame_a"] == "EME2000"
    assert df.attrs["frame_b"] == "SC_BODY"


def test_to_dataframe_leaks_no_astropy_or_object_dtypes() -> None:
    df = _euler_attitude().to_dataframe()
    for column in df.columns:
        kind = df[column].dtype.kind
        assert kind in {"f", "M"}, f"{column} has non-plain dtype {df[column].dtype}"
    for value in df.attrs.values():
        assert isinstance(value, (str, int, float, dict))


def test_to_dataframe_omits_unset_optional_attrs() -> None:
    att = Attitude(
        metadata=Metadata(),
        attitude_type="QUATERNION",
        epochs=np.array(["2024-01-01T00:00:00"], dtype="datetime64[ns]"),
        records=np.array([[0.0, 0.0, 0.0, 1.0]]),
    )
    df = att.to_dataframe()
    for absent in [
        "object_name",
        "central_body",
        "coordinate_system",
        "time_scale",
        "epoch_scales",
        "frame_a",
        "frame_b",
        "euler_rot_seq",
    ]:
        assert absent not in df.attrs
    # units and attitude_type are always materialised, even on a bare metadata spine
    assert df.attrs["units"]["length"] == "km"
    assert df.attrs["attitude_type"] == "QUATERNION"
