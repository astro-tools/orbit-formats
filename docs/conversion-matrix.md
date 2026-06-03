# Conversion-capability matrix

Which conversions orbit-formats supports across the full format set, and what each costs. The
matrix is the contract: a cell is either lossless, lossy-with-a-named-reason, or
unsupported-with-a-reason — never a silent guess. The supported/unsupported split is derived from
the code (`orbit_formats.conversion_capability`) and a test asserts this page agrees with it, so
the published matrix cannot drift from the implementation.

## How routing works

Every format declares a preferred **canonical form**. A conversion routes through that form rather
than as a bespoke format pair:

| Form | Category type | Formats |
|------|---------------|---------|
| mean-elements | `MeanElementSet` | `tle`, `ccsds-omm`, `omm-json` / `omm-csv` (Celestrak / Space-Track flat OMM), `rinex-nav` (read-only — GNSS broadcast: GPS / Galileo / BeiDou / QZSS / NavIC) |
| state | `StateVector` | `ccsds-opm`, `gmat-report` (1 row), `rinex-nav` (read-only — GLONASS / SBAS) |
| ephemeris | `Ephemeris` | `ccsds-oem`, `stk-ephemeris`, `ccsds-ocm`, `spk`, `sp3` (read/write); `gmat-report` (≥2 rows) (read-only) |
| attitude | `Attitude` | `ccsds-aem` (history), `ccsds-apm` (single attitude), `stk-attitude` (STK `.a`) |
| conjunction | `Conjunction` | `ccsds-cdm` |
| tracking | `Tracking` | `ccsds-tdm` |
| ndm (aggregate) | `Combined` | `ccsds-ndm` |

A conversion whose source is already in the target's preferred form is a **same-form
pass-through**: the canonical object is handed straight to the target's writer. Two formats that
share a form therefore convert into each other — TLE ↔ OMM ↔ OMM-JSON ↔ OMM-CSV (mean-elements),
OEM ↔ STK ↔ OCM ↔ SPK ↔ SP3
(ephemeris), AEM ↔ APM ↔ STK-attitude (attitude) — carrying whatever the canonical object holds; the only cost is
whatever the *target writer* cannot express, which it names in a warning. A same-**format** write
(OEM → OEM) additionally recovers full fidelity from `source_native`.

Two **cross-form** bridges are propagator-free and so are implemented:

- **a single state ↔ a series.** A `StateVector` embeds as a length-1 `Ephemeris` (lossless), and an
  `Ephemeris` collapses to the `StateVector` at its first epoch (lossless for a one-sample series;
  for a longer one it warns, naming the dropped epochs). So `ccsds-opm` ↔ `ccsds-oem` / `ccsds-ocm`
  / `stk-ephemeris` convert both ways. The exception is `spk`: an SPK segment is an interpolatable
  trajectory of at least two states, so a single state cannot be written as one (it raises).
- **an attitude history ↔ a single attitude.** APM (single) embeds as a one-record AEM (lossless);
  an AEM history collapses to the first record for an APM, warning for the dropped records.

A conversion that would have to cross forms **through a model step** — a mean-element set to a
state or series (an SGP4 propagation), or a state/series to a mean-element set (an orbit fit) — is
out of scope and refused with `UnsupportedConversionError` rather than guessed. A `rinex-nav`
broadcast set additionally cannot become a TLE / OMM even though both are the mean-element form: it
carries a different *theory* (Toe-referenced, Earth-fixed), so it raises
`IncompatibleMeanElementTheoryError`. The `ccsds-ndm` aggregate carries no single form and never
converts — read it, work with its members, and write it back.

Orthogonal to the form is the **reference frame**. Pass `frame=` to `convert` (or `--frame` to the
CLI) to rotate the Cartesian state into another frame; see [Frame rotation](#frame-rotation).

## The matrix

Rows are the source format (anything readable); columns are the target format (only the writable
formats can be a conversion destination). **✅** lossless · **⚠️** lossy — warns and names what it
dropped · **❌** unsupported — raises. ✅ / ⚠️ are shown for a representative complete source of the
row format; a sparser file may warn where the table shows ✅. The guaranteed contract is the
✅ ∪ ⚠️ versus ❌ split (possible versus refused) and that no supported conversion ever drops a
canonical field silently — every ⚠️ names what it dropped.

<!-- capability-matrix: this table is asserted against orbit_formats.conversion_capability by
     tests/test_conversion_matrix.py::test_doc_matrix_matches_capabilities — keep it in sync. -->

| Source ╲ Target | `tle` | `ccsds-omm` | `ccsds-opm` | `ccsds-oem` | `stk-ephemeris` | `ccsds-ocm` | `spk` | `sp3` | `ccsds-aem` | `ccsds-apm` | `stk-attitude` | `ccsds-cdm` | `ccsds-tdm` | `ccsds-ndm` | `omm-json` | `omm-csv` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tle` | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ⚠️ |
| `ccsds-omm` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ⚠️ |
| `rinex-nav` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-opm` | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-oem` | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `stk-ephemeris` | ❌ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `sp3` | ❌ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `gmat-report` | ❌ | ❌ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-ocm` | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `spk` | ❌ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-aem` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-apm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `stk-attitude` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ | ⚠️ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-cdm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-tdm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `ccsds-ndm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `omm-json` | ⚠️ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| `omm-csv` | ⚠️ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |

`rinex-nav` and `gmat-report` are read into the form their content dictates, and the row above
shows that form's row: `rinex-nav` reads a GNSS *broadcast* mean set (the row shown — refused into
the SGP4 mean formats by theory, and into every other form by a missing model step) or a
GLONASS / SBAS `StateVector`; `gmat-report` reads an `Ephemeris` (≥2 rows, the row shown) or a
single-row `StateVector`. A `rinex-nav` GLONASS state or a one-row `gmat-report` state therefore
converts like the `ccsds-opm` row (into `ccsds-opm` / `ccsds-oem` / `stk-ephemeris` / `ccsds-ocm`).

## What each conversion carries

### Mean-element targets — `tle`, `ccsds-omm`, `omm-json`, `omm-csv`

TLE, the CCSDS OMM, and its Celestrak / Space-Track flat encodings (`omm-json`, `omm-csv`) all
share the mean-element form. The mean elements and the NORAD identifiers cross over; a bare
two-line TLE has no `OBJECT_NAME`, so writing it as an OMM (which requires one) warns and writes a
placeholder. `omm-json` and `omm-csv` are alternative *encodings* of the OMM, so they round-trip
into the CCSDS OMM and into each other carrying the same canonical set; the flat columns hold only
the operational fields, so writing an OMM that carries a header, comments, covariance, spacecraft
parameters, user-defined keys, or a non-TEME/UTC/SGP4 set warns, naming each field the encoding
cannot hold. A `rinex-nav` broadcast set is the same form but a different theory and an
Earth-fixed frame, so it is refused into all of them — `IncompatibleMeanElementTheoryError` (a
subclass of `UnsupportedConversionError`). A state or ephemeris to a mean set is an orbit fit, out
of scope.

### State target — `ccsds-opm`

A `ccsds-opm` round-trips losslessly, carrying its own maneuvers back from `source_native`. An
ephemeris source (`ccsds-oem` / `stk-ephemeris` / `sp3` / `gmat-report` / `ccsds-ocm` / `spk`)
collapses to the state at its **first epoch**; for a multi-sample series that warns, naming the
dropped epochs (and any interpolation hint). A synthesised OPM holds only the state and metadata,
so maneuvers an OCM source carries are dropped with a warning naming `maneuvers`. A one-row
`gmat-report` or a GLONASS `rinex-nav` reads directly as a state and round-trips like an OPM. A
mean-element set to a state needs a propagation, out of scope.

### Ephemeris targets — `ccsds-oem`, `stk-ephemeris`, `ccsds-ocm`, `spk`, `sp3`

These five share the ephemeris form, so they convert into one another carrying the states, frame,
central body, and interpolation hint. Format-specific extras a reader parks on `source_native` — an
OEM's covariance, SP3's clocks and other satellites — are not carried, since the canonical
ephemeris never held them. Maneuvers an OCM states (or, through the single → series bridge, an OPM)
*are* on the canonical object, but none of these five formats has a maneuver block, so a write
drops them with a warning naming `maneuvers`. Each target also warns for the fields *it* requires
that the canonical ephemeris does not supply:

- **`ccsds-oem`** requires `OBJECT_NAME` and `OBJECT_ID`; an STK, SP3, or GMAT source that lacks
  them gets placeholders, each named.
- **`stk-ephemeris`** requires a `CentralBody` (and a coordinate system); a GMAT report that omits
  them warns.
- **`ccsds-ocm`** requires `TIME_SYSTEM`, an epoch, a centre, and a frame — fields any well-formed
  ephemeris already carries, so it is usually lossless; a GMAT report missing the frame warns.
- **`spk`** synthesises a type-9 segment and warns when a NAIF id, frame, or time scale cannot be
  resolved. **A single state cannot be written as SPK** — an SPK segment is an interpolatable
  trajectory of at least two states — so `ccsds-opm` → `spk` raises `UnsupportedConversionError`.
- **`sp3`** writes a fixed-column SP3-d file. The satellite clock columns SP3 requires have no
  slot in the canonical ephemeris, so a synthesised SP3 **always** warns and writes the SP3
  missing-value sentinel; `object_name` becomes the system+PRN satellite id when it already is one
  (otherwise a placeholder is written, named), and a coordinate that overflows SP3's fixed F14.6
  field is truncated with a warning. Writing an SP3 source back to SP3 keeps every satellite and
  clock series from `source_native` (content-lossless), and a retained-source round trip is
  byte-identical.

A single state (`ccsds-opm`, a one-row report) embeds as a length-1 ephemeris, so it converts into
`ccsds-oem` / `stk-ephemeris` / `ccsds-ocm` (those accept a one-sample ephemeris); apart from any
maneuvers it carries — dropped as above — the conversion is lossless. A mean-element set to an
ephemeris needs a propagation, out of scope.

### Attitude targets — `ccsds-aem`, `ccsds-apm`, `stk-attitude`

AEM (a quaternion history), APM (a single quaternion attitude), and STK attitude (a `.a`
quaternion or Euler history) share the attitude form. APM → AEM writes a one-record history
(lossless). AEM → APM keeps the **first** record and warns, naming the dropped records — an APM
holds one attitude. A non-quaternion attitude (Euler, spin) cannot be written as an APM
(representing it as a quaternion would be a representation conversion, out of scope) and raises.

STK `.a` carries quaternions and Euler angles but, unlike the CCSDS pair, names only its
reference axes (`CoordinateAxes`): the object name / id and the body-frame name an AEM / APM
carries have no slot, so AEM / APM → STK attitude warns for what it drops. The reverse (STK →
AEM / APM) supplies the object identity and body frame STK leaves implicit as placeholders, also
warning. A spin attitude has no STK section here and raises.

### Conjunction, tracking — `ccsds-cdm`, `ccsds-tdm`

Each is its own form with a single writable format, so it round-trips to itself and nothing else: a
conjunction is not an orbit and a tracking-data set is not a state, so there is no meaningful
cross-form target.

### The aggregate — `ccsds-ndm`

The combined-NDM aggregate carries several member messages and no single canonical form, so it
never participates in conversion: `convert` to or from `ccsds-ndm` raises
`UnsupportedConversionError`. Read it, convert or inspect its members, and write it back.

## Frame rotation

`convert` rotates the Cartesian state into a requested reference frame when you pass `frame=` (the
CLI's `--frame`); omitted, the source frame is kept. The rotation is **lossless** — a rigid change
of axes, computed through `astropy` (precession / nutation for the inertial frames, the IERS
Earth-orientation tables and the Earth-rotation rate for the terrestrial ITRF), read hermetically
with no network access. It drops the byte-lossless `source_native` handle, since the rotated state
no longer matches the original bytes; the canonical content is exact.

| Rotation | TEME | EME2000 / J2000 | GCRF | ICRF | ITRF |
|----------|:----:|:---------------:|:----:|:----:|:----:|
| **supported** | ✅ | ✅ | ✅ | ✅ | ✅ |

Any one of the five frames rotates into any other; **GCRF and ICRF are identical** by definition,
so that pair is a no-op. The velocity is preserved by every rotation except across ITRF, where the
Earth-rotation term genuinely changes it (the same physical state, on rotating axes).

Out of scope:

- **A frame outside the set**, on either side, raises `FrameRotationUnsupportedError` —
  orbit-formats does not guess an un-modelled rotation.
- **A form with no Cartesian state** (a mean-element set, an attitude, a conjunction, a tracking
  set) has nothing to rotate; requesting a frame on one raises `FrameRotationUnsupportedError`.

## Geodetic projection

Once a state is in the Earth-fixed `ITRF`, the last step of a ground track is purely geometric:
projecting the ECEF Cartesian position onto a reference ellipsoid to read off a longitude,
latitude, and height. `cartesian_to_geodetic` and its inverse `geodetic_to_cartesian` do exactly
that, composing on top of the frame rotation above to give a full inertial → geodetic path.

Unlike the frame rotation, this is closed-form geometry — no precession, nutation, or
Earth-orientation data — so it is plain numpy with **no astropy dependency**: longitudes and
latitudes in degrees, heights and positions in km, the same unit convention as the rest of the
conversion layer. The latitude is geodetic (the angle of the local ellipsoid normal). The
reference ellipsoid is table-driven: pass a known name (`"WGS84"`, the default) or a custom
`Ellipsoid`, so another body can be projected without a new code path.

```python
import numpy as np
from orbit_formats.convert import (
    rotate_state,
    cartesian_to_geodetic,
    geodetic_to_cartesian,
    GeodeticLocation,
    Ellipsoid,
)

# An inertial (TEME) state at one epoch — position km, velocity km/s.
positions = np.array([[-4400.594, 1932.870, 4760.712]])
velocities = np.array([[-5.835, -4.929, -3.397]])
epochs = np.array(["2020-06-01T12:00:00"], dtype="datetime64[ns]")

# 1) rotate the inertial state into the Earth-fixed ITRF (precession / nutation / EOP).
ecef, _ = rotate_state(
    positions, velocities, epochs, time_scale="UTC", from_frame="TEME", to_frame="ITRF"
)

# 2) project the ECEF position onto the WGS84 ellipsoid — the sub-satellite point.
longitude, latitude, height = cartesian_to_geodetic(ecef)   # degrees, degrees, km

# The inverse places a geodetic coordinate back in ECEF.
back = geodetic_to_cartesian(longitude, latitude, height)   # (N, 3) km, round-trips `ecef`

# A fixed ground site is a small value type that carries its own ellipsoid.
site = GeodeticLocation(longitude=-75.7, latitude=45.4, height=0.076)   # km
site_ecef = site.to_cartesian()                                         # (3,) km
GeodeticLocation.from_cartesian(site_ecef)                              # back to lon/lat/height

# Another body is data, not code: pass a custom Ellipsoid.
moon = Ellipsoid(semi_major_axis=1737.4, inverse_flattening=float("inf"))   # a sphere
cartesian_to_geodetic(np.array([1200.0, 0.0, 1500.0]), ellipsoid=moon)
```

Both directions take and return plain numpy: a single `(3,)` position or an `(N, 3)` series,
vectorised over the leading axis. A name the table does not know raises `ValueError` rather than
guessing an ellipsoid.

> **Scope note.** The project charter lists "geodetic lat/lon/height output" and "a general
> frame-transformation engine" as non-goals. This projection is the deliberately narrow case: the
> single ellipsoid projection a ground-track consumer needs, composed on top of the `ITRF` rotation
> the library already performs — not a general geodesy toolkit (no geoid undulation, vertical
> datums, or access/visibility geometry, which remain out of scope). Accepting it is a conscious,
> scoped extension of the conversion layer.

## Reading the matrix in code

The table above is generated from the same code the converter uses; query it directly:

```python
from orbit_formats import conversion_capability, capability_matrix, convert, read, write

# Is a conversion possible, and why?
cap = conversion_capability("ccsds-opm", "spk")
print(cap.supported, cap.kind.value, cap.reason)
# False unsupported-degenerate 'spk' is an interpolatable trajectory of at least two states; ...

# The whole matrix as data:
for cap in capability_matrix():
    if cap.supported:
        ...  # cap.source_format, cap.target_format, cap.kind

# ✅ lossless OEM round trip (byte-identical with retain_source=True)
write(read("orbit.oem", retain_source=True), "copy.oem")

# ⚠️ a single state embeds, then collapses back out of the series — the collapse warns
state = convert("sat.oem", to="ccsds-opm")   # warns: kept the first epoch, dropped the rest

# ❌ a TLE to an OEM needs an SGP4 propagation — refused, not faked
convert("sat.tle", to="ccsds-oem")           # raises UnsupportedConversionError
```

See [Lossy conversions](lossy-conversions.md) for the warning types and how to catch them, and
[Formats](formats.md) for what each format can and cannot express.
