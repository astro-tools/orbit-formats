"""Shared low-level TLE line geometry: the fixed line length and the mod-10 checksum.

A TLE element line is a 68-character body plus a single mod-10 check digit. Three places need
that geometry — the format catalogue's content-signature detector
(:mod:`orbit_formats.formats`), the reader's structural validation
(:mod:`orbit_formats.readers.tle`), and the writer's line reconstruction
(:mod:`orbit_formats.writers.tle`). This module is the single definition they share. It depends
on nothing else in the package, so the catalogue (which must not import the readers) can use it
without a layering cycle, and the correctness-critical checksum cannot drift between a writer
that emits it and a reader that verifies it.
"""

from __future__ import annotations

__all__ = ["TLE_LINE_LEN", "checksum_digit", "checksum_ok"]

# A TLE element line is exactly 69 characters: a 68-character body plus the trailing check digit.
TLE_LINE_LEN = 69


def checksum_digit(body: str) -> int:
    """The TLE mod-10 checksum of a line body: each digit adds its value, ``-`` adds 1, else 0."""
    return sum(int(ch) if ch.isdigit() else 1 if ch == "-" else 0 for ch in body) % 10


def checksum_ok(line: str) -> bool:
    """Whether a full 69-character TLE line ends with the correct mod-10 check digit."""
    check = line[TLE_LINE_LEN - 1]
    if not check.isdigit():
        return False
    return checksum_digit(line[: TLE_LINE_LEN - 1]) == int(check)
