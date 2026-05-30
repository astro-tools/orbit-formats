"""Unit handling — ``astropy.units`` internally, plain numpy floats with unit metadata out.

The library uses ``astropy.units`` for unit safety inside the conversion layer. The
canonical schema exposes plain numpy floats with the units recorded in column metadata,
so a consumer never needs astropy to read a result.
"""
