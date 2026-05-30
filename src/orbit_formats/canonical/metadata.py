"""The shared metadata spine — frame, time scale, central body, object id, units, provenance.

Every canonical object carries this typed, validated metadata on the object itself,
never parked in a pandas ``attrs`` dict (pandas drops ``attrs`` on most operations,
which a lossless-round-trip library cannot depend on). ``to_dataframe()`` materialises
the metadata into ``DataFrame.attrs`` only at the edge.
"""
