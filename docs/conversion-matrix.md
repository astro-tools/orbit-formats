# Conversion-capability matrix

Which conversions v0.1 supports, and what each costs. The matrix is the contract: a cell is
either lossless, lossy-with-a-named-reason, or unsupported-with-a-reason — never a silent
guess.

## How routing works

Every format declares a preferred **canonical form**. A conversion routes through that form
rather than as a bespoke format pair:

| Form | Category type | Formats (v0.1) |
|------|---------------|----------------|
| mean-elements | `MeanElementSet` | `tle` |
| ephemeris | `Ephemeris` | `ccsds-oem`, `stk-ephemeris`, `gmat-report` (≥2 rows) |
| state | `StateVector` | `gmat-report` (1 row) |

A conversion whose source is already in the target's preferred form is a pass-through (and a
same-format write stays lossless via `source_native`). A conversion that would have to cross
forms needs a transform — and in v0.1 the only cross-form step any pair would require is a
propagation, which is out of scope, so it is refused.

## Reading

| Source format | Reads into |
|---------------|------------|
| `tle` | `MeanElementSet` (mean elements, TEME / UTC) |
| `ccsds-oem` | `Ephemeris` |
| `stk-ephemeris` | `Ephemeris` |
| `gmat-report` | `Ephemeris` (multiple rows) or `StateVector` (one row) |

## Writing

CCSDS OEM and STK ephemeris are the writable **ephemeris** targets; the tables below are
therefore "source → each ephemeris target". A source already in the ephemeris form is a
same-form pass-through, so a same-format write recovers full fidelity via `source_native`.
Cross-format conversion carries what the **canonical** ephemeris holds (states, frame,
central body, interpolation) — format-specific extras a target's reader parks on
`source_native` (an OEM's covariance, an STK file's full meta) are not carried across formats,
since the canonical form never held them.

| Source | → CCSDS OEM |
|--------|-------------|
| **CCSDS OEM** | ✅ **lossless** — byte-identical when read with `retain_source=True`, otherwise content-lossless (every field, including covariance and acceleration, preserved) |
| **STK ephemeris** | ⚠️ **lossy** — the states, frame, central body, and interpolation cross over, but the OEM-required `OBJECT_NAME` and `OBJECT_ID` an STK file does not carry become placeholders, each named by a warning |
| **GMAT report** (≥2 rows) | ⚠️ **lossy** — the OEM-required fields a report does not state (`OBJECT_ID`, `CENTER_NAME`) become placeholders, each named by a warning |
| **GMAT report** (1 row) | ❌ **unsupported** — a single row reads as a `StateVector`; OEM expects an ephemeris, and bridging the two is not a conversion |
| **TLE** | ❌ **unsupported** — a mean-element set to an ephemeris requires a propagation (SGP4), which is out of scope; raises `UnsupportedConversionError` |

| Source | → STK ephemeris |
|--------|-----------------|
| **STK ephemeris** | ✅ **lossless** — byte-identical when read with `retain_source=True`, otherwise content-lossless (banner, comments, every meta keyword, and acceleration preserved) |
| **CCSDS OEM** | ✅ **lossless** for the canonical ephemeris — states, frame, central body, and interpolation cross over (an OEM states all the `.e`-required fields) |
| **GMAT report** (≥2 rows) | ⚠️ **lossy** — the STK-required `CentralBody` a report does not state (and `CoordinateSystem`, when its columns omit the frame) becomes a placeholder, named by a warning |
| **GMAT report** (1 row) | ❌ **unsupported** — a single row reads as a `StateVector`; STK ephemeris expects an ephemeris |
| **TLE** | ❌ **unsupported** — a mean-element set to an ephemeris requires a propagation (SGP4), which is out of scope; raises `UnsupportedConversionError` |

**Legend** — ✅ lossless · ⚠️ lossy, warns and names what was dropped · ❌ unsupported,
raises.

## Reading the legend in code

```python
from orbit_formats import convert, read, write

# ✅ lossless OEM round trip
eph = read("orbit.oem", retain_source=True)
write(eph, "copy.oem")                      # byte-identical

# ⚠️ GMAT report -> OEM warns for the META the report omits, and still writes
write(read("mission.report"), "mission.oem")

# ❌ TLE -> OEM is refused, not faked
convert("sat.tle", to="ccsds-oem")          # raises UnsupportedConversionError
```

See [Lossy conversions](lossy-conversions.md) for the warning types and how to catch them,
and [Formats](formats.md) for what each format can and cannot express.
