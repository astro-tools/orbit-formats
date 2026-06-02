"""Conversion-capability introspection — classify every ``(source, target)`` format pair.

This is the machine-readable counterpart to ``docs/conversion-matrix.md``: it derives, from the
same code the converter routes through, *whether* a conversion is possible and *why*, so the
published matrix cannot drift from the implementation. It deliberately reports only the
**structural** outcome — supported (same format, same canonical form, or a registered cross-form
edge) versus unsupported (a different form with no edge, a mean-element theory mismatch, or the
combined-NDM aggregate). Whether a *supported* conversion is lossless or lossy depends on the
particular object (which fields it carries), not on the format pair, so that distinction stays in
the prose and is asserted by the per-format and matrix-wide no-silent-loss tests.

Everything here is derived from :mod:`orbit_formats.formats` (the canonical form each format
prefers and whether it can be written), :func:`orbit_formats.convert.graph.conversion_edges` (the
registered cross-form bridges), and the mean-element theory rule
(:func:`orbit_formats.canonical.elements.ensure_convertible_to_mean_format`) — no second copy of
any of those facts lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from orbit_formats.canonical.elements import _SGP4_MEAN_ELEMENT_FORMATS
from orbit_formats.convert.graph import conversion_edges
from orbit_formats.formats import canonical_form, is_writable, known_format_ids, normalize_format

__all__ = [
    "ConversionCapability",
    "ConversionKind",
    "capability_matrix",
    "conversion_capability",
]

_MEAN_FORM = "mean-elements"
_NDM_FORM = "ndm"

# Source formats whose mean-element output uses the GNSS *broadcast* theory rather than SGP4/TEME.
# RINEX navigation is the only one; its broadcast records cannot be written as a TLE/OMM without a
# propagate-and-refit, mirroring the gate in
# :func:`orbit_formats.canonical.elements.ensure_convertible_to_mean_format`. (TLE and OMM, the
# SGP4 mean formats, live in ``_SGP4_MEAN_ELEMENT_FORMATS``, imported above as the single source of
# truth.) The matrix-wide and doc-parity tests fail if this classification ever diverges from the
# runtime behaviour.
_BROADCAST_MEAN_SOURCES = frozenset({"rinex-nav"})

# Ephemeris targets that are interpolatable trajectories and need at least two states, so the
# single-state -> series bridge cannot feed them: a single state is not a trajectory. SPK (a
# Lagrange/Hermite segment) is the only one; OEM, STK, and OCM accept a length-1 ephemeris. The
# SPK writer enforces the same minimum at runtime; the matrix-wide test fails if they diverge.
_TRAJECTORY_TARGETS = frozenset({"spk"})


class ConversionKind(Enum):
    """How a ``(source, target)`` format pair converts — the structural classification.

    The first three are *supported*; the last three are *unsupported* and name why. See
    :attr:`ConversionCapability.supported`.
    """

    SAME_FORMAT = "same-format"
    SAME_FORM = "same-form"
    CROSS_FORM_EDGE = "cross-form-edge"
    UNSUPPORTED_CROSS_FORM = "unsupported-cross-form"
    UNSUPPORTED_THEORY = "unsupported-theory"
    UNSUPPORTED_AGGREGATE = "unsupported-aggregate"
    UNSUPPORTED_DEGENERATE = "unsupported-degenerate"


_SUPPORTED_KINDS = frozenset(
    {ConversionKind.SAME_FORMAT, ConversionKind.SAME_FORM, ConversionKind.CROSS_FORM_EDGE}
)


@dataclass(frozen=True, slots=True)
class ConversionCapability:
    """The classification of one ``(source_format, target_format)`` conversion."""

    source_format: str
    target_format: str
    source_form: str
    target_form: str
    kind: ConversionKind

    @property
    def supported(self) -> bool:
        """Whether the conversion is possible at all (it may still be lossy)."""
        return self.kind in _SUPPORTED_KINDS

    @property
    def lossless_guaranteed(self) -> bool:
        """Whether the conversion is lossless for *any* input (only a same-format write is)."""
        return self.kind is ConversionKind.SAME_FORMAT

    @property
    def reason(self) -> str:
        """A one-line explanation of the classification, for docs and error context."""
        kind = self.kind
        if kind is ConversionKind.SAME_FORMAT:
            return "same format — byte- or content-lossless via the source's fidelity model"
        if kind is ConversionKind.SAME_FORM:
            return (
                f"both formats use the {self.source_form!r} canonical form; the target writer "
                "carries what the canonical object holds"
            )
        if kind is ConversionKind.CROSS_FORM_EDGE:
            return (
                f"a propagator-free edge bridges the {self.source_form!r} and "
                f"{self.target_form!r} forms"
            )
        if kind is ConversionKind.UNSUPPORTED_THEORY:
            return (
                "a GNSS broadcast mean set cannot be written as an SGP4/TEME mean-element format "
                "without a propagate-and-refit"
            )
        if kind is ConversionKind.UNSUPPORTED_AGGREGATE:
            return (
                "the combined-NDM aggregate carries no single canonical form and does not "
                "participate in conversion"
            )
        if kind is ConversionKind.UNSUPPORTED_DEGENERATE:
            return (
                f"{self.target_format!r} is an interpolatable trajectory of at least two states; "
                "a single state cannot be expressed as one"
            )
        return (
            f"a {self.source_form!r} to a {self.target_form!r} needs a model step "
            "(a propagation or an orbit fit), out of scope"
        )


def conversion_capability(source_format: str, target_format: str) -> ConversionCapability:
    """Classify converting ``source_format`` to ``target_format`` (both format ids).

    Returns the structural :class:`ConversionKind` and a :attr:`~ConversionCapability.reason`,
    derived from the canonical form each format prefers, the registered cross-form edges, and the
    mean-element theory rule — the same facts :func:`orbit_formats.convert.graph.route` and
    :func:`orbit_formats.api.convert` act on. Raises
    :class:`~orbit_formats.errors.UnknownFormatError` for an unknown format id.

    The result describes the *routing* a :func:`~orbit_formats.api.convert` call would take; it
    does not consider whether the target is writable (that is a :func:`~orbit_formats.api.write`
    concern), so a read-only target still classifies by form. :func:`capability_matrix` lists only
    writable targets, the ones that are conversion *destinations*.
    """
    src = normalize_format(source_format)
    tgt = normalize_format(target_format)
    sform = canonical_form(src)
    tform = canonical_form(tgt)
    return ConversionCapability(src, tgt, sform, tform, _classify(src, tgt, sform, tform))


def capability_matrix() -> tuple[ConversionCapability, ...]:
    """The capability of every ``(source, writable target)`` pair, in catalog order.

    Rows range over every known format (anything readable can be a source); columns over the
    writable formats (only those can be a conversion destination). This is the authoritative
    table ``docs/conversion-matrix.md`` documents and the doc-parity test asserts against.
    """
    sources = known_format_ids()
    targets = tuple(fmt for fmt in known_format_ids() if is_writable(fmt))
    return tuple(conversion_capability(src, tgt) for src in sources for tgt in targets)


def _classify(src: str, tgt: str, sform: str, tform: str) -> ConversionKind:
    if sform == _NDM_FORM or tform == _NDM_FORM:
        return ConversionKind.UNSUPPORTED_AGGREGATE
    if src == tgt:
        return ConversionKind.SAME_FORMAT
    if (
        sform == _MEAN_FORM
        and tform == _MEAN_FORM
        and src in _BROADCAST_MEAN_SOURCES
        and tgt in _SGP4_MEAN_ELEMENT_FORMATS
    ):
        return ConversionKind.UNSUPPORTED_THEORY
    if sform == tform:
        return ConversionKind.SAME_FORM
    if sform == "state" and tgt in _TRAJECTORY_TARGETS:
        return ConversionKind.UNSUPPORTED_DEGENERATE
    if (sform, tform) in conversion_edges():
        return ConversionKind.CROSS_FORM_EDGE
    return ConversionKind.UNSUPPORTED_CROSS_FORM
