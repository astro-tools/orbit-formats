# orbit-formats

[![CI](https://github.com/astro-tools/orbit-formats/actions/workflows/ci.yml/badge.svg)](https://github.com/astro-tools/orbit-formats/actions/workflows/ci.yml)
[![Docs](https://github.com/astro-tools/orbit-formats/actions/workflows/docs.yml/badge.svg)](https://astro-tools.github.io/orbit-formats/)
[![PyPI](https://img.shields.io/pypi/v/orbit-formats.svg)](https://pypi.org/project/orbit-formats/)
[![Python versions](https://img.shields.io/pypi/pyversions/orbit-formats.svg)](https://pypi.org/project/orbit-formats/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Lossless round-trip across orbital state-vector and ephemeris formats.

> **Status:** orbit-formats reads and writes the full CCSDS NDM family (OEM, OMM, OPM, OCM, AEM,
> APM, CDM, TDM, and the combined NDM, in KVN and XML), TLE (two-line / 3LE / catalogue / alpha-5),
> the Celestrak / Space-Track flat OMM (JSON and CSV), STK ephemeris, STK attitude, SP3, and SPICE
> SPK (behind the `[spk]` extra); additionally reads GMAT report and RINEX navigation; rotates
> Cartesian states across TEME / EME2000 / GCRF / ICRF / ITRF and projects Earth-fixed positions to
> geodetic longitude / latitude / height; surfaces OPM / OCM maneuvers on the canonical object and
> projects every time-series category — ephemeris, state, mean-element set, and attitude — to a
> DataFrame; and round-trips its writable formats losslessly, cross-validated against Orekit and
> SPICE. Next: the v1.0 API / representation freeze and a published deprecation policy.
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

## Quick start

```python
from orbit_formats import read, write

# read auto-detects the format; an OEM becomes a canonical Ephemeris
eph = read("orbit.oem")

# the canonical DataFrame downstream consumers adopt: Epoch, X, Y, Z, VX, VY, VZ
df = eph.to_dataframe()
df.attrs["coordinate_system"], df.attrs["time_scale"]

# round-trip a file byte-for-byte by retaining the source
write(read("orbit.oem", retain_source=True), "copy.oem")
```

A conversion that cannot carry every field across warns (naming what was lost) rather than
dropping data silently; one that cannot be done without modelling — a TLE's mean elements to
an ephemeris — is refused, not faked. See the
[lossy-conversion contract](https://astro-tools.github.io/orbit-formats/lossy-conversions/)
and the
[conversion-capability matrix](https://astro-tools.github.io/orbit-formats/conversion-matrix/).

## Supported formats

| Format | Read | Write | Canonical form |
|--------|:----:|:-----:|----------------|
| TLE / 3LE | ✅ | ✅ | mean-element set |
| CCSDS OEM (KVN + XML) | ✅ | ✅ | ephemeris |
| CCSDS OMM (KVN + XML) | ✅ | ✅ | mean-element set |
| OMM JSON / CSV (Celestrak / Space-Track) | ✅ | ✅ | mean-element set |
| CCSDS OPM (KVN + XML) | ✅ | ✅ | state vector |
| CCSDS OCM (KVN + XML) | ✅ | ✅ | ephemeris |
| CCSDS AEM (KVN + XML) | ✅ | ✅ | attitude |
| CCSDS APM (KVN + XML) | ✅ | ✅ | attitude |
| CCSDS CDM (KVN + XML) | ✅ | ✅ | conjunction |
| CCSDS TDM (KVN + XML) | ✅ | ✅ | tracking |
| CCSDS combined NDM (KVN + XML) | ✅ | ✅ | aggregate of NDM messages |
| GMAT report | ✅ | — | ephemeris / state |
| STK ephemeris | ✅ | ✅ | ephemeris |
| STK attitude | ✅ | ✅ | attitude |
| SP3 (SP3-c / SP3-d) | ✅ | ✅ | ephemeris |
| RINEX navigation (3.x) | ✅ | — | mean-element set / state |
| SPK (`[spk]` extra) | ✅ | ✅ | ephemeris |

The [canonical representation](https://astro-tools.github.io/orbit-formats/canonical-representation/)
— a small typed dataclass family unified by a metadata spine — is the format-agnostic form
everything reads into and writes from. Every time-series category — `Ephemeris`, `StateVector`,
`MeanElementSet`, and `Attitude` — projects to a pandas DataFrame.

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
