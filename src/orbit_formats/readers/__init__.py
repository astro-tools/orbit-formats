"""Format readers — each parses one format into its format-fidelity model.

A reader's output is a faithful, per-format model (every field the format defines); an
adapter then maps it into the canonical metamodel. One module per format.

Importing this package imports each reader module so that registering a reader against the
public surface is a one-time import side effect (see :mod:`orbit_formats.registry`).
"""

from orbit_formats.readers import (  # noqa: F401
    ccsds,
    ccsds_aem,
    ccsds_apm,
    ccsds_cdm,
    ccsds_omm,
    ccsds_opm,
    ccsds_tdm,
    gmat_report,
    sp3,
    stk_ephemeris,
    tle,
)
