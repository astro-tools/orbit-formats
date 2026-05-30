"""The conversion layer — route a canonical object to the form a target format prefers.

Conversions route through the canonical metamodel rather than as N-by-N bespoke format
pairs: a small explicit graph (``graph``) chains element transforms (``elements``:
Cartesian and Keplerian, given a gravitational parameter) and time-scale transforms
(``time``: UTC / TAI / TT / TDB / GPS / UT1). Frame rotation between distinct frames is
not performed here; a conversion that would require one errors clearly rather than
guessing.
"""
