"""Command-line interface — the ``orbit-formats convert`` one-shot conversion subcommand.

``convert`` is a thin shell over the public API: it runs exactly ``convert(input, to=...)``
followed by ``write(..., format=...)``, so the file it produces is identical to the one the
equivalent API calls produce. The input format is auto-detected (``--from`` overrides the
detection); lossy-conversion warnings are surfaced to **stderr** while the conversion still
succeeds, and the exit code is non-zero only on a hard failure (an unreadable input, an
unknown or read-only target format, or a conversion the library does not support).
"""

from __future__ import annotations

import argparse
import sys
import warnings
from collections.abc import Sequence

from orbit_formats import __version__, convert, write
from orbit_formats.errors import OrbitFormatsError
from orbit_formats.warnings import LossyConversionWarning

__all__ = ["main"]


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv`` and run the requested command, returning a process exit code.

    The console-script wrapper passes the return value to :func:`sys.exit`, so ``0`` means
    success (including a lossy-but-completed conversion) and ``1`` a hard failure. Argument
    or usage errors exit ``2`` via :mod:`argparse`.
    """
    args = _build_parser().parse_args(argv)
    return _run_convert(
        input_path=args.input,
        output_path=args.output,
        target_format=args.to,
        source_format=args.from_format,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orbit-formats",
        description="Convert between orbital state-vector and ephemeris formats.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    convert_parser = subcommands.add_parser(
        "convert",
        help="convert one file to another format",
        description=(
            "Read <input>, convert it to the --to format, and write it to <output>. "
            "The input format is auto-detected unless --from is given. Lossy conversions "
            "warn on stderr but still succeed; the exit code is non-zero only on a hard "
            "failure."
        ),
    )
    convert_parser.add_argument("input", help="path to the source file")
    convert_parser.add_argument("output", help="path to write the converted file to")
    convert_parser.add_argument(
        "--to",
        required=True,
        metavar="FORMAT",
        help="target format id (e.g. ccsds-oem)",
    )
    convert_parser.add_argument(
        "--from",
        dest="from_format",
        metavar="FORMAT",
        help="override input-format detection (default: auto-detect)",
    )
    return parser


def _run_convert(
    *,
    input_path: str,
    output_path: str,
    target_format: str,
    source_format: str | None,
) -> int:
    """Run one file-to-file conversion, surfacing lossy warnings and hard failures.

    Mirrors the equivalent ``convert`` / ``write`` API calls exactly; the only additions are
    routing lossy warnings to ``stderr`` and mapping the library's typed errors (and an
    unreadable input) to a non-zero exit code with a clean message. ``sys.stderr`` is read at
    call time, so a caller (or a test) that has redirected it is honoured.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            obj = convert(input_path, to=target_format, format=source_format)
            write(obj, output_path, format=target_format)
        except (OrbitFormatsError, OSError) as exc:
            print(f"orbit-formats: error: {exc}", file=sys.stderr)
            return 1
        _emit_lossy_warnings(caught)
    return 0


def _emit_lossy_warnings(caught: list[warnings.WarningMessage]) -> None:
    """Write each captured lossy-conversion warning to ``sys.stderr``, one per line."""
    for record in caught:
        message = record.message
        if isinstance(message, LossyConversionWarning):
            print(f"orbit-formats: warning: {message}", file=sys.stderr)
