# Conversion-capability matrix

Which conversions orbit-formats supports, and what each costs. The matrix is the contract: a
cell is either lossless, lossy-with-a-named-reason, or unsupported-with-a-reason — never a
silent guess.

## How routing works

Every format declares a preferred **canonical form**. A conversion routes through that form
rather than as a bespoke format pair:

| Form | Category type | Formats |
|------|---------------|---------|
| mean-elements | `MeanElementSet` | `tle`, `ccsds-omm` |
| ephemeris | `Ephemeris` | `ccsds-oem`, `stk-ephemeris`, `sp3` (read-only), `gmat-report` (≥2 rows) |
| state | `StateVector` | `ccsds-opm`, `gmat-report` (1 row) |

A conversion whose source is already in the target's preferred form is a **pass-through**: the
canonical object is handed straight to the target's writer, and a same-format write stays
lossless via `source_native`. Two formats that share a form therefore convert into each
other — TLE ↔ OMM (mean-elements), OEM ↔ STK (ephemeris) — with no transform between them; the
only cost is whatever the *target writer* cannot express.

A conversion that would have to **cross forms** — a mean-element set to an ephemeris, a single
state to a series — needs a model step (a propagation or an orbit fit) that is out of scope, so
it is refused with `UnsupportedConversionError` rather than guessed.

Orthogonal to the form is the **reference frame**. Pass `frame=` to `convert` (or `--frame` to
the CLI) to rotate the Cartesian state into another frame; see
[Frame rotation](#frame-rotation) below.

## Reading

| Source format | Reads into |
|---------------|------------|
| `tle` | `MeanElementSet` (mean elements, TEME / UTC) |
| `ccsds-omm` | `MeanElementSet` |
| `ccsds-opm` | `StateVector` |
| `ccsds-oem` | `Ephemeris` |
| `stk-ephemeris` | `Ephemeris` |
| `sp3` | `Ephemeris` — the first satellite (ITRF, SP3 time system); the full per-satellite set on `source_native` |
| `gmat-report` | `Ephemeris` (≥2 rows) or `StateVector` (one row) |
| `ccsds-ndm` | `Combined` — an ordered tuple of the member messages, each read into its own type |

A `ccsds-ndm` aggregate is read and written but never **converted**: it carries no single
canonical form, so it composes member messages rather than mapping between forms. `convert` to
or from `ccsds-ndm` raises `UnsupportedConversionError`; read it, work with its members, and
write it back.

## Writing

A source already in the target's form is a same-form pass-through, so a same-format write
recovers full fidelity via `source_native`. Cross-format conversion within a form carries what
the **canonical** object holds — for an ephemeris the states, frame, central body, and
interpolation — while format-specific extras a reader parks on `source_native` (an OEM's
covariance, an STK file's full meta, an OPM's maneuvers) are not carried across formats, since
the canonical form never held them.

The tables below are grouped by the target's form. CCSDS OEM, OMM, and OPM additionally select
KVN vs XML from the destination extension (`.oem` / `.omm` / `.opm` → KVN, `.xml` → XML); the
content is identical either way.

### Mean-element targets — TLE, CCSDS OMM

| Source | → TLE | → CCSDS OMM |
|--------|-------|-------------|
| **TLE** | ✅ **lossless** — the source lines are echoed verbatim (byte-identical for a normalised TLE) | ✅ **lossless** — the TLE → OMM map enriches the message with the TLE's identifiers and drag terms; a nameless 2-line TLE warns for the OMM-required `OBJECT_NAME` |
| **CCSDS OMM** | ⚠️ **lossy** — element-level lossless (a re-read reproduces the same mean elements to the TLE's representable precision), but warns for each TLE identifier the OMM does not carry (`NORAD_CAT_ID`, `ELEMENT_SET_NO`, the international designator) | ✅ **lossless** — byte-identical with `retain_source=True`, otherwise content-lossless (spacecraft, covariance, and user-defined blocks preserved) |
| **ephemeris / state source** | ❌ **unsupported** — a Cartesian state or series to a mean-element set is an orbit fit, out of scope; raises `UnsupportedConversionError` | ❌ **unsupported** — same: a mean-element set cannot be derived from a state without an orbit fit |

### State target — CCSDS OPM

| Source | → CCSDS OPM |
|--------|-------------|
| **CCSDS OPM** | ✅ **lossless** — byte-identical with `retain_source=True`, otherwise content-lossless (the state, Keplerian, spacecraft, covariance, and maneuver blocks all preserved) |
| **GMAT report** (1 row) | ⚠️ **lossy** — the Cartesian state crosses over, but each OPM-required metadata field the report does not state (`OBJECT_NAME`, `OBJECT_ID`, `CENTER_NAME`, and `REF_FRAME` / `TIME_SYSTEM` when the columns omit them) becomes a placeholder, each named by a warning |
| **ephemeris / mean-element source** | ❌ **unsupported** — a series or a mean-element set to a single state crosses forms; raises `UnsupportedConversionError` |

### Ephemeris targets — CCSDS OEM, STK ephemeris

CCSDS OEM and STK ephemeris are the writable **ephemeris** targets.

| Source | → CCSDS OEM | → STK ephemeris |
|--------|-------------|-----------------|
| **CCSDS OEM** | ✅ **lossless** — byte-identical with `retain_source=True`, otherwise content-lossless (every field, including covariance and acceleration, preserved) | ✅ **lossless** for the canonical ephemeris — states, frame, central body, and interpolation cross over (an OEM states all the `.e`-required fields) |
| **STK ephemeris** | ⚠️ **lossy** — the states, frame, central body, and interpolation cross over, but the OEM-required `OBJECT_NAME` / `OBJECT_ID` an STK file does not carry become placeholders, each named by a warning | ✅ **lossless** — byte-identical with `retain_source=True`, otherwise content-lossless (banner, comments, every meta keyword, and acceleration preserved) |
| **SP3** (first satellite) | ⚠️ **lossy** — the satellite's states, the ITRF frame, the Earth centre, and its id cross over; the OEM-required `OBJECT_ID` SP3 does not carry becomes a placeholder, named by a warning; the clock, accuracy codes, and the other satellites stay on `source_native` | ✅ **lossless** for the canonical ephemeris — the states, the ITRF frame, and the Earth centre cross over (SP3 states all the `.e`-required fields); the clock, accuracy codes, and the other satellites stay on `source_native` |
| **GMAT report** (≥2 rows) | ⚠️ **lossy** — the OEM-required fields a report does not state (`OBJECT_ID`, `CENTER_NAME`) become placeholders, each named by a warning | ⚠️ **lossy** — the STK-required `CentralBody` a report does not state (and `CoordinateSystem`, when its columns omit the frame) becomes a placeholder, named by a warning |
| **single-state source** (OPM, 1-row report) | ❌ **unsupported** — a single state reads as a `StateVector`; an ephemeris target expects a series, and bridging the two is not a conversion | ❌ **unsupported** — same |
| **mean-element source** (TLE, OMM) | ❌ **unsupported** — a mean-element set to an ephemeris requires a propagation (SGP4), out of scope; raises `UnsupportedConversionError` | ❌ **unsupported** — same |

**Legend** — ✅ lossless · ⚠️ lossy, warns and names what was dropped · ❌ unsupported, raises.

## Frame rotation

`convert` rotates the Cartesian state into a requested reference frame when you pass `frame=`
(the CLI's `--frame`); omitted, the source frame is kept. The rotation is **lossless** — a
rigid change of axes, computed through `astropy` (precession / nutation for the inertial
frames, the IERS Earth-orientation tables and the Earth-rotation rate for the terrestrial
ITRF), read hermetically with no network access. It drops the byte-lossless `source_native`
handle, since the rotated state no longer matches the original bytes; the canonical content is
exact.

| Rotation | TEME | EME2000 / J2000 | GCRF | ICRF | ITRF |
|----------|:----:|:---------------:|:----:|:----:|:----:|
| **supported** | ✅ | ✅ | ✅ | ✅ | ✅ |

Any one of the five frames rotates into any other; **GCRF and ICRF are identical** by
definition, so that pair is a no-op. The velocity is preserved by every rotation except across
ITRF, where the Earth-rotation term genuinely changes it (the same physical state, on rotating
axes).

Out of scope:

- **A frame outside the set**, on either side, raises `FrameRotationUnsupportedError` —
  orbit-formats does not guess an un-modelled rotation.
- **A mean-element set** (a TLE or OMM) has no Cartesian state to rotate; requesting a frame on
  one raises `FrameRotationUnsupportedError`. Its frame is TEME — tagged and preserved.

## Reading the legend in code

```python
from orbit_formats import convert, read, write

# ✅ lossless OEM round trip
eph = read("orbit.oem", retain_source=True)
write(eph, "copy.oem")                      # byte-identical

# ✅ lossless TLE -> OMM (same mean-element form)
write(convert("iss.tle", to="ccsds-omm"), "iss.omm")

# ✅ lossless frame rotation into J2000
write(convert("orbit.oem", to="ccsds-oem", frame="J2000"), "j2000.oem")

# ⚠️ GMAT report -> OEM warns for the META the report omits, and still writes
write(read("mission.report"), "mission.oem")

# ❌ TLE -> OEM is refused, not faked
convert("sat.tle", to="ccsds-oem")          # raises UnsupportedConversionError
```

See [Lossy conversions](lossy-conversions.md) for the warning types and how to catch them, and
[Formats](formats.md) for what each format can and cannot express.
