# Canonical representation

orbit-formats holds every format in a two-layer model. Understanding the split is the key
to the lossless-round-trip guarantee and to the DataFrame schema downstream consumers
adopt.

## The two layers

**The format-fidelity layer.** Each reader parses its format into a faithful model that
holds *every* field the format defines — the raw TLE lines, an OEM's full header and
per-segment META / covariance / acceleration blocks, a GMAT report's every column and
cell. A same-format round-trip stays at this layer and never down-projects, so it loses
nothing.

**The canonical metamodel.** Above the fidelity layer sits the small, format-agnostic
dataclass family consumers actually speak. It is *federated*, not universal: a shared
metadata spine plus a category type per kind of object, rather than one god-model spanning
genuinely different domain objects.

The v0.1 category types are:

| Type | Holds | DataFrame? |
|------|-------|------------|
| `StateVector` | one Cartesian state (position + velocity) at one epoch | yes — one row |
| `Ephemeris` | a Cartesian state-vector time series | yes — N rows |
| `MeanElementSet` | a mean-element set (TLE / OMM-style), mean elements at an epoch | yes — one row |

(`Attitude`, `Conjunction`, and `Tracking` are reserved for later versions and carry no
v0.1 payload.)

An **adapter** maps each fidelity model to and from the canonical metamodel. Reading routes
`format → fidelity model → canonical`; writing routes `canonical → fidelity model →
format`.

## `source_native` — the round-trip handle

A canonical object keeps an optional handle, `source_native`, back to the fidelity model it
was read from. A same-format write recovers full fidelity from that handle without the
format-specific fields ever polluting the clean canonical schema. Covariance and
acceleration blocks an OEM carries, a TLE's exact lines, a GMAT report's extra columns — all
survive on `source_native` even though the canonical `Ephemeris` has no slot for them.

`source_native` is excluded from equality: two canonical objects with the same content are
equal regardless of which native handle (if any) is attached.

Pass `retain_source=True` to keep the raw source bytes as well, so a same-format write
reproduces the input **byte-for-byte**:

```python
from orbit_formats import read, write

eph = read("orbit.oem", retain_source=True)
write(eph, "copy.oem")          # byte-identical to orbit.oem
```

Without `retain_source`, a same-format write is **content-lossless** instead — every field
preserved, re-serialised in canonical formatting.

## The metadata spine

Every canonical object carries a typed, validated `Metadata` spine *on the object*, never
parked in a pandas `attrs` dict (pandas drops `attrs` on most operations, which a
lossless-round-trip library cannot depend on). The spine fields:

| Field | Meaning |
|-------|---------|
| `object_name` | the object's name |
| `object_id` | catalogue / international designator (e.g. a NORAD id, `1998-067A`) |
| `originator` | the producing agency |
| `reference_frame` | the frame the state is expressed in (tagged, not rotated in v0.1) |
| `central_body` | the gravitational centre |
| `time_scale` | one of `UTC` / `TAI` / `TT` / `TDB` / `GPS` / `UT1` |
| `units` | a `UnitSpec` (defaults: km, km/s, deg, s) |
| `provenance` | a `Provenance` record (`source_format`, `creation_date`, `header`) |

A field the source does not state is left `None` rather than guessed.

## The DataFrame schema

`Ephemeris.to_dataframe()` is the projection downstream consumers adopt as the contract. It
is identical to the schema gmat-run already emits, so a consumer needs zero reshaping.

**Columns** — `Epoch` (`datetime64[ns]`), then `X`, `Y`, `Z`, `VX`, `VY`, `VZ` (`float64`).

**`DataFrame.attrs`** — the metadata spine, materialised at the edge:

| Key | Source |
|-----|--------|
| `object_name` | `metadata.object_name` (set when known) |
| `central_body` | `metadata.central_body` (set when known) |
| `coordinate_system` | `metadata.reference_frame` (set when known) |
| `time_scale` | `metadata.time_scale` (set when known) |
| `epoch_scales` | `{"Epoch": time_scale}` (set when the time scale is known) |
| `units` | `{"length", "speed", "angle", "time"}` |
| `interpolation`, `interpolation_degree` | the source ephemeris's interpolation hint, when present |

```python
df = eph.to_dataframe()
df.columns.tolist()          # ['Epoch', 'X', 'Y', 'Z', 'VX', 'VY', 'VZ']
df.attrs["coordinate_system"]
df.attrs["time_scale"]
```

The projection is the canonical *edge* form: values are plain numpy (no astropy objects
leak), and provenance and the `source_native` handle stay on the object, not in the
DataFrame. `StateVector.to_dataframe()` produces the same schema with a single row;
`MeanElementSet.to_dataframe()` uses a mean-element schema instead (`Epoch`, `MeanMotion`,
`Eccentricity`, `Inclination`, `RAAN`, `ArgPeriapsis`, `MeanAnomaly`, `BStar`,
`MeanMotionDot`, `MeanMotionDdot`).

The round trip `Ephemeris.from_dataframe(eph.to_dataframe())` reproduces the projected
content without drift, so the DataFrame is a stable contract in both directions.
