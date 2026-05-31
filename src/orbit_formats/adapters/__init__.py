"""Adapters — map each format-fidelity model to and from the canonical metamodel.

Reading routes format to fidelity model to canonical; writing routes canonical to
fidelity model to format. Keeping the adapter step explicit is what lets same-format
round-trips stay byte-lossless while cross-format conversion goes through the canonical
metamodel and warns on every field a target cannot hold.

The CCSDS NDM/XML plumbing — turning XML bytes into the generated xsdata bindings and back
— lives in :mod:`orbit_formats.adapters.ccsds_xml`. It is imported on demand (not from
here), so the xsdata runtime is only pulled in when an XML path is actually exercised.
"""

from orbit_formats.adapters.base import Adapter

__all__ = ["Adapter"]
