#!/usr/bin/env python3
"""Regenerate the CCSDS NDM/XML bindings under ``src/orbit_formats/_ccsds_xsd/``.

The bindings are produced by `xsdata <https://xsdata.readthedocs.io>`_ (MIT, the same
code generator the GPL ``ccsds-ndm`` library uses) from the schemas vendored under
``schemas/ccsds-ndm/``. Running this script reproduces the committed bindings exactly:
the xsdata version is pinned here, and the vendored schemas are byte-stable (``-text`` in
``.gitattributes``), so the same inputs always yield the same output.

The generator is fetched on the fly with ``uv run --with`` — mirroring how the oracle CI
job pulls ``ccsds-ndm`` — so nothing permanent is added to the dev environment and the
pin lives in exactly one place. The base ``xsdata`` runtime (which the binding parser/
serialiser in ``orbit_formats.adapters.ccsds_xml`` needs) is the project dependency; the
heavier ``[cli]`` codegen extra is only ever this script's transient concern.

Usage::

    python scripts/regen_ccsds_xsd.py

After running, review the diff and commit ``src/orbit_formats/_ccsds_xsd/__init__.py``.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

# The exact xsdata used to generate the committed bindings. Bump this in lockstep with the
# ``xsdata`` runtime floor in ``pyproject.toml`` and re-run, so the generated code and the
# runtime that parses it stay compatible.
XSDATA_VERSION = "26.2"

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_XSD = REPO_ROOT / "schemas" / "ccsds-ndm" / "ndmxml-4.0.0-master-4.0.xsd"
DEST = REPO_ROOT / "src" / "orbit_formats" / "_ccsds_xsd" / "__init__.py"

# Prepended verbatim to the generated module. Static (no timestamp) so regeneration stays
# byte-deterministic; it marks the file as generated and points back here.
BANNER = f"""\
# This file is generated from the vendored CCSDS NDM/XML schemas by
# scripts/regen_ccsds_xsd.py (xsdata {XSDATA_VERSION}). DO NOT EDIT BY HAND — re-run the
# script to regenerate. See schemas/ccsds-ndm/README.md for schema provenance.
"""


def _generate_into(workdir: Path) -> Path:
    """Run xsdata in ``workdir`` and return the path to the single generated module."""
    subprocess.run(
        [
            "uv",
            "run",
            "--with",
            f"xsdata[cli]=={XSDATA_VERSION}",
            "--",
            "xsdata",
            "generate",
            "--package",
            "ndm",
            "--structure-style",
            "single-package",
            str(MASTER_XSD),
        ],
        cwd=workdir,
        check=True,
    )
    # single-package mode emits one module plus an __init__ re-export; we keep the module
    # (the __init__ re-export hardcodes an import path we do not use) and relocate it.
    modules = [p for p in workdir.glob("*.py") if p.name != "__init__.py"]
    if len(modules) != 1:
        raise SystemExit(f"expected exactly one generated module in {workdir}, found {modules!r}")
    return modules[0]


def main() -> None:
    if not MASTER_XSD.is_file():
        raise SystemExit(f"vendored master schema not found: {MASTER_XSD}")
    with tempfile.TemporaryDirectory() as tmp:
        module = _generate_into(Path(tmp))
        body = module.read_text(encoding="utf-8")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(BANNER + body, encoding="utf-8", newline="\n")
    print(f"wrote {DEST.relative_to(REPO_ROOT)} ({body.count(chr(10)) + 1} lines)")


if __name__ == "__main__":
    sys.exit(main())
