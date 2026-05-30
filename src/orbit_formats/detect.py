"""Format auto-detection — pick a reader from a file's content signature or extension.

Detection is content-signature-first: a strong header or magic number identifies the
format, the file extension breaks ties, and an explicit ``format=`` override always
wins. Ambiguity resolves through a deterministic, ordered detector list, falling back
to a clear error that names the candidate formats.
"""
