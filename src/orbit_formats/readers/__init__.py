"""Format readers — each parses one format into its format-fidelity model.

A reader's output is a faithful, per-format model (every field the format defines); an
adapter then maps it into the canonical metamodel. One module per format.
"""
