"""Tests for the two-layer plumbing: the fidelity-model base and the adapter protocol."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

from orbit_formats import Ephemeris, FidelityModel, Metadata, StateVector
from orbit_formats.adapters import Adapter

_Row = tuple[str, float, float, float, float, float, float]


@dataclass
class _ToyOem(FidelityModel):
    """A stand-in fidelity model — every field a (toy) format defines."""

    format_name = "toy-oem"
    raw_header: str = ""
    rows: list[_Row] = field(default_factory=list)


def test_fidelity_subclass_must_declare_format_name() -> None:
    with pytest.raises(TypeError, match="format_name"):

        class _Bad(FidelityModel):
            pass


def test_fidelity_subclass_with_format_name_is_usable() -> None:
    model = _ToyOem(
        raw_header="CCSDS_OEM_VERS = 2.0", rows=[("2026-01-01T00:00:00", 7000, 0, 0, 0, 7.5, 0)]
    )
    assert model.format_name == "toy-oem"
    assert isinstance(model, FidelityModel)


def _ephemeris(*, source_native: FidelityModel | None) -> Ephemeris:
    return Ephemeris(
        metadata=Metadata(reference_frame="TEME", time_scale="UTC"),
        epochs=np.array(["2026-01-01T00:00:00"], dtype="datetime64[ns]"),
        positions=np.array([[7000.0, 0.0, 0.0]]),
        velocities=np.array([[0.0, 7.5, 0.0]]),
        source_native=source_native,
    )


def test_source_native_handle_is_carried_but_excluded_from_equality() -> None:
    native = _ToyOem(raw_header="h")
    with_native = _ephemeris(source_native=native)
    without_native = _ephemeris(source_native=None)
    # the native handle is reachable and typed...
    assert with_native.source_native is native
    assert with_native.source_native is not None
    assert with_native.source_native.format_name == "toy-oem"
    # ...but two canonical objects with identical content are equal regardless of it
    assert with_native == without_native


class _ToyAdapter:
    """A structural :class:`Adapter` — maps the toy fidelity model to/from canonical."""

    def to_canonical(self, fidelity: _ToyOem) -> StateVector:
        _, x, y, z, vx, vy, vz = fidelity.rows[0]
        return StateVector(
            metadata=Metadata(),
            epoch=np.datetime64("2026-01-01T00:00:00", "ns"),
            position=np.array([x, y, z]),
            velocity=np.array([vx, vy, vz]),
            source_native=fidelity,
        )

    def from_canonical(self, canonical: StateVector) -> _ToyOem:
        x, y, z = canonical.position
        vx, vy, vz = canonical.velocity
        return _ToyOem(rows=[("2026-01-01T00:00:00", x, y, z, vx, vy, vz)])


def test_adapter_protocol_is_satisfied_structurally() -> None:
    adapter: Adapter[_ToyOem, StateVector] = _ToyAdapter()
    native = _ToyOem(rows=[("2026-01-01T00:00:00", 7000.0, 1.0, 2.0, 0.0, 7.5, 0.1)])
    canonical = adapter.to_canonical(native)
    assert isinstance(canonical, StateVector)
    assert canonical.source_native is native
    round_tripped = adapter.from_canonical(canonical)
    assert round_tripped.rows[0][1] == 7000.0
