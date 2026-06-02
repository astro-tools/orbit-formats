"""The static catalog of known formats — ids, signatures, extensions, and canonical form.

This module is pure data and pure functions: it knows *what* formats exist, how to
recognise each from a content signature, which file extensions hint at it, the canonical
form it prefers (the shape :mod:`orbit_formats.convert` routes through), and whether it
can be written. It depends only on the error types, so the detector
(:mod:`orbit_formats.detect`), the registry, and the public API can all build on it
without a cycle.

A format's *preferred canonical form* is one of: ``ephemeris`` (a Cartesian state-vector
time series), ``state`` (a single Cartesian state), ``mean-elements`` (a TLE/OMM-style
mean-element set), ``attitude`` (an attitude history), ``conjunction`` (a close approach),
``tracking`` (a tracking-data set), or ``ndm`` (the combined-NDM aggregate — a container of
several of the above, which carries no single form and so does not participate in conversion).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from orbit_formats.errors import UnknownFormatError

__all__ = [
    "FORMATS",
    "Confidence",
    "FormatSpec",
    "canonical_form",
    "extension_format",
    "is_known_format",
    "is_writable",
    "known_format_ids",
    "match_binary",
    "normalize_format",
    "score_text_formats",
]


class Confidence(IntEnum):
    """How strongly a detector matched. The highest-confidence match wins.

    ``CONTAINER`` outranks ``HIGH`` so the combined-NDM aggregate beats its own members on
    the inevitable tie: an ``<ndm>`` wrapper (or a KVN concatenation) also matches each child
    message's signature, and the container is the more specific, correct answer.
    """

    NONE = 0
    HIGH = 1
    CONTAINER = 2


# A signature inspects the raw bytes (binary magic) and/or the decoded text prefix and
# reports how confidently the format matched. ``text`` is ``None`` when the content did
# not decode as text (i.e. it is binary).
Signature = Callable[[bytes, "str | None"], Confidence]


@dataclass(frozen=True, slots=True)
class FormatSpec:
    """One known format: its id, detection signature, extensions, and canonical form."""

    id: str
    canonical_form: str
    extensions: tuple[str, ...] = ()
    binary: bool = False
    writable: bool = True
    signature: Signature | None = None


# --- signature detectors ---------------------------------------------------------------

_TLE_LINE_LEN = 69


def _tle_checksum_ok(line: str) -> bool:
    """A TLE line ends with a mod-10 checksum: digits sum to themselves, ``-`` counts 1."""
    check = line[68]
    if not check.isdigit():
        return False
    total = sum(int(ch) if ch.isdigit() else 1 if ch == "-" else 0 for ch in line[:68])
    return total % 10 == int(check)


def _sig_tle(data: bytes, text: str | None) -> Confidence:
    if text is None:
        return Confidence.NONE
    line1: str | None = None
    line2: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if len(line) != _TLE_LINE_LEN or line[1] != " ":
            continue
        if line[0] == "1":
            line1 = line
        elif line[0] == "2":
            line2 = line
        if line1 is not None and line2 is not None:
            break
    if line1 is None or line2 is None:
        return Confidence.NONE
    # Matched line structure; require valid checksums and an agreeing catalog number so
    # arbitrary text that happens to start "1 " / "2 " is not mistaken for a TLE.
    if line1[2:7] == line2[2:7] and _tle_checksum_ok(line1) and _tle_checksum_ok(line2):
        return Confidence.HIGH
    return Confidence.NONE


def _ccsds_signature(kvn_keyword: str, xml_root: str) -> Signature:
    """A CCSDS NDM member is either KVN (``CCSDS_<TYPE>_VERS =``) or XML.

    KVN opens with the ``CCSDS_<TYPE>_VERS =`` header keyword. XML carries the same
    ``CCSDS_<TYPE>_VERS`` marker in its root element's ``id`` attribute
    (``<oem id="CCSDS_OEM_VERS" ...>``); requiring the root element *and* that marker
    recognises both the namespaced form and the unqualified form orbit-formats' own
    serialiser emits — where the ``urn:ccsds:`` namespace is absent — while never matching a
    different NDM member (each keys on its own root and marker).
    """
    kvn_re = re.compile(rf"^\s*{kvn_keyword}\s*=", re.MULTILINE)
    xml_open_re = re.compile(rf"<{xml_root}\b")

    def signature(data: bytes, text: str | None) -> Confidence:
        if text is None:
            return Confidence.NONE
        if kvn_re.search(text):
            return Confidence.HIGH
        if xml_open_re.search(text) and (kvn_keyword in text or "urn:ccsds:" in text):
            return Confidence.HIGH
        return Confidence.NONE

    return signature


# The combined / aggregate NDM. XML opens with the ``<ndm>`` wrapper element; KVN has no
# standardised wrapper, so the aggregate is the individual KVN messages concatenated, each
# keeping its own ``CCSDS_<TYPE>_VERS =`` header — two or more of those header lines is the
# signal. Either match outranks the members (``Confidence.CONTAINER``): an ``<ndm>`` also
# satisfies each child's ``<oem>`` / ``<cdm>`` signature, and a concatenation satisfies each
# child's KVN signature, so the container must win the tie.
_NDM_XML_OPEN_RE = re.compile(r"<ndm\b")
_CCSDS_VERS_RE = re.compile(r"^\s*CCSDS_[A-Z0-9]+_VERS\s*=", re.MULTILINE)


def _sig_ndm(data: bytes, text: str | None) -> Confidence:
    if text is None:
        return Confidence.NONE
    if _NDM_XML_OPEN_RE.search(text) and ("urn:ccsds:" in text or "CCSDS_" in text):
        return Confidence.CONTAINER
    if len(_CCSDS_VERS_RE.findall(text)) >= 2:
        return Confidence.CONTAINER
    return Confidence.NONE


_STK_RE = re.compile(r"^stk\.v\.\d", re.IGNORECASE)
_RINEX_RE = re.compile(r"RINEX VERSION\s*/\s*TYPE")


def _first_nonempty_line(text: str) -> str | None:
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped:
            return stripped
    return None


def _sig_sp3(data: bytes, text: str | None) -> Confidence:
    if text is None:
        return Confidence.NONE
    first = _first_nonempty_line(text)
    if first is not None and len(first) >= 2 and first[0] == "#" and first[1] in "abcd":
        return Confidence.HIGH
    return Confidence.NONE


def _sig_stk(data: bytes, text: str | None) -> Confidence:
    # STK ephemeris and STK attitude share the ``stk.v.X.Y`` banner; the ``BEGIN`` block
    # keyword disambiguates them. Require ``BEGIN Ephemeris`` so an attitude ``.a`` (which
    # carries the same banner but ``BEGIN Attitude``) is not mistaken for an ephemeris.
    if text is None:
        return Confidence.NONE
    first = _first_nonempty_line(text)
    if first is None or not _STK_RE.match(first):
        return Confidence.NONE
    return Confidence.HIGH if "BEGIN Ephemeris" in text else Confidence.NONE


def _sig_stk_attitude(data: bytes, text: str | None) -> Confidence:
    # The attitude counterpart of ``_sig_stk``: the same ``stk.v.X.Y`` banner, keyed on the
    # ``BEGIN Attitude`` block so it never collides with the ephemeris ``.e``.
    if text is None:
        return Confidence.NONE
    first = _first_nonempty_line(text)
    if first is None or not _STK_RE.match(first):
        return Confidence.NONE
    return Confidence.HIGH if "BEGIN Attitude" in text else Confidence.NONE


def _sig_rinex(data: bytes, text: str | None) -> Confidence:
    if text is None:
        return Confidence.NONE
    # The "RINEX VERSION / TYPE" label sits in the header label field of the first line.
    return Confidence.HIGH if _RINEX_RE.search(text[:200]) else Confidence.NONE


def _sig_spk(data: bytes, text: str | None) -> Confidence:
    # A SPICE binary kernel opens with its DAF file-architecture id word.
    head = data[:8]
    return Confidence.HIGH if head.startswith((b"DAF/SPK", b"NAIF/DAF")) else Confidence.NONE


# --- the catalog -----------------------------------------------------------------------

# Order matters only for the rare case two text signatures tie; binary magic is checked
# first by the detector regardless of position. The GMAT report has no signature — it is
# recognised by extension or named with an explicit format=.
FORMATS: tuple[FormatSpec, ...] = (
    FormatSpec("spk", "ephemeris", (".bsp", ".spk"), binary=True, signature=_sig_spk),
    FormatSpec("tle", "mean-elements", (".tle", ".3le"), signature=_sig_tle),
    FormatSpec(
        "ccsds-oem", "ephemeris", (".oem",), signature=_ccsds_signature("CCSDS_OEM_VERS", "oem")
    ),
    FormatSpec(
        "ccsds-omm", "mean-elements", (".omm",), signature=_ccsds_signature("CCSDS_OMM_VERS", "omm")
    ),
    FormatSpec(
        "ccsds-opm", "state", (".opm",), signature=_ccsds_signature("CCSDS_OPM_VERS", "opm")
    ),
    FormatSpec(
        "ccsds-aem", "attitude", (".aem",), signature=_ccsds_signature("CCSDS_AEM_VERS", "aem")
    ),
    FormatSpec(
        "ccsds-apm", "attitude", (".apm",), signature=_ccsds_signature("CCSDS_APM_VERS", "apm")
    ),
    FormatSpec(
        "ccsds-cdm", "conjunction", (".cdm",), signature=_ccsds_signature("CCSDS_CDM_VERS", "cdm")
    ),
    FormatSpec(
        "ccsds-tdm", "tracking", (".tdm",), signature=_ccsds_signature("CCSDS_TDM_VERS", "tdm")
    ),
    FormatSpec(
        "ccsds-ocm", "ephemeris", (".ocm",), signature=_ccsds_signature("CCSDS_OCM_VERS", "ocm")
    ),
    FormatSpec("ccsds-ndm", "ndm", (".ndm",), signature=_sig_ndm),
    FormatSpec("sp3", "ephemeris", (".sp3",), writable=False, signature=_sig_sp3),
    FormatSpec("stk-ephemeris", "ephemeris", (".e", ".ephem"), signature=_sig_stk),
    FormatSpec("stk-attitude", "attitude", (".a",), signature=_sig_stk_attitude),
    FormatSpec("gmat-report", "ephemeris", (".report",), writable=False, signature=None),
    FormatSpec(
        "rinex-nav", "mean-elements", (".rnx", ".nav"), writable=False, signature=_sig_rinex
    ),
)

_BY_ID: dict[str, FormatSpec] = {spec.id: spec for spec in FORMATS}
_BY_EXTENSION: dict[str, str] = {ext: spec.id for spec in FORMATS for ext in spec.extensions}
# RINEX navigation files also use the version-2 "<2-digit-year><system letter>" suffix,
# e.g. ``.21n`` (GPS), ``.22g`` (GLONASS), ``.23l`` (Galileo).
_RINEX_NAV_EXT_RE = re.compile(r"^\.\d\d[ngl]$")


def is_known_format(format_id: str) -> bool:
    """Whether ``format_id`` is a catalogued format."""
    return format_id in _BY_ID


def known_format_ids() -> tuple[str, ...]:
    """All catalogued format ids, in catalog order."""
    return tuple(spec.id for spec in FORMATS)


def normalize_format(format: str) -> str:
    """Validate and canonicalise an explicit format id (lowercased, trimmed).

    This is the counterpart to detection: where :func:`orbit_formats.detect.detect_format`
    works out *what a source is*, this validates a format id a caller already supplied.
    Raises :class:`~orbit_formats.errors.UnknownFormatError` if it is not a known format.
    """
    normalized = format.strip().lower()
    if not is_known_format(normalized):
        raise UnknownFormatError(
            f"unknown format {format!r}; known formats: {', '.join(known_format_ids())}"
        )
    return normalized


def canonical_form(format_id: str) -> str:
    """The canonical form ``format_id`` prefers. Assumes ``format_id`` is known."""
    return _BY_ID[format_id].canonical_form


def is_writable(format_id: str) -> bool:
    """Whether ``format_id`` can be written. Assumes ``format_id`` is known."""
    return _BY_ID[format_id].writable


def extension_format(suffix: str | None) -> str | None:
    """Map a file extension (with leading dot) to a format id, or ``None`` if unmapped.

    Generic extensions (``.xml``, ``.txt``) are deliberately not mapped — they identify no
    single format and must be resolved by content signature or an explicit ``format=``.
    """
    if suffix is None:
        return None
    lowered = suffix.lower()
    if lowered in _BY_EXTENSION:
        return _BY_EXTENSION[lowered]
    if _RINEX_NAV_EXT_RE.match(lowered):
        return "rinex-nav"
    return None


def match_binary(data: bytes) -> str | None:
    """Check the binary-magic detectors against raw bytes, before any text decode."""
    for spec in FORMATS:
        if (
            spec.binary
            and spec.signature is not None
            and spec.signature(data, None) != Confidence.NONE
        ):
            return spec.id
    return None


def score_text_formats(data: bytes, text: str) -> list[tuple[str, Confidence]]:
    """Score every text-signature format against decoded ``text``; keep the matches."""
    scored: list[tuple[str, Confidence]] = []
    for spec in FORMATS:
        if spec.binary or spec.signature is None:
            continue
        confidence = spec.signature(data, text)
        if confidence != Confidence.NONE:
            scored.append((spec.id, confidence))
    return scored
