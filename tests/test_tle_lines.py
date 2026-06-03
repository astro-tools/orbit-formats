"""Unit tests for the shared low-level TLE line helpers."""

from __future__ import annotations

from orbit_formats._tle_lines import TLE_LINE_LEN, checksum_digit, checksum_ok

# A real ISS element set (the digit after the 68-character body is the published checksum).
_LINE1 = "1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927"
_LINE2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"


def test_line_length_is_69() -> None:
    assert TLE_LINE_LEN == 69
    assert len(_LINE1) == TLE_LINE_LEN
    assert len(_LINE2) == TLE_LINE_LEN


def test_checksum_digit_matches_the_published_check_digit() -> None:
    # checksum_ok verifies; checksum_digit must reproduce the same trailing digit it checks.
    for line in (_LINE1, _LINE2):
        assert checksum_digit(line[:-1]) == int(line[-1])


def test_checksum_digit_counts_a_minus_as_one() -> None:
    # Two minus signs and no digits: 1 + 1 = 2.
    assert checksum_digit("--") == 2
    # Digits add their value, other characters add nothing.
    assert checksum_digit("12A-") == 1 + 2 + 0 + 1


def test_checksum_ok_accepts_a_valid_line_and_rejects_a_corrupted_one() -> None:
    assert checksum_ok(_LINE1) is True
    corrupted = _LINE1[:-1] + str((int(_LINE1[-1]) + 1) % 10)
    assert checksum_ok(corrupted) is False


def test_checksum_ok_rejects_a_non_digit_check_character() -> None:
    assert checksum_ok("1" + " " * 67 + "X") is False
