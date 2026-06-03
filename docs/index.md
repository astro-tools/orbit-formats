# orbit-formats

Lossless round-trip across orbital state-vector and ephemeris formats.

orbit-formats reads any supported orbital state or ephemeris format into a single
canonical in-memory representation, writes it back to any supported target, and
round-trips losslessly when the two formats can express the same information. When a
conversion cannot preserve information, it emits an explicit, structured warning naming
exactly what was lost — never a silent drop.

## Why

Orbital state vectors live in a dozen formats — TLE, the CCSDS Navigation Data Message
family, SP3, RINEX navigation, SPICE SPK, STK ephemeris, GMAT report — and every project
re-implements the subset it needs, rarely testing round-trip fidelity. orbit-formats
consolidates that I/O layer into one permissively-licensed (MIT) library with a tested,
round-trip-faithful core that anything in the astro-tools org — or outside it — can
depend on as the single source of format truth.

## What it is not

- Not a propagator, integrator, or analysis toolkit — it does only the conversion the
  formats themselves require.
- Not a general frame-transformation engine — it performs the time-scale and frame
  transforms cross-format conversion needs, at the precision the formats demand, and
  defers arbitrary transforms to [astropy](https://www.astropy.org/) or SPICE.
- Not a route from a TLE's mean elements to an osculating state — that is a propagation,
  not a format conversion.

## What it reads and writes

orbit-formats reads TLE / 3LE (with the catalogue and alpha-5 variants); the full CCSDS NDM
family — OEM, OMM, OPM, OCM, AEM, APM, CDM, TDM, and the combined NDM, each in KVN and XML; the
Celestrak / Space-Track flat OMM (JSON and CSV); STK ephemeris; STK attitude; SP3; GMAT report;
SPICE SPK (behind the `[spk]` extra); and RINEX navigation. It writes every one of those except
the read-only GMAT report and RINEX navigation; converts between formats that share a canonical
form — including the lossless TLE ↔ OMM pairing; rotates Cartesian states across
TEME / EME2000 / GCRF / ICRF / ITRF on request; and projects an Earth-fixed position to geodetic
longitude / latitude / height. See [Formats](formats.md) for what each can and
cannot express, and the [conversion-capability matrix](conversion-matrix.md) for what converts
to what.

## Installation

```bash
pip install orbit-formats
```

## Explore

- **[Getting started](getting-started.md)** — read a file, project to a DataFrame, convert
  and write, catch a lossy warning.
- **[Canonical representation](canonical-representation.md)** — the two-layer model and the
  DataFrame schema downstream consumers adopt.
- **[Formats](formats.md)** — the per-format reference.
- **[Lossy conversions](lossy-conversions.md)** — the lossless-round-trip and
  lossy-warning contract, and the frame / time-transform scope.
- **[Conversion-capability matrix](conversion-matrix.md)** — what converts to what, and at
  what cost.
- **[Validation](validation.md)** — the external oracles (Orekit, SPICE, the CCSDS references)
  and what they guarantee.
- **[Command-line interface](cli.md)** and **[API reference](api.md)**.

See the
[changelog](https://github.com/astro-tools/orbit-formats/blob/main/CHANGELOG.md) for
released functionality.
