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
| mean-elements | `MeanElementSet` | `tle`, `ccsds-omm`, `rinex-nav` (read-only — GNSS broadcast: GPS / Galileo / BeiDou / QZSS / NavIC) |
| state | `StateVector` | `ccsds-opm`, `gmat-report` (1 row), `rinex-nav` (read-only — GLONASS / SBAS) |
| ephemeris | `Ephemeris` | `ccsds-oem`, `stk-ephemeris`, `ccsds-ocm`, `spk` (read/write); `sp3`, `gmat-report` (≥2 rows) (read-only) |
| attitude | `Attitude` | `ccsds-aem` (history), `ccsds-apm` (single attitude) |
| conjunction | `Conjunction` | `ccsds-cdm` |
| tracking | `Tracking` | `ccsds-tdm` |
| ndm (aggregate) | `Combined` | `ccsds-ndm` |

A conversion whose source is already in the target's preferred form is a **same-form
pass-through**: the canonical object is handed straight to the target's writer. Two formats that
share a form therefore convert into each other — TLE ↔ OMM (mean-elements), OEM ↔ STK ↔ OCM ↔ SPK
(ephemeris), AEM ↔ APM (attitude) — carrying whatever the canonical object holds; the only cost is
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

| Source ╲ Target | `tle` | `ccsds-omm` | `ccsds-opm` | `ccsds-oem` | `stk-ephemeris` | `ccsds-ocm` | `spk` | `ccsds-aem` | `ccsds-apm` | `ccsds-cdm` | `ccsds-tdm` | `ccsds-ndm` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tle` | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-omm` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `rinex-nav` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-opm` | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-oem` | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `stk-ephemeris` | ❌ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `sp3` | ❌ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `gmat-report` | ❌ | ❌ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-ocm` | ❌ | ❌ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `spk` | ❌ | ❌ | ⚠️ | ⚠️ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ccsds-aem` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ⚠️ | ❌ | ❌ | ❌ |
| `ccsds-apm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `ccsds-cdm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `ccsds-tdm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| `ccsds-ndm` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

`rinex-nav` and `gmat-report` are read into the form their content dictates, and the row above
shows that form's row: `rinex-nav` reads a GNSS *broadcast* mean set (the row shown — refused into
the SGP4 mean formats by theory, and into every other form by a missing model step) or a
GLONASS / SBAS `StateVector`; `gmat-report` reads an `Ephemeris` (≥2 rows, the row shown) or a
single-row `StateVector`. A `rinex-nav` GLONASS state or a one-row `gmat-report` state therefore
converts like the `ccsds-opm` row (into `ccsds-opm` / `ccsds-oem` / `stk-ephemeris` / `ccsds-ocm`).

## What each conversion carries

### Mean-element targets — `tle`, `ccsds-omm`

TLE ↔ OMM share the mean-element form. The mean elements and the NORAD identifiers cross over; a
bare two-line TLE has no `OBJECT_NAME`, so writing it as an OMM (which requires one) warns and
writes a placeholder. A `rinex-nav` broadcast set is the same form but a different theory and an
Earth-fixed frame, so it is refused into both — `IncompatibleMeanElementTheoryError` (a subclass of
`UnsupportedConversionError`). A state or ephemeris to a mean set is an orbit fit, out of scope.

### State target — `ccsds-opm`

A `ccsds-opm` round-trips losslessly. An ephemeris source (`ccsds-oem` / `stk-ephemeris` / `sp3` /
`gmat-report` / `ccsds-ocm` / `spk`) collapses to the state at its **first epoch**; for a
multi-sample series that warns, naming the dropped epochs (and any interpolation hint). A
one-row `gmat-report` or a GLONASS `rinex-nav` reads directly as a state and round-trips like an
OPM. A mean-element set to a state needs a propagation, out of scope.

### Ephemeris targets — `ccsds-oem`, `stk-ephemeris`, `ccsds-ocm`, `spk`

These four share the ephemeris form, so they convert into one another carrying the states, frame,
central body, and interpolation hint; format-specific extras a reader parks on `source_native` (an
OEM's covariance, an OPM's maneuvers, SP3's clocks and other satellites) are not carried, since the
canonical ephemeris never held them. Each target warns for the fields *it* requires that the
canonical ephemeris does not supply:

- **`ccsds-oem`** requires `OBJECT_NAME` and `OBJECT_ID`; an STK, SP3, or GMAT source that lacks
  them gets placeholders, each named.
- **`stk-ephemeris`** requires a `CentralBody` (and a coordinate system); a GMAT report that omits
  them warns.
- **`ccsds-ocm`** requires `TIME_SYSTEM`, an epoch, a centre, and a frame — fields any well-formed
  ephemeris already carries, so it is usually lossless; a GMAT report missing the frame warns.
- **`spk`** synthesises a type-9 segment and warns when a NAIF id, frame, or time scale cannot be
  resolved. **A single state cannot be written as SPK** — an SPK segment is an interpolatable
  trajectory of at least two states — so `ccsds-opm` → `spk` raises `UnsupportedConversionError`.

A single state (`ccsds-opm`, a one-row report) embeds as a length-1 ephemeris, so it converts into
`ccsds-oem` / `stk-ephemeris` / `ccsds-ocm` losslessly (those accept a one-sample ephemeris). A
mean-element set to an ephemeris needs a propagation, out of scope.

### Attitude targets — `ccsds-aem`, `ccsds-apm`

AEM (a quaternion history) and APM (a single quaternion attitude) share the attitude form. APM →
AEM writes a one-record history (lossless). AEM → APM keeps the **first** record and warns, naming
the dropped records — an APM holds one attitude. A non-quaternion attitude (Euler, spin) cannot be
written as an APM (representing it as a quaternion would be a representation conversion, out of
scope) and raises.

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
