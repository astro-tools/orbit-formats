"""The conversion graph: same-form pass-through (lossless, source_native preserved), the
cross-frame-rotation guard, and the unsupported cross-form path through the public surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pytest

from orbit_formats import (
    Ephemeris,
    FidelityModel,
    FrameRotationUnsupportedError,
    Metadata,
    UnsupportedConversionError,
    convert,
)
from orbit_formats.convert.graph import _TRANSFORMS, apply_frame, route


@dataclass
class _NativeOem(FidelityModel):
    format_name = "ccsds-oem"
    raw: str = ""


def _ephemeris(*, frame: str = "TEME", native: FidelityModel | None = None) -> Ephemeris:
    # A 2020 epoch keeps any real rotation inside astropy's bundled IERS-B coverage.
    return Ephemeris(
        metadata=Metadata(reference_frame=frame, time_scale="UTC", central_body="EARTH"),
        epochs=np.array(["2020-06-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
        source_native=native,
    )


# --- routing -----------------------------------------------------------------------


def test_same_form_route_returns_the_same_object() -> None:
    ephemeris = _ephemeris()
    assert route(ephemeris, "ephemeris", "ephemeris") is ephemeris


def test_cross_form_route_has_no_v01_edge() -> None:
    # mean-elements -> ephemeris needs a propagator (out of scope); no edge exists.
    assert route(_ephemeris(), "mean-elements", "ephemeris") is None


def test_route_dispatches_a_registered_cross_form_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    # The v0.1 edge table is empty, but the routing machinery must dispatch an edge once
    # one is registered — this is the skeleton the later cross-form transforms plug into.
    sentinel = _ephemeris()
    monkeypatch.setitem(_TRANSFORMS, ("state", "ephemeris"), lambda _obj: sentinel)
    assert route(_ephemeris(), "state", "ephemeris") is sentinel


def test_same_form_pass_through_preserves_source_native_and_is_lossless(
    assert_no_silent_loss: Callable[..., None],
) -> None:
    native = _NativeOem(raw="CCSDS_OEM_VERS = 2.0")
    ephemeris = _ephemeris(native=native)

    result = convert(ephemeris, to="ccsds-oem")  # ephemeris-form -> ephemeris-form

    assert result is ephemeris
    assert result.source_native is native  # the byte-lossless write handle survives
    # A same-form conversion drops nothing, so it must stay warn-free.
    assert_no_silent_loss(lambda: convert(ephemeris, to="ccsds-oem"), loses=False)


def test_cross_form_conversion_is_unsupported_through_the_public_surface() -> None:
    # ephemeris -> ccsds-opm (state form) has no propagator-free edge in v0.1.
    with pytest.raises(UnsupportedConversionError):
        convert(_ephemeris(), to="ccsds-opm")


# --- the frame axis: apply_frame ---------------------------------------------------


def test_apply_frame_without_a_target_is_a_no_op() -> None:
    ephemeris = _ephemeris(frame="EME2000")
    assert apply_frame(ephemeris, None) is ephemeris  # frame preserved, source_native intact


def test_apply_frame_to_the_same_frame_is_a_no_op() -> None:
    # J2000 names the same frame as EME2000, so no rotation happens and the object is returned.
    ephemeris = _ephemeris(frame="EME2000")
    assert apply_frame(ephemeris, "J2000") is ephemeris


def test_apply_frame_rotates_a_supported_pair_and_drops_the_native_handle() -> None:
    native = _NativeOem(raw="CCSDS_OEM_VERS = 2.0")
    ephemeris = _ephemeris(frame="TEME", native=native)
    rotated = apply_frame(ephemeris, "J2000")
    assert isinstance(rotated, Ephemeris)
    assert rotated is not ephemeris
    assert rotated.metadata.reference_frame == "EME2000"  # tagged with the canonical target id
    assert rotated.source_native is None  # the verbatim handle no longer describes the state
    assert rotated.positions.shape == ephemeris.positions.shape
    assert not np.allclose(rotated.positions, ephemeris.positions)  # the axes actually moved
    np.testing.assert_allclose(  # a rigid rotation preserves the magnitude
        np.linalg.norm(rotated.positions, axis=1),
        np.linalg.norm(ephemeris.positions, axis=1),
        rtol=1e-9,
    )


def test_apply_frame_rejects_an_unknown_target_frame() -> None:
    with pytest.raises(FrameRotationUnsupportedError):
        apply_frame(_ephemeris(frame="TEME"), "NONSENSE")


def test_apply_frame_rejects_an_unknown_source_frame() -> None:
    # The state's own frame is unknown, so there is no defined rotation toward the target.
    with pytest.raises(FrameRotationUnsupportedError):
        apply_frame(_ephemeris(frame="WANDER"), "J2000")


def test_apply_frame_needs_a_time_scale() -> None:
    ephemeris = Ephemeris(
        metadata=Metadata(reference_frame="TEME"),  # no time_scale set
        epochs=np.array(["2020-06-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
    )
    with pytest.raises(ValueError, match="time scale"):
        apply_frame(ephemeris, "J2000")


def test_route_resolves_the_target_frame_before_the_form() -> None:
    # route threads the frame through: a same-form route with no frame returns the object
    # untouched (byte-lossless path intact), while one into a new frame returns the rotation.
    ephemeris = _ephemeris(frame="TEME")
    assert route(ephemeris, "ephemeris", "ephemeris") is ephemeris
    rotated = route(ephemeris, "ephemeris", "ephemeris", target_frame="J2000")
    assert isinstance(rotated, Ephemeris)
    assert rotated is not ephemeris
    assert rotated.metadata.reference_frame == "EME2000"


def test_no_conversion_rotates_a_frame_unless_asked() -> None:
    # The frame boundary holds end to end: a convert with no frame= keeps the source frame
    # verbatim (never rotated toward the target), preserving the byte-lossless path.
    eme2000 = _ephemeris(frame="EME2000")
    routed = convert(eme2000, to="ccsds-oem")  # same-form: ephemeris -> ephemeris
    assert routed is eme2000
    assert routed.metadata.reference_frame == "EME2000"  # preserved verbatim, not rotated


# --- the lazy convert-package surface ----------------------------------------------


def test_convert_package_lazily_exposes_the_time_helper() -> None:
    # The `convert` function shadows the `convert` subpackage as an attribute of
    # orbit_formats, so reach the package through the import system, not attribute access.
    import importlib

    from orbit_formats.convert.time import convert_time_scale

    convert_pkg = importlib.import_module("orbit_formats.convert")
    assert convert_pkg.convert_time_scale is convert_time_scale
    with pytest.raises(AttributeError):
        _ = convert_pkg.no_such_helper
