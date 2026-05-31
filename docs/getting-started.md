# Getting started

## Installation

orbit-formats is a pure-Python package; install it from PyPI:

```bash
pip install orbit-formats
```

SPICE SPK support pulls in a heavier binary-kernel dependency and is kept behind an
optional extra:

```bash
pip install orbit-formats[spk]
```

orbit-formats requires Python 3.10, 3.11, or 3.12.

## Reading a file

`read` resolves the format from the file's content and extension and returns the matching
canonical type — a `MeanElementSet` for a TLE, an `Ephemeris` for an OEM:

```python
from orbit_formats import read

elements = read("iss.tle")            # -> MeanElementSet
ephemeris = read("orbit.oem")         # -> Ephemeris (format auto-detected)
```

Pass `format=` to override detection — required for a format with no content signature, such
as a GMAT report:

```python
ephemeris = read("mission.report", format="gmat-report")
```

## The canonical DataFrame

Every state-series type projects to the canonical DataFrame consumers adopt — columns
`Epoch, X, Y, Z, VX, VY, VZ`, with the frame, time scale, central body, and units on
`DataFrame.attrs`:

```python
df = ephemeris.to_dataframe()
df.attrs["coordinate_system"]         # e.g. 'EME2000'
df.attrs["time_scale"]                # e.g. 'UTC'
```

See [Canonical representation](canonical-representation.md) for the full schema.

## Converting and writing

`convert` returns the source in the canonical form the target format expects; `write`
serialises it. The target format comes from `format=` or the destination extension:

```python
from orbit_formats import convert, read, write

eph = read("orbit.oem")
write(eph, "copy.oem")                # same-format write: lossless

# round-trip a file byte-for-byte by retaining the source
eph = read("orbit.oem", retain_source=True)
write(eph, "exact-copy.oem")          # byte-identical to orbit.oem
```

Pass `frame=` to rotate the Cartesian state into another reference frame on the way out — a
lossless rotation across TEME, EME2000 / J2000, GCRF, ICRF, and ITRF:

```python
write(convert("orbit.oem", to="ccsds-oem", frame="J2000"), "j2000.oem")
```

A conversion the library cannot do without modelling — a TLE's mean elements to an ephemeris,
which needs a propagation — raises `UnsupportedConversionError` rather than guessing. The
[conversion-capability matrix](conversion-matrix.md) lists what is supported.

## Catching lossy conversions

When a conversion cannot carry every field across, it warns rather than dropping data
silently. Catch the whole family with `LossyConversionWarning`:

```python
import warnings
from orbit_formats import read, LossyConversionWarning

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    state = read("positions_only.report", format="gmat-report")

for record in caught:
    if isinstance(record.message, LossyConversionWarning):
        print(record.message.fields)  # the fields that were lost
```

See [Lossy conversions](lossy-conversions.md) for the warning types.

## Development

To work on orbit-formats itself:

```bash
git clone https://github.com/astro-tools/orbit-formats.git
cd orbit-formats
uv sync --all-groups
```

Run the same checks CI runs:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

See
[CONTRIBUTING.md](https://github.com/astro-tools/orbit-formats/blob/main/CONTRIBUTING.md)
for the full branch / PR / test workflow.
