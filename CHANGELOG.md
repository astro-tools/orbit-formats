# Changelog

All notable changes to orbit-formats are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/astro-tools/orbit-formats/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/astro-tools/orbit-formats/releases/tag/v0.1.0
