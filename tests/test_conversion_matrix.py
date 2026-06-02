"""The conversion-capability matrix as a contract.

Three things are asserted here, together making the published matrix the v1.0 contract:

1. **The capability classifier** (`conversion_capability` / `capability_matrix`) reports the right
   structural kind for representative pairs and is total over the catalog.
2. **The no-silent-loss meta-test** runs every ``(source, target)`` pair end to end (read → convert
   → write) and checks the whole matrix honours the contract: a pair the classifier calls supported
   succeeds and every warning it emits is a structured :class:`LossyConversionWarning` naming at
   least one dropped field; a pair it calls unsupported raises a typed
   :class:`UnsupportedConversionError`. Nothing raises a raw third-party error and nothing drops a
   field in silence.
3. **The doc-parity test** parses ``docs/conversion-matrix.md`` and asserts its ✅/⚠️/❌ cells agree
   with the classifier, so the page cannot drift from the code.
"""

from __future__ import annotations

import io
import warnings
from pathlib import Path

import numpy as np
import pytest

from orbit_formats import (
    ConversionKind,
    Ephemeris,
    Metadata,
    StateVector,
    UnknownFormatError,
    UnsupportedConversionError,
    capability_matrix,
    conversion_capability,
    convert,
    read,
    write,
)
from orbit_formats.canonical.base import Canonical
from orbit_formats.formats import is_writable, known_format_ids
from orbit_formats.warnings import LossyConversionWarning

try:  # SPK lives behind the [spk] extra; skip its cells when spiceypy is absent.
    import spiceypy  # noqa: F401

    _HAS_SPICE = True
except ImportError:
    _HAS_SPICE = False

_DATA = Path(__file__).parent / "data"
_DOC = Path(__file__).parent.parent / "docs" / "conversion-matrix.md"

_TLE = (
    b"1 25544U 98067A   08264.51782528 -.00002182  00000-0 -11606-4 0  2927\n"
    b"2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.72125391563537\n"
)
_GMAT_REPORT = (
    b"Sat.UTCGregorian   Sat.EarthMJ2000Eq.X   Sat.EarthMJ2000Eq.Y   Sat.EarthMJ2000Eq.Z   "
    b"Sat.EarthMJ2000Eq.VX   Sat.EarthMJ2000Eq.VY   Sat.EarthMJ2000Eq.VZ\n"
    b"26 Nov 2026 12:00:00.000   7000.0   0.0   0.0   0.0   7.5   0.0\n"
    b"26 Nov 2026 12:01:00.000   6999.0   450.0   0.0   -0.5   7.49   0.0\n"
)

# One representative, complete source per readable format (the same goldens the per-format tests
# use), plus an explicit format for the two signature-less / inline sources.
_SOURCES: dict[str, tuple[bytes | Path, str | None]] = {
    "tle": (_TLE, "tle"),
    "ccsds-omm": (_DATA / "omm/golden_omm.omm", None),
    "ccsds-opm": (_DATA / "opm/golden_opm.opm", None),
    "ccsds-oem": (_DATA / "oem/golden_roundtrip.oem", None),
    "stk-ephemeris": (_DATA / "stk/golden_roundtrip.e", None),
    "stk-attitude": (_DATA / "stk/golden_roundtrip.a", None),
    "sp3": (_DATA / "sp3/sample_sp3c.sp3", None),
    "gmat-report": (_GMAT_REPORT, "gmat-report"),
    "rinex-nav": (_DATA / "rinex/sample_rinex3_mixed.rnx", None),
    "ccsds-ocm": (_DATA / "ocm/golden_ocm.ocm", None),
    "spk": (_DATA / "spk/golden.bsp", None),
    "ccsds-aem": (_DATA / "aem/golden_aem.aem", None),
    "ccsds-apm": (_DATA / "apm/golden_apm.apm", None),
    "ccsds-cdm": (_DATA / "cdm/golden_cdm.cdm", None),
    "ccsds-tdm": (_DATA / "tdm/golden_tdm.tdm", None),
    "ccsds-ndm": (_DATA / "ndm/golden_ndm.ndm", None),
    "omm-json": (_DATA / "omm/golden_omm.json", None),
    "omm-csv": (_DATA / "omm/golden_omm.csv", None),
}

# Destination extension per writable format, so write() resolves the right writer/notation.
_EXTENSION: dict[str, str] = {
    "tle": ".tle",
    "ccsds-omm": ".omm",
    "ccsds-opm": ".opm",
    "ccsds-oem": ".oem",
    "stk-ephemeris": ".e",
    "stk-attitude": ".a",
    "ccsds-ocm": ".ocm",
    "sp3": ".sp3",
    "spk": ".bsp",
    "ccsds-aem": ".aem",
    "ccsds-apm": ".apm",
    "ccsds-cdm": ".cdm",
    "ccsds-tdm": ".tdm",
    "ccsds-ndm": ".ndm",
    "omm-json": ".json",
    "omm-csv": ".csv",
}

_SOURCE_FORMATS = list(known_format_ids())
_TARGET_FORMATS = [fmt for fmt in known_format_ids() if is_writable(fmt)]
_PAIRS = [(source, target) for source in _SOURCE_FORMATS for target in _TARGET_FORMATS]

_SOURCE_CACHE: dict[str, Canonical] = {}


def _load_source(fmt: str) -> Canonical:
    if fmt not in _SOURCE_CACHE:
        payload, explicit = _SOURCES[fmt]
        source: object = io.BytesIO(payload) if isinstance(payload, bytes) else payload
        _SOURCE_CACHE[fmt] = read(source, format=explicit)  # type: ignore[arg-type]
    return _SOURCE_CACHE[fmt]


# --- 1. the capability classifier ------------------------------------------------------


def test_every_source_and_writable_target_is_covered_exactly_once() -> None:
    matrix = capability_matrix()
    pairs = {(cap.source_format, cap.target_format) for cap in matrix}
    assert len(matrix) == len(pairs) == len(_SOURCE_FORMATS) * len(_TARGET_FORMATS)
    assert {cap.target_format for cap in matrix} == set(_TARGET_FORMATS)
    assert {cap.source_format for cap in matrix} == set(_SOURCE_FORMATS)


@pytest.mark.parametrize(
    "source,target,kind",
    [
        ("ccsds-oem", "ccsds-oem", ConversionKind.SAME_FORMAT),
        ("tle", "ccsds-omm", ConversionKind.SAME_FORM),
        ("ccsds-aem", "ccsds-apm", ConversionKind.SAME_FORM),
        ("ccsds-opm", "ccsds-oem", ConversionKind.CROSS_FORM_EDGE),
        ("ccsds-oem", "ccsds-opm", ConversionKind.CROSS_FORM_EDGE),
        ("ccsds-opm", "spk", ConversionKind.UNSUPPORTED_DEGENERATE),
        ("rinex-nav", "tle", ConversionKind.UNSUPPORTED_THEORY),
        ("tle", "ccsds-oem", ConversionKind.UNSUPPORTED_CROSS_FORM),
        ("ccsds-ndm", "ccsds-oem", ConversionKind.UNSUPPORTED_AGGREGATE),
        ("ccsds-oem", "ccsds-ndm", ConversionKind.UNSUPPORTED_AGGREGATE),
    ],
)
def test_capability_classifies_representative_pairs(
    source: str, target: str, kind: ConversionKind
) -> None:
    cap = conversion_capability(source, target)
    assert cap.kind is kind
    assert cap.supported == (kind in {kind.SAME_FORMAT, kind.SAME_FORM, kind.CROSS_FORM_EDGE})
    assert cap.reason  # every kind explains itself


def test_only_a_same_format_conversion_is_lossless_guaranteed() -> None:
    assert conversion_capability("ccsds-oem", "ccsds-oem").lossless_guaranteed
    assert not conversion_capability("ccsds-opm", "ccsds-oem").lossless_guaranteed


def test_capability_rejects_an_unknown_format() -> None:
    with pytest.raises(UnknownFormatError):
        conversion_capability("bogus", "ccsds-oem")


# --- 2. the whole-matrix no-silent-loss meta-test --------------------------------------


@pytest.mark.parametrize("source,target", _PAIRS, ids=[f"{s}->{t}" for s, t in _PAIRS])
def test_matrix_pair_honours_the_no_silent_loss_contract(
    source: str, target: str, tmp_path: Path
) -> None:
    if (source == "spk" or target == "spk") and not _HAS_SPICE:
        pytest.skip("spk requires the [spk] extra (spiceypy)")
    obj = _load_source(source)
    cap = conversion_capability(source, target)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            converted = convert(obj, to=target)
            write(converted, tmp_path / f"out{_EXTENSION[target]}", format=target)
        except UnsupportedConversionError:
            assert not cap.supported, (
                f"{source} -> {target}: refused at runtime but the matrix calls it supported "
                f"({cap.kind.value})"
            )
            return

    assert cap.supported, (
        f"{source} -> {target}: succeeded but the matrix calls it unsupported ({cap.kind.value})"
    )
    for record in caught:
        if isinstance(record.message, LossyConversionWarning):
            assert record.message.dropped, (
                f"{source} -> {target}: a lossy warning named no dropped field (silent loss)"
            )


# --- 3. the doc-parity test ------------------------------------------------------------


def _parse_doc_matrix() -> dict[tuple[str, str], str]:
    """Parse the marked capability table in the matrix doc into ``{(source, target): symbol}``."""
    lines = _DOC.read_text(encoding="utf-8").splitlines()
    marker = next(i for i, line in enumerate(lines) if "capability-matrix" in line)
    head = next(i for i in range(marker, len(lines)) if lines[i].lstrip().startswith("|"))
    rows: list[str] = []
    for line in lines[head:]:  # the one contiguous table block right after the marker
        if not line.lstrip().startswith("|"):
            break
        rows.append(line)
    header = _split_row(rows[0])[1:]  # drop the "Source ╲ Target" corner label
    targets = [_unquote(cell) for cell in header]
    matrix: dict[tuple[str, str], str] = {}
    for row in rows[1:]:
        cells = _split_row(row)
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue  # the |---|---| separator row
        source = _unquote(cells[0])
        for target, symbol in zip(targets, cells[1:], strict=True):
            matrix[(source, target)] = symbol
    return matrix


def _split_row(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _unquote(cell: str) -> str:
    return cell.strip().strip("`").strip()


def _symbol_supported(symbol: str) -> bool:
    if "❌" in symbol:
        return False
    assert "✅" in symbol or "⚠" in symbol, f"unrecognised matrix cell {symbol!r}"
    return True


def test_doc_matrix_covers_exactly_the_catalog() -> None:
    matrix = _parse_doc_matrix()
    assert {source for source, _ in matrix} == set(_SOURCE_FORMATS)
    assert {target for _, target in matrix} == set(_TARGET_FORMATS)
    assert len(matrix) == len(_SOURCE_FORMATS) * len(_TARGET_FORMATS)


def test_doc_matrix_matches_capabilities() -> None:
    for (source, target), symbol in _parse_doc_matrix().items():
        cap = conversion_capability(source, target)
        assert _symbol_supported(symbol) == cap.supported, (
            f"docs/conversion-matrix.md {source} -> {target} = {symbol!r} disagrees with "
            f"conversion_capability (kind={cap.kind.value}, supported={cap.supported})"
        )


# --- the single <-> series cross-form edges --------------------------------------------


def _ephemeris(rows: int) -> Ephemeris:
    epochs = np.array(
        [np.datetime64("2024-01-01T00:00:00", "ns") + np.timedelta64(i, "m") for i in range(rows)],
        dtype="datetime64[ns]",
    )
    return Ephemeris(
        metadata=Metadata(reference_frame="EME2000", time_scale="UTC", central_body="EARTH"),
        epochs=epochs,
        positions=np.tile([7000.0, 0.0, 0.0], (rows, 1)),
        velocities=np.tile([0.0, 7.5, 0.0], (rows, 1)),
        interpolation="LAGRANGE",
        interpolation_degree=5,
    )


def test_state_embeds_as_a_length_one_ephemeris_losslessly() -> None:
    state = StateVector(
        metadata=Metadata(reference_frame="EME2000", time_scale="UTC", central_body="EARTH"),
        epoch=np.datetime64("2024-01-01T00:00:00", "ns"),
        position=np.array([7000.0, 0.0, 0.0]),
        velocity=np.array([0.0, 7.5, 0.0]),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", LossyConversionWarning)  # a lossless edge must not warn
        eph = convert(state, to="ccsds-oem")
    assert isinstance(eph, Ephemeris)
    assert len(eph) == 1
    assert eph.source_native is None
    np.testing.assert_array_equal(eph.positions[0], state.position)


def test_one_sample_ephemeris_collapses_to_a_state_losslessly() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", LossyConversionWarning)
        state = convert(_ephemeris(1), to="ccsds-opm")
    assert isinstance(state, StateVector)


def test_multi_sample_ephemeris_collapse_warns_naming_the_dropped_epochs() -> None:
    with pytest.warns(LossyConversionWarning) as record:
        state = convert(_ephemeris(3), to="ccsds-opm")
    assert isinstance(state, StateVector)
    dropped = {field.name for warning in record for field in warning.message.dropped}  # type: ignore[union-attr]
    assert "epochs" in dropped
    assert "interpolation" in dropped


def test_empty_ephemeris_to_state_is_refused() -> None:
    with pytest.raises(UnsupportedConversionError):
        convert(_ephemeris(0), to="ccsds-opm")
