# orbit-formats

[![CI](https://github.com/astro-tools/orbit-formats/actions/workflows/ci.yml/badge.svg)](https://github.com/astro-tools/orbit-formats/actions/workflows/ci.yml)
[![Docs](https://github.com/astro-tools/orbit-formats/actions/workflows/docs.yml/badge.svg)](https://astro-tools.github.io/orbit-formats/)
[![PyPI](https://img.shields.io/pypi/v/orbit-formats.svg)](https://pypi.org/project/orbit-formats/)
[![Python versions](https://img.shields.io/pypi/pyversions/orbit-formats.svg)](https://pypi.org/project/orbit-formats/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Lossless round-trip across orbital state-vector and ephemeris formats.

> **Status:** orbit-formats is in early development. The package skeleton and tooling
> are in place; format readers, writers, and the conversion layer land incrementally.
> See the [changelog](CHANGELOG.md) for released functionality.

## What this is

orbit-formats reads any supported orbital state or ephemeris format into a single
canonical in-memory representation, writes it back to any supported target, and
round-trips losslessly when the two formats can express the same information. When a
conversion cannot preserve information — covariance a target cannot hold, the
mean-element semantics of a TLE, a value truncated to a format's field width — it emits
an explicit, structured warning naming what was lost, never a silent drop.

It consolidates the format-I/O layer that astro-tools projects keep re-implementing into
one permissively-licensed (MIT) library that anything in the org — or outside it — can
depend on as the single source of format truth.

## What this is not

- **Not** a propagator, integrator, or analysis toolkit — it does only the conversion
  the formats themselves require.
- **Not** a general frame-transformation engine — it performs the time-scale and frame
  transforms cross-format conversion needs and defers arbitrary transforms to
  [astropy](https://www.astropy.org/) or SPICE.
- **Not** a way to turn a TLE's mean elements into an osculating state — that is a
  propagation, not a format conversion.

## Installation

```bash
pip install orbit-formats
```

SPICE SPK support is kept behind an optional extra (heavier binary-kernel dependency):

```bash
pip install orbit-formats[spk]
```

orbit-formats requires Python 3.10, 3.11, or 3.12.

## Documentation

Full docs at **<https://astro-tools.github.io/orbit-formats/>**.

## Development

```bash
git clone https://github.com/astro-tools/orbit-formats.git
cd orbit-formats
uv sync --all-groups
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full branch / PR / test workflow.

## Licence

MIT. See [LICENSE](LICENSE).
