"""Structured lossy-conversion warnings.

A conversion that cannot preserve information — covariance a target format cannot hold,
the mean-element semantics of a TLE, a value truncated to a format's field width —
emits a structured, catchable warning naming exactly what was lost, rather than
dropping data silently.
"""
