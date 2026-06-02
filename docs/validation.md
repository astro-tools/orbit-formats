# Validation

orbit-formats earns the lossless-round-trip promise by testing it against **independent external
references**, not against itself. The conversion layer is built on `astropy` internally, so a
check against `astropy` is a useful self-consistency test but not an independent one — the
reference and the implementation share a library. The oracles on this page close that gap: each
is a separate, independently developed implementation that confirms the bytes orbit-formats
writes, and the conversions it computes, are right against an outside authority.

## What is checked

- **Golden round-trips.** A committed corpus of reference files for every supported format is
  read into the canonical form and written back, then diffed against the golden. Same-format
  round-trips are lossless; cross-format round-trips are lossless only where the formats overlap,
  and every dropped field is asserted to have [warned](lossy-conversions.md).
- **The conversion-capability matrix is generated from the code.** A test asserts the published
  [matrix](conversion-matrix.md) agrees with `orbit_formats.conversion_capability`, so the
  contract cannot drift from the implementation.
- **The package stays permissively licensed.** A smoke test installs the package with no extras
  and no dev group and imports it, catching any oracle or extra dependency leaking into the base
  install path.
- **The platform spread.** The suite runs on Linux, Windows, and macOS across Python 3.10, 3.11,
  and 3.12.

## The external oracles

Three oracles cross-validate the parts of orbit-formats where an independent reference exists:
the CCSDS writers, the conversion layer, and the SPK round-trip.

!!! note "The oracles are dev / CI-only — never shipped"
    No oracle is a runtime dependency, an optional extra, or even a dev-group dependency, and
    none appears in the lock file. The package never imports any of them. Each runs in a
    dedicated CI job that installs its reference transiently, and every oracle test
    `importorskip`s its reference, so it simply skips everywhere else — the main test matrix, a
    normal local run. This is what keeps orbit-formats permissively licensed end-to-end: the
    most complete CCSDS reference, `ccsds-ndm`, is GPL-3.0, and using it only as a CI oracle —
    never linked, never distributed — means orbit-formats and everything that depends on it stay
    free of that copyleft.

### CCSDS messages — `ccsds-ndm` and the official XSDs

The CCSDS writers are validated by re-parsing their output with an independent library and
checking it against the canonical object that produced it:

- **`ccsds-ndm` (GPL-3.0)** parses the KVN and XML orbit-formats emits for OEM, OMM, OPM, AEM,
  APM, CDM, and TDM, and the combined NDM. The oracle asserts the message it reads back carries
  the same identity, frames, states, and records as the canonical object written — so the bytes
  are valid CCSDS an outside library reads as the same message, not merely a file orbit-formats
  can re-read.
- **`xmlschema` (MIT)** validates the OCM (and the combined-NDM XML wrapper) against the vendored
  official CCSDS XSD. `ccsds-ndm` predates the OCM and cannot parse it, so the schema is the
  independent authority there: the XML orbit-formats writes is asserted valid against the
  standard's own grammar.

### Conversions — Orekit

[Orekit](https://www.orekit.org/) is a mature, independently developed space-dynamics library
(Java, Apache-2.0) with its own precession / nutation, reference-frame, and time-scale
machinery. It is bridged through `orekit-jpype` on a pip-only JDK — no system Java, no repository
dependency — in a throwaway CI environment, and cross-validates the conversion layer:

- **Element conversion** — Cartesian ↔ Keplerian, given a gravitational parameter passed
  explicitly to both sides so the check isolates the algebra rather than a difference in the
  constant.
- **Frame rotation** — across TEME, EME2000 / J2000, GCRF, ICRF, and ITRF. (orbit-formats' `ICRF`
  is the geocentric, GCRF-aligned frame, so the oracle maps it onto Orekit's geocentric frame —
  the one we actually mean.)
- **Time-scale conversion** — across UTC, TAI, TT, TDB, and GPS.

The reference Earth-orientation and leap-second data is a pinned `orekit-data` snapshot the CI
job fetches once at install time; the cross-check itself touches no network. Tolerances are
calibrated per conversion family and reflect genuine `astropy`-vs-Orekit model differences, not
arbitrary slack — agreement to those bounds means the conversions are right against an outside
authority, not merely internally consistent.

### SPK — SPICE

The [SPK](formats.md#spk-spk-extra-spk) reader and writer are built on `spiceypy`'s low-level DAF
segment primitives. The SPK oracle closes the loop with a genuinely independent path: it
furnishes the kernel orbit-formats wrote and asks SPICE's own high-level geometric-state
evaluator (`spkgeo`) to interpolate the states back. `spkgeo` walks the SPK interpolation
machinery, not orbit-formats' DAF parser, so agreement means the bytes emitted are a valid SPK an
outside toolkit reads as the same trajectory. The states are asserted to match node-for-node to
**1 µm** on position and **1 nm·s⁻¹** on velocity — the residual is interpolation round-off at
the sample epochs, so the bound is tight by design. Because `spiceypy` is the `[spk]` extra's own
implementation library, this oracle also exercises that install path.

## What validation does *not* cover

orbit-formats validates that it reads and writes an orbit **faithfully** — not that the orbit is
physically correct. Whether a trajectory is right is the producer's concern; orbit-formats'
guarantee is that a state read from one format and written to another preserves everything the
two formats can both express, and warns, naming the loss, wherever it cannot.
