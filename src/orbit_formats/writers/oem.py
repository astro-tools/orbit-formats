"""CCSDS OEM writer — a KVN OEM serialiser, generalised from gmat-run's OEM writer.

A same-format OEM read/write round-trip is lossless to tolerance, pinned by committed
goldens and cross-checked against the dev-only ccsds-ndm oracle in CI.
"""
