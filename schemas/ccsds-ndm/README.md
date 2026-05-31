# Vendored CCSDS NDM/XML schemas

These are the official CCSDS Navigation Data Messages XML (NDM/XML) W3C XML Schema
documents, vendored verbatim. They are the input to the binding generator: the
xsdata-generated Python bindings under `src/orbit_formats/_ccsds_xsd/` are produced from
them by `scripts/regen_ccsds_xsd.py`, and must never be hand-edited.

## Provenance

- **Source:** SANA registry, `ndmxml_unqualified` namespace —
  <https://sanaregistry.org/r/ndmxml_unqualified/>
  (files under `https://sanaregistry.org/files/ndmxml_unqualified/`).
- **Schema set:** NDM/XML version **4.0.0** (`urn:ccsds:schema:ndmxml`,
  `elementFormDefault="unqualified"`).
- **Specification:** CCSDS 505.0-B-3 *XML Specification for Navigation Data Messages*
  (Blue Book, 05/2023) and the message Blue Books it references (ODM 502.0-B-3, etc.).
- **Retrieved:** 2026-05-31.

The *unqualified* variant places every message in the single `urn:ccsds:schema:ndmxml`
namespace; it is the simpler set to bind and matches the `urn:ccsds:` content signature the
KVN detector already keys on.

## Files

| File | NDM member |
|------|------------|
| `ndmxml-4.0.0-master-4.0.xsd` | Master schema — includes every component below; the regeneration entry point |
| `ndmxml-4.0.0-namespace-4.0.xsd` | Namespace aggregator (includes all message + common schemas) |
| `ndmxml-4.0.0-common-4.0.xsd` | Shared types (units, state vectors, frames, time) |
| `ndmxml-4.0.0-ndm-4.0.xsd` | Combined NDM container |
| `ndmxml-4.0.0-oem-3.0.xsd` | Orbit Ephemeris Message |
| `ndmxml-4.0.0-omm-3.0.xsd` | Orbit Mean-Elements Message |
| `ndmxml-4.0.0-opm-3.0.xsd` | Orbit Parameter Message |
| `ndmxml-4.0.0-ocm-3.0.xsd` | Orbit Comprehensive Message |
| `ndmxml-4.0.0-aem-2.0.xsd` | Attitude Ephemeris Message |
| `ndmxml-4.0.0-apm-2.0.xsd` | Attitude Parameter Message |
| `ndmxml-4.0.0-acm-2.0.xsd` | Attitude Comprehensive Message |
| `ndmxml-4.0.0-cdm-1.0.xsd` | Conjunction Data Message |
| `ndmxml-4.0.0-rdm-1.0.xsd` | Reentry Data Message |
| `ndmxml-4.0.0-tdm-2.0.xsd` | Tracking Data Message |

## Regenerating the bindings

```bash
python scripts/regen_ccsds_xsd.py
```

The script pins the exact xsdata version, so the same schemas always reproduce the same
bindings.
