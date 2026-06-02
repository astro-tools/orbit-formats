# Changelog

All notable changes to orbit-formats are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-02

This release completes the CCSDS NDM family and broadens the canonical model beyond orbits:
orbit-formats now reads and writes the attitude (AEM, APM), conjunction (CDM), tracking (TDM),
and comprehensive-orbit (OCM) messages in both KVN and XML, composes them through the aggregate
NDM container, reads and writes SPICE SPK kernels behind an optional `[spk]` extra, reads RINEX
navigation, and ships a complete, code-derived conversion-capability matrix — every conversion now
cross-validated against independent references (Orekit and SPICE), under the same
lossless-or-explicitly-warned contract.

### Added

- CCSDS **AEM** and **APM** attitude messages (KVN + XML), promoting the canonical `Attitude`
  category to a populated node — quaternion, Euler-angle, and spin representations with the frames
  an attitude is expressed between.
- CCSDS **CDM** conjunction message (KVN + XML) and the canonical `Conjunction` category — TCA,
  miss distance, relative position/velocity, per-object metadata and state, and the RTN covariances.
- CCSDS **TDM** tracking message (KVN + XML) and the canonical `Tracking` category — range, Doppler,
  and angle observations with their participants, paths, and data segments.
- CCSDS **OCM** comprehensive-orbit message (KVN + XML): orbit-relevant blocks (trajectory,
  covariance, manoeuvres) adapt to the canonical `Ephemeris` / `StateVector`, while blocks the
  canonical form cannot represent (physical properties, perturbations, orbit determination,
  user-defined) survive a same-format round-trip on `source_native` and are warned when a
  cross-format conversion drops them.
- **Aggregate / combined NDM** container (KVN + XML): reads a multi-message NDM into an ordered
  collection of canonical objects and writes a collection back, preserving the wrapper header.
- **SPK** (SPICE binary kernel) read and write behind the optional **`[spk]`** extra (`spiceypy`),
  detected by binary magic; the kernel path stays out of the base install and raises a typed,
  actionable error when the extra is missing.
- **RINEX navigation** reader (read-only): broadcast ephemerides adapt to the canonical form with
  the correct frame and GNSS time-system tags.
- The complete **conversion-capability matrix**: every physically-meaningful cross-form and
  cross-frame edge among the supported formats is implemented, classified (lossless /
  lossy-with-warning / unsupported, with the reason), and derived from the registered edges so the
  published matrix cannot drift from the code.

### Changed

- Conversions are now cross-validated in CI against external references — Orekit (state, element,
  frame, and time-scale conversions) and SPICE (the SPK round-trip) — both dev/CI-only and absent
  from the runtime dependency set.

## [0.2.0] - 2026-05-31

This release widens the writable format surface and the CCSDS notation coverage:
orbit-formats now reads and writes the full CCSDS NDM trio (OEM, OMM, OPM) in both KVN and
XML, writes TLE and STK ephemeris, reads SP3 precise GNSS ephemerides, and rotates Cartesian
states between real reference frames — extending the same lossless-or-explicitly-warned
contract to every new path.

### Added

- CCSDS XML notation across the NDM family: an `xsdata`-generated, MIT-licensed binding layer
  (regenerated from the vendored CCSDS XSDs by `scripts/regen_ccsds_xsd.py`) drives reading and
  writing OEM, OMM, and OPM in XML alongside the existing KVN notation, selected automatically
  from the file or by an explicit `format=`.
- CCSDS OMM reader and writer (KVN + XML), canonicalised as a mean-element set, with
  bidirectional TLE ↔ OMM conversion — both share the mean-element form, so the conversion is a
  same-form re-emission rather than a model change.
- CCSDS OPM reader and writer (KVN + XML), canonicalised as a state vector, preserving
  covariance and manoeuvres on the fidelity model.
- TLE / 3LE writer: TLE becomes a writable format, emitting checksum-correct, column-exact
  lines that round-trip a parsed TLE.
- STK ephemeris (`.e`) reader and writer (ephemeris form).
- SP3 reader (SP3-c / SP3-d precise GNSS ephemeris, read-only).
- Real frame rotation for Cartesian states across TEME / EME2000 / GCRF / ICRF / ITRF (via
  astropy): a cross-frame conversion now rotates the state rather than being refused, while
  conversions that still cannot preserve information continue to warn explicitly.

### Changed

- The CCSDS OEM writer is generalised to emit both KVN and XML from the same canonical
  ephemeris.
- `xsdata` (MIT) is now a base runtime dependency — the CCSDS XML binding runtime — keeping the
  base install permissively licensed; the heavier codegen extra stays dev-only.

### Fixed

- The GMAT report format is correctly marked read-only in the format catalog, so the
  conversion-capability matrix and `detect_format` no longer imply a GMAT report writer.

## [0.1.0] - 2026-05-30

First release. orbit-formats reads TLE, CCSDS OEM (KVN), and GMAT report files into a
single canonical representation, writes CCSDS OEM, and round-trips OEM losslessly —
emitting an explicit, structured warning whenever a conversion cannot preserve
information, never a silent drop.

### Added

- Canonical representation: a federated, typed dataclass family — `StateVector`,
  `Ephemeris`, and `MeanElementSet` — unified by a shared `Metadata` spine (reference
  frame, time scale, central body, object id, units, provenance). State-series types
  project to a gmat-run-identical DataFrame (`Epoch, X, Y, Z, VX, VY, VZ`, with the spine
  on `DataFrame.attrs`) that downstream consumers can adopt without reshaping.
- Two-layer model: a faithful per-format fidelity layer beneath the canonical metamodel,
  linked by an optional `source_native` handle, so a same-format round-trip stays
  byte-identical (with `retain_source=True`) or content-lossless.
- Readers: TLE / 3LE (sgp4-backed mean elements, TEME / UTC), CCSDS OEM (in-house KVN
  parser — multi-segment, with covariance and acceleration preserved on the fidelity
  model), and GMAT report (whitespace-aligned tables into an ephemeris or state).
- Writer: CCSDS OEM (KVN), with byte-identical, content-lossless, and synthesised paths.
- Public API — `read`, `write`, `convert`, and `detect_format` — with
  content-signature-first format auto-detection and an explicit `format=` override.
- Conversion graph: Cartesian ↔ Keplerian elements and time-scale conversion across UTC /
  TAI / TT / TDB / GPS / UT1; conversions route through each format's preferred canonical
  form.
- Lossy-conversion framework: structured, catchable warnings (`DroppedFieldWarning`,
  `PrecisionLossWarning`, `ModelApproximationWarning`, `MissingFieldWarning`) that name
  exactly what a conversion drops.
- Frame-rotation boundary: reference frames are tagged and preserved; a conversion that
  would require rotating between distinct frames is refused rather than approximated.
- `orbit-formats convert` command-line interface for one-shot file-to-file conversion.
- Documentation site — the canonical-representation reference, a per-format reference, the
  lossy-conversion semantics, and the conversion-capability matrix — and a typed
  (`py.typed`), MIT-licensed package published to PyPI.

[Unreleased]: https://github.com/astro-tools/orbit-formats/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/astro-tools/orbit-formats/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/astro-tools/orbit-formats/releases/tag/v0.1.0
