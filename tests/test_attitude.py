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
    epochs = np.array(
        [f"2024-01-01T00:0{i}:00" for i in range(rows)], dtype="datetime64[ns]"
    )
    records = np.array([[0.1, 0.2, 0.3, 0.927], [0.11, 0.21, 0.31, 0.92]][:rows])
    return Attitude(
        metadata=Metadata(object_name="SAT", time_scale="UTC"),
        attitude_type="QUATERNION",
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
