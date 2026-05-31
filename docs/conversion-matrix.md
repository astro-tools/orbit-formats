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
| ephemeris | `Ephemeris` | `ccsds-oem`, `gmat-report` (≥2 rows) |
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
| `gmat-report` | `Ephemeris` (multiple rows) or `StateVector` (one row) |

## Writing

CCSDS OEM is the only writable format in v0.1. The matrix below is therefore "source → CCSDS
OEM"; more targets land as their writers do.

| Source | → CCSDS OEM |
|--------|-------------|
| **CCSDS OEM** | ✅ **lossless** — byte-identical when read with `retain_source=True`, otherwise content-lossless (every field, including covariance and acceleration, preserved) |
| **GMAT report** (≥2 rows) | ⚠️ **lossy** — the OEM-required fields a report does not state (`OBJECT_ID`, `CENTER_NAME`) become placeholders, each named by a warning |
| **GMAT report** (1 row) | ❌ **unsupported** — a single row reads as a `StateVector`; OEM expects an ephemeris, and bridging the two is not a v0.1 conversion |
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
