"""The public ``read`` / ``write`` / ``convert`` entry points.

These tie the catalog, the detector, and the reader/writer registry together:

- :func:`read` resolves the format (explicit or detected) and dispatches to the
  registered reader, returning the appropriate canonical subtype.
- :func:`write` resolves the target format (explicit or from the destination extension)
  and dispatches to the registered writer, serialising to the destination.
- :func:`convert` resolves the input to a canonical object (reading it first if given a
  path) and returns it in the form the target format expects.

A format with no registered reader/writer raises
:class:`~orbit_formats.errors.UnsupportedFormatError`; cross-form conversion that has no
available path raises :class:`~orbit_formats.errors.UnsupportedConversionError`.
"""

from __future__ import annotations

import os
from pathlib import Path

from orbit_formats.canonical.attitude import Attitude
from orbit_formats.canonical.base import Canonical
from orbit_formats.canonical.conjunction import Conjunction
from orbit_formats.canonical.elements import MeanElementSet
from orbit_formats.canonical.ephemeris import Ephemeris
from orbit_formats.canonical.state import StateVector
from orbit_formats.convert.graph import route
from orbit_formats.detect import detect_format_from_source
from orbit_formats.errors import (
    UnknownFormatError,
    UnsupportedConversionError,
    UnsupportedFormatError,
)
from orbit_formats.formats import (
    canonical_form,
    extension_format,
    is_writable,
    normalize_format,
)
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.source import SourceInput, load_source

__all__ = ["convert", "read", "write"]

# The canonical form each category type projects to, used to decide when a
# conversion is a no-op (the object is already in the target format's preferred form).
_FORM_BY_TYPE: dict[type[Canonical], str] = {
    Ephemeris: "ephemeris",
    StateVector: "state",
    MeanElementSet: "mean-elements",
    Attitude: "attitude",
    Conjunction: "conjunction",
}


def read(
    source: SourceInput, *, format: str | None = None, retain_source: bool = False
) -> Canonical:
    """Read ``source`` into the appropriate canonical subtype.

    ``source`` is a path or in-memory buffer; an explicit ``format=`` overrides detection.
    Raises :class:`~orbit_formats.errors.UnsupportedFormatError` if the resolved format
    has no registered reader, and the detection errors otherwise (see
    :func:`~orbit_formats.detect.detect_format`).

    Set ``retain_source=True`` to keep the raw source bytes on the result's
    ``source_native`` fidelity model, so a later :func:`write` back to the same format
    reproduces the input **byte-for-byte**. It defaults to ``False`` — an ordinary read
    holds no extra copy, and a same-format write is then content-lossless (every field
    preserved, canonically formatted) rather than byte-identical. Only formats with a
    verbatim-capable fidelity model (the OEM reader today) honour it.
    """
    src = load_source(source, retain=retain_source)
    format_id = normalize_format(format) if format is not None else detect_format_from_source(src)
    reader = get_reader(format_id)
    if reader is None:
        raise UnsupportedFormatError(f"no reader is registered for format {format_id!r}")
    return reader(src)


def write(
    obj: Canonical, destination: str | os.PathLike[str], *, format: str | None = None
) -> None:
    """Write ``obj`` to ``destination`` in the given (or extension-inferred) format.

    The target format comes from an explicit ``format=`` or, failing that, the
    destination's extension. For a format with more than one notation — CCSDS OEM in KVN
    vs XML — the destination extension also selects the notation (``.oem`` → KVN, ``.xml``
    → XML); since ``.xml`` does not name a single NDM message, writing one needs an explicit
    ``format=`` (e.g. ``write(eph, "sat.xml", format="ccsds-oem")``). Raises
    :class:`~orbit_formats.errors.UnsupportedFormatError` for a read-only target or one
    with no registered writer, and :class:`~orbit_formats.errors.UnknownFormatError` if
    no format can be resolved.
    """
    format_id = _resolve_write_format(format, destination)
    if not is_writable(format_id):
        raise UnsupportedFormatError(f"{format_id!r} is a read-only format and cannot be written")
    writer = get_writer(format_id)
    if writer is None:
        raise UnsupportedFormatError(f"no writer is registered for format {format_id!r}")
    # The destination extension lets a multi-notation writer (CCSDS OEM: KVN vs XML) pick:
    # `.xml` → XML, `.oem` → KVN. Writers that have one notation ignore it.
    suffix = Path(destination).suffix.lower() or None
    Path(destination).write_bytes(writer(obj, suffix))


def convert(
    source: SourceInput | Canonical, to: str, *, format: str | None = None, frame: str | None = None
) -> Canonical:
    """Convert ``source`` to the canonical form the target format ``to`` expects.

    ``source`` is a canonical object or a path/buffer (read first, with ``format=`` as the
    read override). The result is a canonical object — serialise it with :func:`write`.
    When ``source`` is already in the target's preferred form the same object is returned;
    a cross-form conversion with no available path raises
    :class:`~orbit_formats.errors.UnsupportedConversionError`.

    Pass ``frame=`` (e.g. ``"J2000"``, ``"ITRF"``) to rotate the state into that reference
    frame; omitted, the source frame is kept. Supported frames are TEME, EME2000 / J2000,
    GCRF, ICRF, and ITRF; a rotation between two frames this version cannot relate — or a
    form with no Cartesian state to rotate — raises
    :class:`~orbit_formats.errors.FrameRotationUnsupportedError`. The rotation is lossless;
    it drops the byte-lossless ``source_native`` handle, since the rotated state no longer
    matches the original bytes.
    """
    target = normalize_format(to)
    obj = source if isinstance(source, Canonical) else read(source, format=format)
    source_form = _form_of(obj)
    target_form = canonical_form(target)
    # The conversion graph owns the routing decision: it resolves the target frame (a no-op
    # unless a rotation is needed), then a same-form conversion returns the object unchanged
    # (a later same-format write stays byte-lossless via source_native when nothing rotated);
    # a cross-form request with no available edge comes back as None and is reported as
    # unsupported here, where the target format id for the error is in hand.
    routed = route(obj, source_form, target_form, target_frame=frame)
    if routed is None:
        raise UnsupportedConversionError(source_form, target, target_form)
    return routed


def _resolve_write_format(format: str | None, destination: str | os.PathLike[str]) -> str:
    if format is not None:
        return normalize_format(format)
    suffix = Path(destination).suffix.lower() or None
    from_extension = extension_format(suffix)
    if from_extension is None:
        raise UnknownFormatError(
            "could not infer the target format from the destination; pass an explicit format="
        )
    return from_extension


def _form_of(obj: Canonical) -> str:
    form = _FORM_BY_TYPE.get(type(obj))
    if form is None:
        raise UnsupportedConversionError(type(obj).__name__, "unknown", "unknown")
    return form
