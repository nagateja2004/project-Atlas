"""
Equipment tags are recognised by shape, not from a whitelist.

Two defects motivated this, and both were visible in the running product:

  - The pattern named three families explicitly, so every other equipment item
    on a project was invisible to any view that lists equipment. None of the six
    items in the extended corpus could be selected anywhere.
  - `CRAC-\\d+` matched zero-padded document sequence numbers, so a phantom
    `CRAC-001` travelled into compliance findings alongside the real `CRAC-1`.
    Those findings then failed to pair with the shipment for the same equipment,
    and the impact-chain view silently fell back to a different equipment's
    shipment - presenting two unrelated items as one causal chain.
"""

import pytest

from app.ingestion import entity_references


def tags(text: str) -> list[str]:
    return entity_references(text)["equipment_tags"]


@pytest.mark.parametrize(
    "tag",
    [
        # The families the old pattern knew.
        "SWGR-A",
        "UPS-A",
        "CRAC-1",
        # The extended corpus, none of which the old pattern could see.
        "GEN-A",
        "CH-A",
        "PDU-A",
        "XFMR-A",
        "FS-A",
        "BMS-A",
        # Shapes a project might reasonably use.
        "SWGR-B2",
        "CRAC-12",
    ],
)
def test_recognises_an_equipment_tag_by_shape(tag: str) -> None:
    assert tags(f"Furnish {tag} for the data hall.") == [tag]


@pytest.mark.parametrize(
    "identifier",
    [
        "RFI-012",       # request for information
        "CO-001",        # change order
        "MM-014",        # meeting minutes
        "SUB-SWGR-002",  # submittal
        "SPEC-UPS-001",  # specification
        "T-140",         # schedule task
        "SHP-2001",      # shipment
        "CX-GENA-001",   # commissioning procedure
        "NCR-004",       # non-conformance
    ],
)
def test_document_identifiers_are_not_equipment(identifier: str) -> None:
    assert tags(f"See {identifier} for details.") == []


def test_zero_padded_suffix_is_a_sequence_number_not_a_designator() -> None:
    """The distinction that stopped findings pairing with their shipment."""
    assert tags("Submittal CRAC-001 covers CRAC-1.") == ["CRAC-1"]
    assert "CRAC-001" not in tags("CRAC-001 and CRAC-002 and CRAC-1")


def test_a_realistic_paragraph_yields_only_equipment() -> None:
    text = (
        "Per RFI-012 and change order CO-001, submittal SUB-SWGR-002 for SWGR-A "
        "offers 50 kAIC. Task T-140 slips, affecting CRAC-1 and UPS-A. Shipment "
        "SYN-SHP-001 is at risk. See specification SPEC-SWGR-001 clause 2.2.3."
    )
    assert tags(text) == ["CRAC-1", "SWGR-A", "UPS-A"]


def test_tags_are_deduplicated_and_sorted() -> None:
    assert tags("UPS-A, SWGR-A, UPS-A again, SWGR-A again") == ["SWGR-A", "UPS-A"]


def test_no_text_yields_no_tags() -> None:
    assert tags("") == []
    assert tags("No identifiers of any kind in this sentence.") == []
