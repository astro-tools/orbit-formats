"""The lossy-conversion warning framework: a catchable family, structured payloads, and
the no-silent-loss contract every converter must satisfy."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from orbit_formats import (
    DroppedField,
    DroppedFieldWarning,
    LossyConversionWarning,
    ModelApproximationWarning,
    PrecisionLossWarning,
    warn_lossy,
)

CONCRETE_WARNINGS = [DroppedFieldWarning, ModelApproximationWarning, PrecisionLossWarning]


def _sample(cls: type[LossyConversionWarning]) -> LossyConversionWarning:
    """A representative instance of each concrete warning, with full context."""
    if cls is DroppedFieldWarning:
        return DroppedFieldWarning("covariance", target_format="ccsds-oem")
    if cls is PrecisionLossWarning:
        return PrecisionLossWarning("epoch", target_format="tle")
    if cls is ModelApproximationWarning:
        return ModelApproximationWarning(
            source_kind="mean elements", target_kind="state", fields=["state"], model="SGP4"
        )
    raise AssertionError(f"unhandled warning type {cls!r}")


# --- the hierarchy -----------------------------------------------------------------


def test_every_warning_descends_from_the_base() -> None:
    assert issubclass(LossyConversionWarning, Warning)
    for cls in CONCRETE_WARNINGS:
        assert issubclass(cls, LossyConversionWarning)


def test_a_lossy_warning_must_name_a_dropped_field() -> None:
    with pytest.raises(ValueError, match="at least one"):
        LossyConversionWarning("nothing was lost", dropped=[])
    with pytest.raises(ValueError, match="at least one"):
        ModelApproximationWarning(source_kind="mean elements", target_kind="state", fields=[])


# --- the structured payload --------------------------------------------------------


@pytest.mark.parametrize("cls", CONCRETE_WARNINGS)
def test_each_warning_names_what_was_lost(cls: type[LossyConversionWarning]) -> None:
    warning = _sample(cls)
    assert warning.dropped
    for field in warning.dropped:
        assert isinstance(field, DroppedField)
        assert field.name
        assert field.reason
        assert field.name in str(warning)
    assert warning.fields == tuple(field.name for field in warning.dropped)


def test_warnings_build_without_optional_context() -> None:
    dropped = DroppedFieldWarning("covariance")
    assert "covariance" in str(dropped)
    assert dropped.target_format is None
    assert dropped.dropped[0].reason

    precision = PrecisionLossWarning("epoch")
    assert "epoch" in str(precision)
    assert precision.target_format is None

    model = ModelApproximationWarning(
        source_kind="mean elements", target_kind="state", fields=["state"]
    )
    assert model.model is None
    assert model.dropped[0].reason


# --- emission via the sanctioned seam ----------------------------------------------


def test_warn_lossy_is_catchable_as_a_family_with_payload_intact() -> None:
    with pytest.warns(LossyConversionWarning) as record:
        warn_lossy(DroppedFieldWarning("covariance", target_format="ccsds-oem"))
    assert len(record) == 1
    caught = record[0].message
    assert isinstance(caught, DroppedFieldWarning)
    assert caught.field == "covariance"
    assert caught.target_format == "ccsds-oem"
    assert [field.name for field in caught.dropped] == ["covariance"]


@pytest.mark.parametrize("cls", CONCRETE_WARNINGS)
def test_each_warning_is_catchable_by_its_own_type(cls: type[LossyConversionWarning]) -> None:
    with pytest.warns(cls):
        warn_lossy(_sample(cls))


# --- the no-silent-loss meta-test --------------------------------------------------
#
# Representative converters for the three conversion semantics decided at kickoff. A
# same-format write recovers full fidelity via source_native and stays warn-free; a
# cross-format projection warns per field the target cannot hold; a cross-category step
# warns on the model approximation. The real converters replace these as they land,
# reusing the same assert_no_silent_loss fixture.


def _same_format_roundtrip() -> object:
    """A same-format write recovers full fidelity via source_native — nothing is lost."""
    return b"<bytes>"


def _cross_format_projection() -> object:
    """A projection to a target that cannot hold every field warns per dropped field."""
    warn_lossy(DroppedFieldWarning("covariance", target_format="ccsds-oem"))
    return b"<bytes>"


def _cross_category_model_step() -> object:
    """A mean-elements to state conversion warns on the model step."""
    warn_lossy(
        ModelApproximationWarning(
            source_kind="mean elements", target_kind="state", fields=["state"], model="SGP4"
        )
    )
    return b"<bytes>"


@pytest.mark.parametrize(
    ("conversion", "loses"),
    [
        (_same_format_roundtrip, False),
        (_cross_format_projection, True),
        (_cross_category_model_step, True),
    ],
)
def test_no_converter_loses_information_without_warning(
    conversion: Callable[[], object],
    loses: bool,
    assert_no_silent_loss: Callable[..., None],
) -> None:
    """Information-dropping conversions raise a structured warning; lossless ones stay quiet."""
    assert_no_silent_loss(conversion, loses=loses)
