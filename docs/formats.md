# Formats

What each v0.1 format expresses, what it cannot, and how it maps into the canonical
representation. Reading routes a format into its canonical category type; everything the
canonical form has no slot for is preserved on the [`source_native`](canonical-representation.md)
fidelity model rather than dropped.

## Support at a glance

| Format | Id | Read | Write | Canonical form |
|--------|----|:----:|:-----:|----------------|
| TLE / 3LE | `tle` | ✓ | — | mean-element set |
| CCSDS OEM (KVN) | `ccsds-oem` | ✓ | ✓ | ephemeris |
| GMAT report | `gmat-report` | ✓ | — | ephemeris / state |

Other formats — SP3, STK ephemeris, the rest of the CCSDS NDM family (OMM / OPM / AEM /
CDM), SPICE SPK, RINEX navigation — are recognised by detection but not yet read or written;
a `read` of one raises `UnsupportedFormatError`. They land in later versions.

## TLE / 3LE — `tle`

A two-line (optionally name-prefixed three-line) element set reads into a `MeanElementSet`.
The elements are derived from the lines with `sgp4` and stay **mean** elements in the
**TEME** frame on the **UTC** scale, geocentric; the NORAD id is tagged on
`metadata.object_id`.

- **Expresses:** mean motion (rev/day), eccentricity, inclination, RAAN, argument of
  periapsis, mean anomaly, and the SGP4 drag terms (`bstar`, mean-motion derivatives).
- **Does not express:** an osculating state. Turning a TLE into a state at any time other
  than the element-set epoch is a *propagation*, not a format conversion — out of scope.
  The single SGP4 state at the epoch is available via the fidelity model
  (`result.source_native.epoch_state()`).
- **Fidelity:** the raw 69-character lines are kept verbatim on `source_native`.
- **Detection:** the `1 ` / `2 ` line structure with valid mod-10 checksums and agreeing
  satellite numbers, or the `.tle` / `.3le` extension. A bad checksum or disagreeing
  satellite numbers raise `MalformedSourceError`.

## CCSDS OEM (KVN) — `ccsds-oem`

An Orbit Ephemeris Message in key-value notation reads into an `Ephemeris`. v0.1 covers the
KVN form; the XML form lands later.

- **Expresses:** a Cartesian state-vector time series, with the frame, central body, time
  system, object name, and object id from the segment META.
- **Multi-segment files** are concatenated into one canonical ephemeris. The segments must
  agree on reference frame, central body, and time system — concatenating states tagged
  differently would need a transform v0.1 does not perform, so a disagreement raises
  `MalformedSourceError` rather than producing a wrong series. Per-segment META is preserved
  on `source_native`.
- **Preserved on `source_native`, not in the canonical form:** acceleration columns,
  covariance blocks, comments, non-standard META keywords, and the full per-segment header.
  An OEM whose `TIME_SYSTEM` is one the canonical spine does not carry (e.g. `TCB`) leaves
  `metadata.time_scale` unset but keeps the raw value on the fidelity model.
- **Writing** picks one of three paths automatically: a byte-identical re-emit (when the
  read opted into `retain_source=True`), a content-lossless re-serialisation of the fidelity
  model, or — for a synthesised or cross-format ephemeris with no OEM `source_native` — a
  fresh OEM built from the canonical fields, warning for each OEM-required field the
  canonical form cannot supply. See [Lossy conversions](lossy-conversions.md).
- **Detection:** the `CCSDS_OEM_VERS =` header, or the `.oem` extension.

## GMAT report — `gmat-report`

A GMAT `ReportFile` table reads into an `Ephemeris` (multiple rows) or a `StateVector` (a
single row). Columns are whitespace-aligned; a run of two-or-more spaces separates them, so a
single space inside a value (a Gregorian epoch) never splits a column. Headers re-emitted at
mission-sequence boundaries are skipped.

- **Expresses:** the first Cartesian state group it finds (`<resource>.<frame>.<component>`),
  tagged with the frame from the coordinate-system segment and the time scale from the epoch
  column's suffix.
- **Tagged only where the column names declare it.** A component named without a coordinate
  system (GMAT's undeclared default frame) leaves `reference_frame` unset; GMAT's `A1` scale,
  which the canonical spine does not carry, leaves `time_scale` unset with the raw column name
  on the fidelity model. A report does not declare a central body, so `central_body` stays
  unset — never inferred.
- **Missing components** (a position-only report — common from GMAT) are filled with NaN, not
  a fabricated value, and a `MissingFieldWarning` names exactly which components were absent.
- **Preserved on `source_native`:** every column the canonical form cannot place — a second
  spacecraft's state, Keplerian elements, mass, and any other parameter.
- **Detection:** the GMAT report has *no* content signature. It is recognised by the
  `.report` extension or named with an explicit `format="gmat-report"`.
