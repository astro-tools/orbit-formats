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
