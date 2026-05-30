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

## Status

orbit-formats is in early development. The package skeleton and tooling are in place;
format readers, writers, and the conversion layer land incrementally. See the
[changelog](https://github.com/astro-tools/orbit-formats/blob/main/CHANGELOG.md) for
released functionality.

## Installation

```bash
pip install orbit-formats
```

See [Getting started](getting-started.md).
