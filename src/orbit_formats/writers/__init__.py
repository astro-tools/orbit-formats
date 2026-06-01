"""Format writers — each serialises a format-fidelity model back to its file format.

A writer consumes a per-format fidelity model (produced directly, or adapted from a
canonical object) and serialises it. One module per writable format.

Importing this package imports each writer module so that registering a writer against the
public surface is a one-time import side effect (see :mod:`orbit_formats.registry`).
"""

from orbit_formats.writers import (  # noqa: F401
    aem,
    apm,
    cdm,
    ndm,
    ocm,
    oem,
    omm,
    opm,
    stk_ephemeris,
    tdm,
    tle,
)
