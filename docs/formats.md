# Formats

What each format expresses, what it cannot, and how it maps into the canonical
representation. Reading routes a format into its canonical category type; everything the
canonical form has no slot for is preserved on the [`source_native`](canonical-representation.md)
fidelity model rather than dropped.

## Support at a glance

| Format | Id | Read | Write | Canonical form |
|--------|----|:----:|:-----:|----------------|
| TLE / 3LE | `tle` | ✓ | ✓ | mean-element set |
| CCSDS OEM (KVN + XML) | `ccsds-oem` | ✓ | ✓ | ephemeris |
| CCSDS OMM (KVN + XML) | `ccsds-omm` | ✓ | ✓ | mean-element set |
| CCSDS OPM (KVN + XML) | `ccsds-opm` | ✓ | ✓ | state vector |
| GMAT report | `gmat-report` | ✓ | — | ephemeris / state |
| STK ephemeris | `stk-ephemeris` | ✓ | ✓ | ephemeris |
| SP3 (SP3-c / SP3-d) | `sp3` | ✓ | — | ephemeris |
| RINEX navigation (3.x) | `rinex-nav` | ✓ | — | mean-element set / state |
| CCSDS combined NDM (KVN + XML) | `ccsds-ndm` | ✓ | ✓ | aggregate of NDM messages |

TLE and OMM share the **mean-element set** canonical form, so they convert into each other:
read a TLE and write an OMM, or read an OMM and write a TLE. A RINEX-navigation mean set is
*also* in the mean-element form, but it carries GNSS **broadcast** elements rather than SGP4
elements, so it does **not** convert to a TLE or OMM — see [RINEX navigation](#rinex-navigation-3x-rinex-nav)
below.

**CCSDS notation — KVN and XML.** The OEM, OMM, and OPM each read and write in both CCSDS
notations under a single format id. The two notations are held at **parity**: KVN and XML parse
into the same fidelity model, so a message carries identical content whichever it arrived in,
and a KVN → XML → KVN round trip reproduces it. On write, the destination extension selects the
notation (`.oem` / `.omm` / `.opm` → KVN, `.xml` → XML); since `.xml` names no single NDM
message, writing one needs an explicit `format=` (e.g. `write(eph, "sat.xml",
format="ccsds-oem")`).

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
- **Writing:** a TLE read back out is echoed verbatim. A `MeanElementSet` from another source
  (an OMM, say) is reconstructed into two element lines with fresh checksums — *element-level*
  lossless (a re-read reproduces the same elements to the TLE's representable precision),
  warning for each TLE identifier the source could not supply.
- **Detection:** the `1 ` / `2 ` line structure with valid mod-10 checksums and agreeing
  satellite numbers, or the `.tle` / `.3le` extension. A bad checksum or disagreeing
  satellite numbers raise `MalformedSourceError`.

## CCSDS OEM (KVN + XML) — `ccsds-oem`

An Orbit Ephemeris Message reads into an `Ephemeris`. Both notations of the message — KVN
(key-value notation) and XML — are read and written; they share one `ccsds-oem` id and one
fidelity model, so an OEM is the same canonical object whichever notation it arrived in.

- **Expresses:** a Cartesian state-vector time series, with the frame, central body, time
  system, object name, and object id from the segment META.
- **Multi-segment files** are concatenated into one canonical ephemeris. The segments must
  agree on reference frame, central body, and time system — the reader does not silently rotate
  or rescale one segment to match another, so a disagreement raises `MalformedSourceError`
  rather than producing a wrong series. (Rotating a whole ephemeris into another frame is a
  separate, explicit step — `convert(..., frame=...)`.) Per-segment META is preserved on
  `source_native`.
- **Preserved on `source_native`, not in the canonical form:** acceleration columns,
  covariance blocks, comments, non-standard META keywords, and the full per-segment header.
  An OEM whose `TIME_SYSTEM` is one the canonical spine does not carry (e.g. `TCB`) leaves
  `metadata.time_scale` unset but keeps the raw value on the fidelity model.
- **Writing** picks one of three paths automatically: a byte-identical re-emit (when the
  read opted into `retain_source=True`), a content-lossless re-serialisation of the fidelity
  model, or — for a synthesised or cross-format ephemeris with no OEM `source_native` — a
  fresh OEM built from the canonical fields, warning for each OEM-required field the
  canonical form cannot supply. See [Lossy conversions](lossy-conversions.md).
- **KVN vs XML on write:** the destination extension selects the notation — `.oem` writes
  KVN, `.xml` writes XML — otherwise the source's own notation is re-emitted. Since `.xml`
  names no single NDM message, writing one needs an explicit format, e.g.
  `write(eph, "sat.xml", format="ccsds-oem")`.
- **Detection:** the `CCSDS_OEM_VERS =` KVN header, or an `<oem>` XML root carrying the same
  marker (the `urn:ccsds:` namespace is not required), or the `.oem` extension.

## CCSDS OMM (KVN + XML) — `ccsds-omm`

An Orbit Mean-elements Message reads into a `MeanElementSet`. Both notations — KVN and XML —
are read and written under one `ccsds-omm` id and one fidelity model. An OMM is the CCSDS
sibling of a TLE: both carry SGP4 mean elements, so the two convert into each other losslessly
(`TLE → OMM` enriches the message with the TLE's identifiers; `OMM → TLE` reconstructs the
lines).

- **Expresses:** the six mean Keplerian elements plus the SGP4 mean motion, the mean-element
  theory, the frame / central body / time system, and the TLE bookkeeping (catalog number,
  classification, element-set and revolution numbers, `BSTAR` and the mean-motion derivatives).
- **Preserved on `source_native`, not in the canonical form:** the spacecraft-parameters and
  covariance blocks, user-defined parameters, comments, and the full header. A Keplerian OMM
  that states `SEMI_MAJOR_AXIS` rather than `MEAN_MOTION` has its mean motion derived from the
  semi-major axis and `GM`.
- **Writing** mirrors the OEM writer: byte-identical (with `retain_source=True`),
  content-lossless, or synthesised from the canonical fields with a warning for each
  OMM-required field the source cannot supply. The destination extension selects the notation
  (`.omm` → KVN, `.xml` → XML).
- **Detection:** the `CCSDS_OMM_VERS =` KVN header, or an `<omm>` XML root carrying the same
  marker, or the `.omm` extension.

## CCSDS OPM (KVN + XML) — `ccsds-opm`

An Orbit Parameter Message reads into a `StateVector`. Both notations — KVN and XML — are
read and written under one `ccsds-opm` id and one fidelity model. An OPM carries a single
Cartesian state at one epoch, optionally accompanied by an osculating Keplerian restatement,
spacecraft parameters, a covariance, and any number of planned maneuvers.

- **Expresses:** the Cartesian position and velocity at the state epoch, tagged with the
  frame, central body, time system, object name, and object id from the metadata.
- **Osculating Keplerian block:** when the OPM states one with a `TRUE_ANOMALY` it populates
  the canonical `keplerian` — a redundant restatement of the same Cartesian state. A block
  stated with `MEAN_ANOMALY` instead leaves the canonical view unset (the canonical form holds
  a true-anomaly representation), but the full block survives on `source_native`.
- **Preserved on `source_native`, not in the canonical form:** the covariance, the maneuver
  blocks (ignition epoch, duration, delta-mass, frame, and the three delta-v components), the
  spacecraft-parameters block, the full Keplerian block, user-defined parameters, comments, and
  the header. An OPM whose `TIME_SYSTEM` is one the canonical spine does not carry leaves
  `metadata.time_scale` unset with the raw value on the fidelity model.
- **Writing** mirrors the OEM and OMM writers: byte-identical (with `retain_source=True`),
  content-lossless, or synthesised from the canonical state with a warning for each
  OPM-required metadata field the source cannot supply. The destination extension selects the
  notation (`.opm` → KVN, `.xml` → XML).
- **Detection:** the `CCSDS_OPM_VERS =` KVN header, or an `<opm>` XML root carrying the same
  marker, or the `.opm` extension.

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

## STK ephemeris — `stk-ephemeris`

An AGI / STK text ephemeris (`.e`) reads into an `Ephemeris`; GMAT's STK-TimePosVel writer
emits the same format. A `stk.v.X.Y` banner and optional `# …` comments precede a
`BEGIN Ephemeris` block of whitespace-separated `KEY VALUE` metadata, then an
`EphemerisTimePosVel` (or `EphemerisTimePosVelAcc`) data section of records — an
offset-from-epoch in seconds plus the position / velocity (and optional acceleration)
triplet — closed by `END Ephemeris`.

- **Expresses:** a Cartesian state-vector time series, tagged with the frame
  (`CoordinateSystem`) and central body (`CentralBody`) from the meta block. Each record's
  offset is made absolute against `ScenarioEpoch`.
- **Time scale:** a `.e` declares none, so the canonical scale is tagged **UTC** — GMAT's
  default for the STK writer, and the only sensible default. The raw `ScenarioEpoch` text is
  kept on `source_native` so a consumer whose mission pinned another scale can re-interpret
  it. `ScenarioEpoch` is read either as a Gregorian `DD Mon YYYY HH:MM:SS.fff` value or as a
  numeric GMAT Modified Julian Date.
- **Preserved on `source_native`, not in the canonical form:** acceleration columns (from the
  `…Acc` data section — the canonical `Ephemeris` holds position and velocity only), the
  version banner, the header comments, and every meta keyword verbatim (including
  `NumberOfEphemerisPoints`, `DistanceUnit`, and any the canonical form does not interpret).
- **Writing** picks one of three paths automatically, mirroring the OEM writer: a
  byte-identical re-emit (with `retain_source=True`), a content-lossless re-serialisation of
  the fidelity model, or — for a synthesised or cross-format ephemeris with no STK
  `source_native` — a fresh `.e` built from the canonical fields, warning for each
  `.e`-required field (`CentralBody`, `CoordinateSystem`, `ScenarioEpoch`) the canonical form
  cannot supply. See [Lossy conversions](lossy-conversions.md).
- **Detection:** the `stk.v.X.Y` banner on the first non-comment line, or the `.e` / `.ephem`
  extension. Only the banner, `BEGIN Ephemeris`, `ScenarioEpoch`, and a recognised data
  section are mandatory; other data-section variants (e.g. `EphemerisTimePos`) raise
  `MalformedSourceError`.

## SP3 — `sp3`

An IGS precise GNSS ephemeris (`.sp3`, SP3-c / SP3-d) reads into an `Ephemeris`. SP3 is a
multi-satellite product: a header declares the version, a position-only (`P`) or
position-and-velocity (`V`) mode, the satellite list with a per-satellite accuracy code, and
the time system; the body is a sequence of epochs, each carrying one position record per
satellite (and, in `V` mode, a velocity record). SP3 is **read-only** — there is no SP3
writer, so a write to `.sp3` raises `UnsupportedFormatError`.

- **Expresses:** a Cartesian state-vector time series per satellite, tagged **ITRF** (SP3 is
  Earth-centred, Earth-fixed) with **Earth** as the central body and the SP3 time system as
  the time scale. Positions are in km; SP3 velocities (decimetres·s⁻¹) are converted to
  km·s⁻¹.
- **Multi-satellite → a per-satellite ephemeris set.** `read` returns the **first** listed
  satellite as the canonical `Ephemeris`, its id on `metadata.object_name`; the whole set is
  `result.source_native.ephemerides()` — a `dict` of satellite id → `Ephemeris`, each tagged
  identically. Every satellite's series rides on `source_native`, so no satellite is dropped.
- **Time scale:** the SP3 time system is tagged when the canonical spine carries it (`GPS` /
  `UTC` / `TAI` / `TT` / `UT1`); a GNSS system time it does not model (`GLO` / `GAL` / `QZS`
  / `BDT` / `IRN`) leaves `time_scale` unset, with the raw value kept on the fidelity model.
- **Position-only files** (`P`-mode) fill the canonical velocities with NaN — never a
  fabricated value — and a `MissingFieldWarning` names them.
- **Preserved on `source_native`, not in the canonical form:** the satellite clock offsets
  (and rates), the per-satellite accuracy codes, the specific frame realisation (`IGS20`,
  `IGb14`), the agency / orbit type / GPS week / interval, and the header comments.
- **Detection:** the `#` + version-letter (`#c` / `#d`) content signature on the first line,
  or the `.sp3` extension. The reader parses SP3-c and SP3-d; another version, a malformed
  header, a record with too few columns or a non-numeric value, or a satellite whose record
  count disagrees with the epoch count raise `MalformedSourceError`.

## RINEX navigation (3.x) — `rinex-nav`

A RINEX **navigation** file (the GNSS *broadcast ephemeris*) reads into the canonical form. It
is a fixed-layout text message: a header closed by `END OF HEADER`, then a sequence of
per-satellite records — an epoch line (satellite id, the time of clock `Toc`, and the SV-clock
polynomial terms) followed by the constellation's broadcast-orbit lines. RINEX navigation is
**read-only** — there is no writer, so a write to `.rnx` raises `UnsupportedFormatError`.

- **Two canonical categories, by constellation.** The Keplerian constellations — GPS, Galileo,
  BeiDou, QZSS, and NavIC — carry quasi-Keplerian parameters and read into a `MeanElementSet`:
  the headline mean elements, with the **mean motion derived** from `sqrt(A)` and `Delta n`
  through the constellation's gravitational parameter, converted to rev/day. The Cartesian
  constellations — GLONASS and SBAS — carry an Earth-fixed position / velocity / acceleration
  and read into a `StateVector` (position and velocity; the acceleration rides on
  `source_native`).
- **Frame and time.** Tagged **ITRF** (RINEX navigation is Earth-centred, Earth-fixed; the
  specific datum — WGS-84, PZ-90, GTRF, CGCS2000 — follows from the satellite id and stays on
  the fidelity model) with **Earth** as the central body. The time scale is the constellation's
  epoch time system when the canonical spine carries it — GPS → `GPS`, GLONASS → `UTC`; Galileo
  / BeiDou / QZSS / NavIC system time the spine does not model leaves `time_scale` unset, the
  same conservative rule SP3 follows.
- **Broadcast, not SGP4.** A RINEX mean set is tagged with the **broadcast** mean-element
  theory. Broadcast elements are referenced to the time of ephemeris in an Earth-fixed datum
  and evaluated by the constellation's user algorithm — they are *not* SGP4 / TEME elements.
  Converting one to a TLE or OMM is therefore refused with `IncompatibleMeanElementTheoryError`
  (a subclass of `UnsupportedConversionError`): a faithful conversion would need to propagate
  the broadcast model and refit SGP4 elements — a propagation plus an orbit fit, out of scope —
  not relabel the numbers. See [Conversion matrix](conversion-matrix.md).
- **Multi-record → a record set.** `read` returns the **first** record as its canonical object;
  the whole file is `result.source_native`, and `result.source_native.to_canonical()` returns
  every record's canonical object in file order. No record is dropped.
- **Preserved on `source_native`, not in the canonical form:** the SV-clock polynomial, the
  harmonic corrections (`Cuc` … `Cis`), `Toe` and the broadcast week, the satellite health,
  the group delays, and every other broadcast-orbit field — kept verbatim on each record, with
  named access via `record.field(...)` for the orbit-determining fields.
- **Detection:** the `RINEX VERSION / TYPE` header label, or the `.rnx` / `.nav` /
  `.NNn` (version-2 year-and-system) extension. The reader parses RINEX **3.x**; RINEX 2.x or
  4.x, a missing or malformed header, an unknown constellation, a truncated record, or a
  non-numeric field raise `MalformedSourceError`.

## CCSDS combined NDM (KVN + XML) — `ccsds-ndm`

A combined (aggregate) NDM holds several individual NDM messages — an OPM and a CDM, several
OEMs, any mix — in one file. `read` returns a **`Combined`**: an ordered tuple of the member
canonical objects on `Combined.messages`, plus the wrapper's `message_id` and `comments`. Each
member is exactly the object reading that message on its own would yield — its full identity and
`source_native` intact — so the members of `read("bundle.ndm")` are an `Ephemeris`, a
`Conjunction`, a `StateVector`, and so on, ready to use individually.

- **Two notations.** XML is the standardised `<ndm>` wrapper. KVN has no standardised wrapper,
  so the aggregate is the member KVN messages **concatenated**, each keeping its
  `CCSDS_<TYPE>_VERS =` header. On write the destination extension selects the notation (`.ndm`
  / `.kvn` → KVN, `.xml` → XML); since `.xml` names no single message, writing one needs an
  explicit `format="ccsds-ndm"`.
- **Members group by type.** The XML `<ndm>` stores its children in one list per message type,
  so both notations emit the members grouped by type (and in their original order within a
  type). The two are held at **parity**: a combined NDM read from either carries the same
  members, and a KVN → XML → KVN round trip reproduces it.
- **The member format follows `source_native`.** Each member is written back as the NDM message
  it was read as — an `Ephemeris` whose native is a `ccsds-oem` writes as an `<oem>` — so the
  members of a `Combined` you assemble yourself are objects read from (or otherwise tagged with)
  an NDM message.
- **The wrapper `MESSAGE_ID`.** XML carries it; KVN has nowhere to put it, so a KVN write
  reports it as a loss through the [lossy-conversion](lossy-conversions.md) framework. The
  wrapper comments carry in both notations.
- **Detection:** the `<ndm>` root element (XML), or two or more `CCSDS_<TYPE>_VERS =` headers in
  one file (KVN) — either outranks the individual members, so a concatenation of an OEM and an
  OMM reads as one combined NDM. A member type this version has no reader for (an `acm` or `rdm`
  child) raises `UnsupportedFormatError` rather than being dropped; a single-member KVN "bundle"
  raises `MalformedSourceError`.
- **Not a conversion target.** An aggregate carries no single canonical form — it composes
  messages rather than mapping between forms — so `convert` to or from `ccsds-ndm` raises
  `UnsupportedConversionError`.
