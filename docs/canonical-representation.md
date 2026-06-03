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

The category types are:

| Type | Holds | DataFrame? |
|------|-------|------------|
| `StateVector` | one Cartesian state (position + velocity) at one epoch | yes — one row |
| `Ephemeris` | a Cartesian state-vector time series | yes — N rows |
| `MeanElementSet` | a mean-element set (TLE / OMM-style), mean elements at an epoch | yes — one row |
| `Attitude` | an attitude history (CCSDS AEM / APM) | yes — N rows (one for an APM) |
| `Conjunction` | a close-approach record between two objects (CCSDS CDM) | no |
| `Tracking` | a tracking-data set (CCSDS TDM) | no |
| `Combined` | several member messages bundled in a combined NDM | no |

A `Combined` is the one *container* among them: it is what `read` returns for a combined
(aggregate) NDM, holding an ordered tuple of the member canonical objects above on
`Combined.messages` plus the wrapper's `message_id` and comments. It carries no payload of its
own — each member keeps its own metadata, payload, and `source_native`.

An **adapter** maps each fidelity model to and from the canonical metamodel. Reading routes
`format → fidelity model → canonical`; writing routes `canonical → fidelity model →
format`.

## The non-orbit categories

The orbit categories — `StateVector`, `Ephemeris`, `MeanElementSet` — describe *where* a body
is and project to the DataFrame. The three categories the CCSDS attitude, conjunction, and
tracking messages read into describe something else and carry their own fields. `Attitude` is a
time series like `Ephemeris`, so it too projects to a DataFrame — its own attitude-component
schema rather than the state schema; `Conjunction` and `Tracking` have no DataFrame projection:

- **`Attitude`** (AEM / APM) — how a body is *oriented*: the rotation from one reference frame to
  another, sampled at one epoch (APM) or over a time series (AEM). `attitude_type` tags the
  representation — `QUATERNION`, `EULER_ANGLE`, or `SPIN` — and `records` holds one row per
  `epochs` entry in that representation's columns; `frame_a` and `frame_b` name the two frames
  the rotation maps between (the spine's single `reference_frame` cannot, so it is left unset),
  with `euler_rot_seq` for the Euler case. Quaternions are stored scalar-last (`Q1 Q2 Q3 QC`)
  regardless of the source's notation.
- **`Conjunction`** (CDM) — a close approach between *two* objects: the time of closest approach
  `tca`, the `miss_distance`, the relative position / velocity / speed in the RTN frame, and a
  pair of `objects`. Each `ConjunctionObject` carries its designator, reference frame, its `(6,)`
  Cartesian state at TCA, and its `(6, 6)` RTN position/velocity covariance. The spine tags the
  primary object and the originator; the time scale is UTC (the CDM convention).
- **`Tracking`** (TDM) — the raw measurements a ground station records: the `participants` and a
  flat sequence of `observations`, each a `(observation_type, epoch, value)` triple, concatenated
  across the message's segments. The spine carries the originator and time scale.

Per-format specifics that have no slot in these schemas — an AEM's interpolation block, a CDM's
screen-volume and extended covariance, a TDM's full segment metadata — ride on the
`source_native` fidelity model below, exactly as the orbit categories' format-specific fields do.

## Maneuvers

OPM and OCM are the formats that state spacecraft maneuvers, and their burns are exposed as a
typed `Maneuver` record on the canonical object the format reads into — a `maneuvers` collection
on the `StateVector` (OPM) and on the `Ephemeris` (OCM). A `Maneuver` is not a category of its
own: a burn belongs to the body whose state it acts on, so it shares that object's metadata spine
rather than carrying one. Each record holds the burn's common denominator across the two formats:

| Field | Meaning |
|-------|---------|
| `epoch_ignition` | the ignition epoch |
| `ref_frame` | the frame the `delta_v` is expressed in (a burn names its own frame — often RTN — independent of the state's) |
| `duration` | seconds; `0.0` for an impulsive burn |
| `delta_v` | the `(3,)` Δv vector in km/s, when the source states it (else `None`) |
| `delta_mass` | the mass change in kg, when stated |
| `comments` | the block's leading comment lines |

```python
from orbit_formats import read

state = read("mission.opm")
for burn in state.maneuvers:
    print(burn.epoch_ignition, burn.ref_frame, burn.delta_v)
```

An OCM `man` block is read through its `MAN_COMPOSITION` columns: the time column places each
`manLine` (an absolute epoch, or seconds relative to `EPOCH_TZERO`), `DV_X` / `DV_Y` / `DV_Z` give
the Δv (scaled to km/s via `MAN_UNITS`), and `MAN_DURA` / `DELTA_MASS` fill the duration and mass
change. Composition columns the record has no slot for — thrust, deterministic-command timing,
per-element sigmas — stay on `source_native`, like every other format-specific field.

The maneuvers ride through the conversion layer (a frame rotation or a single ↔ series bridge
carries them verbatim — a burn's Δv is not rotated), and a same-format write recovers them from
`source_native`. A write to a format with no maneuver block drops them, naming the loss through a
`LossyConversionWarning` rather than dropping it in silence.

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
| `reference_frame` | the frame the state is expressed in (tagged; rotated on request across TEME / EME2000 / GCRF / ICRF / ITRF) |
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

`Attitude.to_dataframe()` projects an attitude time series the same way, so every time-series
category — `Ephemeris`, `StateVector`, `MeanElementSet`, and `Attitude` — has a DataFrame form.
Its columns are `Epoch` plus the component columns of the attitude's representation: `Q1`, `Q2`,
`Q3`, `QC` for a `QUATERNION`, `ANGLE_1`, `ANGLE_2`, `ANGLE_3` for an `EULER_ANGLE`, and
`SPIN_ALPHA`, `SPIN_DELTA`, `SPIN_ANGLE`, `SPIN_ANGLE_VEL` for a `SPIN` — one row per epoch (many
for an AEM history, one for an APM). Its `attrs` carry the same metadata spine plus the
attitude-specific `attitude_type` and the `frame_a` / `frame_b` / `euler_rot_seq` tags when set.
The frame pair lives on `frame_a` / `frame_b`, not the spine's single `coordinate_system`, so that
key is absent.

```python
df = att.to_dataframe()
df.columns.tolist()          # ['Epoch', 'Q1', 'Q2', 'Q3', 'QC'] for a quaternion attitude
df.attrs["attitude_type"]    # 'QUATERNION'
df.attrs["frame_a"], df.attrs["frame_b"]
```

The round trip `Ephemeris.from_dataframe(eph.to_dataframe())` reproduces the projected
content without drift, so the DataFrame is a stable contract in both directions.
