"""The format-fidelity layer — one faithful model per format, every field it defines.

Same-format round-trips (OEM to OEM) stay at this layer and are byte-lossless: a
fidelity model never down-projects. An adapter maps a fidelity model to and from the
canonical metamodel; a canonical object holds an optional ``source_native`` handle back
to the fidelity model it came from.
"""
