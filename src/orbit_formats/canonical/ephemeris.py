"""``Ephemeris`` — a state-vector time series with a ``to_dataframe()`` projection.

The DataFrame projection matches gmat-run's schema verbatim — columns ``X, Y, Z, VX,
VY, VZ`` with ``coordinate_system`` / ``central_body`` / ``time_scale`` / ``object_name``
on ``DataFrame.attrs``, extended with ``units`` and ``interpolation`` — so downstream
consumers need zero reshaping.
"""
