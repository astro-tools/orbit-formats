"""The canonical metamodel — the typed dataclass family consumers speak.

A shared metadata spine (``metadata``) tags every object with frame, time scale,
central body, object identity, units, and provenance. Category types build on it:
``StateVector`` (single state), ``Ephemeris`` (state time series), and
``MeanElementSet`` (TLE/SGP4, CCSDS OMM). Each canonical object keeps an optional
handle to its format-fidelity model (``fidelity``) so a same-format write recovers
full fidelity without polluting the canonical schema.
"""
