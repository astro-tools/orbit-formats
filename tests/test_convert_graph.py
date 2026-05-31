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
from orbit_formats.convert.graph import _TRANSFORMS, require_same_frame, route


@dataclass
class _NativeOem(FidelityModel):
    format_name = "ccsds-oem"
    raw: str = ""


def _ephemeris(*, frame: str = "TEME", native: FidelityModel | None = None) -> Ephemeris:
    return Ephemeris(
        metadata=Metadata(reference_frame=frame, time_scale="UTC", central_body="EARTH"),
        epochs=np.array(["2026-01-01T00:00:00"], dtype="datetime64[ns]"),
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


# --- the frame-rotation guard ------------------------------------------------------


def test_require_same_frame_passes_for_identical_frames() -> None:
    require_same_frame("TEME", "TEME")
    require_same_frame("teme", "  TEME ")  # case- and whitespace-insensitive


def test_require_same_frame_passes_when_a_frame_is_unknown() -> None:
    # An unknown frame on either side is not enough to assert a mismatch.
    require_same_frame(None, "EME2000")
    require_same_frame("EME2000", None)


def test_require_same_frame_rejects_a_cross_frame_rotation() -> None:
    with pytest.raises(FrameRotationUnsupportedError) as excinfo:
        require_same_frame("TEME", "EME2000")
    assert excinfo.value.source_frame == "TEME"
    assert excinfo.value.target_frame == "EME2000"
    assert "frame rotation" in str(excinfo.value)


def test_no_v01_conversion_silently_rotates_a_frame() -> None:
    # The frame-rotation boundary holds end to end on the v0.1 surface: a same-form
    # conversion returns the object with its frame intact (never rotated toward a target),
    # and the only cross-form route raises (see the unsupported-conversion test above)
    # rather than transforming. require_same_frame is the wired-in guard for v0.2's
    # frame-crossing edges; until then no convert path can rotate silently.
    eme2000 = _ephemeris(frame="EME2000")
    routed = convert(eme2000, to="ccsds-oem")  # same-form: ephemeris -> ephemeris
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
