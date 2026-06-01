"""The combined-NDM reader and writer: detection, the multi-message return shape, KVN.

A combined NDM is the aggregate container that holds several member messages in one file.
:func:`~orbit_formats.read` returns a :class:`~orbit_formats.Combined` — an ordered tuple of
the member canonical objects plus the wrapper ``MESSAGE_ID`` / comments. The committed golden
``golden_ndm.ndm`` concatenates a CDM and an OEM (two distinct member types); the XML twin and
KVN ↔ XML parity live in ``test_ccsds_ndm_xml.py``.

CCSDS standardises the combined instantiation only in XML, so the KVN aggregate is the members
concatenated — each keeping its ``CCSDS_<TYPE>_VERS =`` header — with the members normalised to
the same type-grouped order the XML wrapper uses. The wrapper ``MESSAGE_ID`` has no KVN home.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orbit_formats import (
    Combined,
    Conjunction,
    Ephemeris,
    LossyConversionWarning,
    MalformedSourceError,
    UnsupportedConversionError,
    UnsupportedFormatError,
    convert,
    detect_format,
    read,
    write,
)
from orbit_formats.canonical.metadata import Metadata, Provenance
from orbit_formats.readers.ccsds_ndm import NDM_CHILD_ORDER, NdmFile, read_ndm
from orbit_formats.registry import get_reader, get_writer
from orbit_formats.writers.ndm import write_ndm

DATA = Path(__file__).parent / "data"
GOLDEN_KVN = DATA / "ndm" / "golden_ndm.ndm"
GOLDEN_XML = DATA / "ndm" / "golden_ndm.xml"
GOLDEN_OEM = DATA / "oem" / "golden_roundtrip.oem"
GOLDEN_CDM = DATA / "cdm" / "golden_cdm.cdm"


def _members() -> tuple[Conjunction, Ephemeris]:
    """A CDM and an OEM read from their single-message goldens (each carries source_native)."""
    cdm = read(GOLDEN_CDM.read_bytes())
    oem = read(GOLDEN_OEM.read_bytes())
    assert isinstance(cdm, Conjunction)
    assert isinstance(oem, Ephemeris)
    return cdm, oem


def _combined(message_id: str | None = None) -> Combined:
    cdm, oem = _members()
    return Combined(
        metadata=Metadata(provenance=Provenance(source_format="ccsds-ndm")),
        messages=(oem, cdm),  # deliberately not in NDM_CHILD_ORDER; the writer normalises it
        message_id=message_id,
        comments=("a combined NDM",),
    )


# --- registration & detection ----------------------------------------------------------


def test_reader_and_writer_are_registered_for_ccsds_ndm() -> None:
    assert get_reader("ccsds-ndm") is read_ndm
    assert get_writer("ccsds-ndm") is write_ndm


def test_kvn_aggregate_is_detected_before_reading() -> None:
    assert detect_format(GOLDEN_KVN.read_bytes()) == "ccsds-ndm"


def test_a_single_member_is_not_an_aggregate() -> None:
    # One CCSDS_*_VERS header is a single message, not a combined NDM.
    assert detect_format(GOLDEN_CDM.read_bytes()) == "ccsds-cdm"


# --- the multi-message return shape ----------------------------------------------------


def test_read_returns_a_combined_of_its_members() -> None:
    combined = read(GOLDEN_KVN.read_bytes())
    assert isinstance(combined, Combined)
    assert len(combined) == 2
    # The golden's members are normalised to the type-grouped order: CDM (conjunction) then OEM.
    assert [type(m).__name__ for m in combined.messages] == ["Conjunction", "Ephemeris"]


def test_combined_tags_provenance_and_keeps_the_wrapper_comments() -> None:
    combined = read(GOLDEN_KVN.read_bytes())
    assert isinstance(combined, Combined)
    assert combined.metadata.provenance is not None
    assert combined.metadata.provenance.source_format == "ccsds-ndm"
    assert "container" in combined.comments[0]
    native = combined.source_native
    assert isinstance(native, NdmFile)
    assert native.serialization == "kvn"


def test_each_member_keeps_its_own_source_native() -> None:
    combined = read(GOLDEN_KVN.read_bytes())
    assert isinstance(combined, Combined)
    formats = [m.source_native.format_name for m in combined.messages if m.source_native]
    assert formats == ["ccsds-cdm", "ccsds-oem"]
    # A member pulled out of the aggregate equals the same message read on its own.
    assert combined.messages[1] == read(GOLDEN_OEM.read_bytes())


# --- the Combined canonical type -------------------------------------------------------


def test_combined_equality_is_by_content_and_ignores_source_native() -> None:
    bare = read(GOLDEN_KVN.read_bytes())  # source_native is an NdmFile
    assert isinstance(bare, Combined)
    rebuilt = Combined(  # same content, no source_native
        metadata=bare.metadata, messages=bare.messages, comments=bare.comments
    )
    assert rebuilt == bare
    differing = Combined(metadata=bare.metadata, messages=bare.messages, message_id="X")
    assert differing != bare


def test_combined_coerces_messages_and_comments_to_tuples() -> None:
    cdm, oem = _members()
    # Deliberately pass lists: __post_init__ must coerce them to tuples (so equality, which
    # compares tuples, holds regardless of how the caller supplied the sequence).
    combined = Combined(metadata=Metadata(), messages=[cdm, oem], comments=["a", "b"])  # type: ignore[arg-type]
    assert isinstance(combined.messages, tuple)
    assert isinstance(combined.comments, tuple)
    assert len(combined) == 2


# --- KVN round-trip --------------------------------------------------------------------


def test_kvn_round_trip_is_byte_stable_against_the_golden() -> None:
    golden = GOLDEN_KVN.read_bytes()
    assert write_ndm(read(golden), ".ndm") == golden


def test_retain_source_kvn_round_trip_is_byte_identical() -> None:
    golden = GOLDEN_KVN.read_bytes()
    combined = read(golden, retain_source=True)
    assert write_ndm(combined, ".ndm") == golden


def test_public_read_write_round_trips_through_paths(tmp_path: Path) -> None:
    target = tmp_path / "aggregate.ndm"
    write(read(GOLDEN_KVN.read_bytes()), target)
    assert detect_format(target) == "ccsds-ndm"
    assert read(target) == read(GOLDEN_KVN.read_bytes())


# --- ordering normalisation ------------------------------------------------------------


def test_members_are_written_in_the_type_grouped_order() -> None:
    # Built CDM-last; the writer must still emit CDM before OEM (NDM_CHILD_ORDER).
    kvn = write_ndm(_combined(), ".ndm").decode("utf-8")
    versions = [line.split("=")[0].strip() for line in kvn.splitlines() if "_VERS" in line]
    assert versions == ["CCSDS_CDM_VERS", "CCSDS_OEM_VERS"]
    assert NDM_CHILD_ORDER.index("ccsds-cdm") < NDM_CHILD_ORDER.index("ccsds-oem")


def test_member_order_does_not_change_the_serialised_output() -> None:
    cdm, oem = _members()
    spine = Metadata(provenance=Provenance(source_format="ccsds-ndm"))
    one = Combined(metadata=spine, messages=(oem, cdm))
    two = Combined(metadata=spine, messages=(cdm, oem))
    assert write_ndm(one, ".ndm") == write_ndm(two, ".ndm")


# --- the wrapper MESSAGE_ID has no KVN home --------------------------------------------


def test_message_id_is_reported_as_a_loss_on_a_kvn_write() -> None:
    with pytest.warns(LossyConversionWarning) as caught:
        kvn = write_ndm(_combined(message_id="NDM-001"), ".ndm")
    dropped = {field for record in caught for field in getattr(record.message, "fields", ())}
    assert "MESSAGE_ID" in dropped
    assert b"NDM-001" not in kvn


# --- error paths -----------------------------------------------------------------------


def test_fewer_than_two_members_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="two or more"):
        read(GOLDEN_CDM.read_bytes(), format="ccsds-ndm")


def test_content_before_the_first_member_is_rejected() -> None:
    junk = b"not a comment\nCCSDS_OEM_VERS = 2.0\nCCSDS_CDM_VERS = 1.0\n"
    with pytest.raises(MalformedSourceError, match="before the first combined-NDM member"):
        read(junk, format="ccsds-ndm")


def test_an_unreadable_member_type_is_rejected_not_dropped() -> None:
    # ACM has no reader in this library; an aggregate that carries one must fail loudly.
    aggregate = b"CCSDS_ACM_VERS = 2.0\nCCSDS_OEM_VERS = 2.0\n"
    with pytest.raises(UnsupportedFormatError, match="CCSDS_ACM_VERS"):
        read(aggregate, format="ccsds-ndm")


def test_an_aggregate_does_not_participate_in_conversion() -> None:
    combined = read(GOLDEN_KVN.read_bytes())
    with pytest.raises(UnsupportedConversionError):
        convert(combined, to="ccsds-oem")
    with pytest.raises(UnsupportedConversionError):
        convert(read(GOLDEN_OEM.read_bytes()), to="ccsds-ndm")


def test_writing_a_non_combined_to_ndm_is_unsupported() -> None:
    with pytest.raises(UnsupportedConversionError):
        write_ndm(read(GOLDEN_OEM.read_bytes()), ".ndm")


def test_a_member_without_an_ndm_source_native_cannot_be_written() -> None:
    # A synthesised ephemeris carries no member source_native, so the writer cannot know which
    # NDM message it should serialise as.
    template = read(GOLDEN_OEM.read_bytes())
    assert isinstance(template, Ephemeris)
    bare = Ephemeris(
        metadata=Metadata(object_name="SAT", reference_frame="EME2000", time_scale="UTC"),
        epochs=template.epochs,
        positions=template.positions,
        velocities=template.velocities,
    )
    combined = Combined(metadata=Metadata(), messages=(bare,))
    with pytest.raises(UnsupportedConversionError):
        write_ndm(combined, ".ndm")
