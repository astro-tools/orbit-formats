"""Edge cases of the format catalog and its signature detectors.

These exercise the detection primitives directly — in particular the contract that every
text signature stays silent on binary (``text is None``) input, which the public detector
relies on when it checks binary magic before attempting a text decode.
"""

from __future__ import annotations

import pytest

from orbit_formats import UnknownFormatError
from orbit_formats import registry as registry_module
from orbit_formats._tle_lines import checksum_ok
from orbit_formats.formats import (
    Confidence,
    _ccsds_signature,
    _first_nonempty_line,
    _sig_rinex,
    _sig_sp3,
    _sig_stk,
    _sig_tle,
    extension_format,
    normalize_format,
)


def test_normalize_format_canonicalises_a_known_id() -> None:
    assert normalize_format("  CCSDS-OEM  ") == "ccsds-oem"
    assert normalize_format("tle") == "tle"


def test_normalize_format_rejects_an_unknown_id() -> None:
    with pytest.raises(UnknownFormatError, match="unknown format 'bogus'"):
        normalize_format("bogus")


def test_text_signatures_report_no_match_on_binary_input() -> None:
    oem = _ccsds_signature("CCSDS_OEM_VERS", "oem")
    for signature in (_sig_tle, _sig_sp3, _sig_stk, _sig_rinex, oem):
        assert signature(b"\x00\x01", None) == Confidence.NONE


def test_tle_checksum_rejects_a_non_digit_check_character() -> None:
    assert checksum_ok("1" + " " * 67 + "X") is False


def test_tle_signature_needs_both_lines() -> None:
    line2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537"
    assert _sig_tle(line2.encode(), line2) == Confidence.NONE


def test_tle_signature_ignores_a_69_char_non_element_line() -> None:
    bogus = "3 " + "x" * 67  # right length, leading "3 " — but not a TLE element line
    assert _sig_tle(bogus.encode(), bogus) == Confidence.NONE


def test_first_nonempty_line_skips_blanks_and_handles_an_empty_text() -> None:
    assert _first_nonempty_line("\n  \n#c data\n") == "#c data"
    assert _first_nonempty_line("   \n\n") is None


def test_extension_format_returns_none_for_an_unmapped_extension() -> None:
    assert extension_format(".bin") is None


def test_plugin_loading_is_idempotent() -> None:
    # The first lookup triggers the one-time reader/writer import; a second short-circuits.
    registry_module.get_reader("tle")
    assert registry_module._plugins_loaded is True
    registry_module.get_writer("ccsds-oem")
    assert registry_module._plugins_loaded is True
