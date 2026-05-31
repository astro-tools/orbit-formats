"""The ``orbit-formats convert`` CLI.

The command is a thin shell over the public API, so the contract these tests pin is exactly
that: the file the CLI writes is byte-identical to the one the equivalent ``convert`` /
``write`` calls produce. Around that, they cover input auto-detection and the ``--from``
override, lossy warnings surfaced to stderr (without failing the run), and the hard failures
that earn a non-zero exit.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from orbit_formats import convert, write
from orbit_formats.cli import main

# A full-state GMAT report (two rows -> Ephemeris). It carries no OBJECT_ID and no central
# body, so synthesising an OEM from it warns for those two fields: a real lossy conversion
# that still succeeds. The report has no content signature, so it is recognised by its
# ``.report`` extension or an explicit ``--from gmat-report``.
REPORT_FULL = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   "
    b"Sat.EarthMJ2000Eq.Z   Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   "
    b"Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5   0.0\n"
    b"26 Nov 2026 12:01:00.000   6999.0   450.0   0.0   -0.5   7.49   0.0\n"
)

# A TLE — mean-elements form. OEM wants an ephemeris, and v0.1 has no propagator-free path
# across forms, so ``tle -> ccsds-oem`` is an unsupported conversion (a hard failure), not a
# silent propagation.
TLE = (
    b"ISS (ZARYA)\n"
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)

GOLDEN_OEM = Path(__file__).parent / "data" / "oem" / "golden_roundtrip.oem"


def _api_convert(source: str, output: Path, *, to: str, source_format: str | None = None) -> None:
    """Run the conversion through the public API (warnings muted) — the CLI's reference."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        obj = convert(source, to=to, format=source_format)
        write(obj, output, format=to)


# --- the headline contract: identical to the equivalent API calls ----------------------


def test_convert_matches_the_api_for_a_gmat_report(tmp_path: Path) -> None:
    source = tmp_path / "sat.report"
    source.write_bytes(REPORT_FULL)
    api_out = tmp_path / "api.oem"
    _api_convert(str(source), api_out, to="ccsds-oem")

    cli_out = tmp_path / "cli.oem"
    assert main(["convert", str(source), str(cli_out), "--to", "ccsds-oem"]) == 0
    assert cli_out.read_bytes() == api_out.read_bytes()


def test_convert_matches_the_api_for_an_oem_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "in.oem"
    source.write_bytes(GOLDEN_OEM.read_bytes())
    api_out = tmp_path / "api.oem"
    _api_convert(str(source), api_out, to="ccsds-oem")

    cli_out = tmp_path / "cli.oem"
    assert main(["convert", str(source), str(cli_out), "--to", "ccsds-oem"]) == 0
    assert cli_out.read_bytes() == api_out.read_bytes()


# --- input format resolution: auto-detection and the --from override -------------------


def test_input_format_is_auto_detected_from_content(tmp_path: Path) -> None:
    # An unknown extension, so only the OEM content signature can identify the input.
    source = tmp_path / "ephemeris.dat"
    source.write_bytes(GOLDEN_OEM.read_bytes())
    out = tmp_path / "out.oem"
    assert main(["convert", str(source), str(out), "--to", "ccsds-oem"]) == 0
    assert out.read_bytes() == GOLDEN_OEM.read_bytes()


def test_from_override_forces_the_input_format(tmp_path: Path) -> None:
    # A GMAT report has no content signature; in a file with an unknown extension it cannot
    # be auto-detected, so --from is what makes the read possible.
    source = tmp_path / "report.dat"
    source.write_bytes(REPORT_FULL)
    out = tmp_path / "out.oem"

    assert main(["convert", str(source), str(out), "--to", "ccsds-oem"]) == 1
    assert not out.exists()

    code = main(["convert", str(source), str(out), "--to", "ccsds-oem", "--from", "gmat-report"])
    assert code == 0
    assert out.read_bytes().startswith(b"CCSDS_OEM_VERS")


# --- lossy warnings: surfaced to stderr, run still succeeds -----------------------------


def test_lossy_conversion_warns_on_stderr_and_still_succeeds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "sat.report"
    source.write_bytes(REPORT_FULL)
    out = tmp_path / "out.oem"

    assert main(["convert", str(source), str(out), "--to", "ccsds-oem"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    # The dropped fields are named on stderr, and the output file was still written.
    assert "warning" in captured.err
    assert "OBJECT_ID" in captured.err
    assert "CENTER_NAME" in captured.err
    assert out.exists()


def test_lossless_conversion_is_quiet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "in.oem"
    source.write_bytes(GOLDEN_OEM.read_bytes())
    out = tmp_path / "out.oem"

    assert main(["convert", str(source), str(out), "--to", "ccsds-oem"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""


# --- hard failures: non-zero exit, message on stderr, no output ------------------------


def test_unsupported_cross_form_conversion_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The issue's headline tle -> ccsds-oem: mean elements to an ephemeris needs a propagator,
    # which is out of scope, so the API raises and the CLI mirrors it with a hard failure.
    source = tmp_path / "iss.tle"
    source.write_bytes(TLE)
    out = tmp_path / "out.oem"

    assert main(["convert", str(source), str(out), "--to", "ccsds-oem"]) == 1
    assert "error" in capsys.readouterr().err
    assert not out.exists()


def test_missing_input_file_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out.oem"
    assert main(["convert", str(tmp_path / "absent.oem"), str(out), "--to", "ccsds-oem"]) == 1
    assert "error" in capsys.readouterr().err
    assert not out.exists()


def test_unknown_target_format_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "in.oem"
    source.write_bytes(GOLDEN_OEM.read_bytes())
    out = tmp_path / "out.bin"
    assert main(["convert", str(source), str(out), "--to", "bogus"]) == 1
    assert "unknown format 'bogus'" in capsys.readouterr().err


# --- argument / usage errors: argparse owns these (exit 2) -----------------------------


def test_missing_required_to_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["convert", "in.oem", "out.oem"])
    assert excinfo.value.code == 2


def test_no_subcommand_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_version_flag_reports_the_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "0.1.0" in capsys.readouterr().out
