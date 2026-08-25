"""
A claim is verified against the retrieved evidence, not the compressed excerpt.

Compression exists to fit the prompt budget: it keeps the sentences most
relevant to the query and drops the rest. `ContextChunk.text` is therefore what
the model was shown, not the whole of what was retrieved.

Verification used that same trimmed text, so a true claim was discarded whenever
the sentence supporting it happened to be cut for length - and every claim being
discarded is what produced INSUFFICIENT_EVIDENCE with "Generated claims were not
supported by project evidence". Observed on the deployment for
"What interrupting rating does the switchgear specification require?", which
compressed to 131 tokens, while questions that compressed to 292 and 428 tokens
answered normally.

Widening the check to the retrieved text cannot admit an unsupported claim: the
excerpt is a subset of it, and both are evidence the retriever actually returned
for that citation id.
"""

import uuid

import pytest

from app.context import ContextChunk
from app.workflow import _GeneratedClaim, _deterministic_support, _evidence_text

RETRIEVED = (
    "Short-circuit interrupting rating: not less than 65 kAIC at 480 V for all main "
    "and feeder protective devices. Form of separation: Form 3b equivalent "
    "compartment segregation for this synthetic project."
)
# What compression kept for a query that matched the separation sentence more
# strongly than the rating sentence.
SHOWN = "Form of separation: Form 3b equivalent compartment segregation for this synthetic project."


def chunk(*, shown: str, retrieved: str) -> ContextChunk:
    return ContextChunk(
        chunk_id="c1",
        parent_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_type="specification",
        project_id=uuid.uuid4(),
        page=2,
        section="2.2 Electrical requirements",
        text=shown,
        score=1.0,
        dense_rank=1,
        bm25_rank=1,
        rrf_score=1.0,
        citation={
            "document_id": str(uuid.uuid4()),
            "filename": "Switchgear_Specification.md",
            "page": 2,
            "section": "2.2",
        },
        attributes={},
        rerank_score=0.9,
        source_text=retrieved,
    )


def claim(text: str) -> _GeneratedClaim:
    return _GeneratedClaim(text=text, type="fact", citation_ids=["C1"])


def test_evidence_text_prefers_the_retrieved_source() -> None:
    assert _evidence_text(chunk(shown=SHOWN, retrieved=RETRIEVED)) == RETRIEVED


def test_evidence_text_falls_back_to_the_excerpt() -> None:
    """A chunk built without a source (older callers, tests) still verifies."""
    assert _evidence_text(chunk(shown=SHOWN, retrieved="")) == SHOWN


def test_a_true_claim_survives_when_compression_trimmed_its_sentence() -> None:
    """The exact case that made the copilot refuse."""
    supported = claim("The specification requires not less than 65 kAIC at 480 V.")

    # Verified against the excerpt alone, as it was before: rejected.
    assert _deterministic_support(supported, {"C1": chunk(shown=SHOWN, retrieved=SHOWN)}) == "UNSUPPORTED"

    # Verified against what was actually retrieved: supported.
    assert _deterministic_support(supported, {"C1": chunk(shown=SHOWN, retrieved=RETRIEVED)}) == "SUPPORTED"


def test_a_claim_the_evidence_does_not_support_is_still_rejected() -> None:
    """Widening the evidence must not turn the verifier into a rubber stamp."""
    invented = claim("The specification requires not less than 95 kAIC at 690 V.")
    assert _deterministic_support(invented, {"C1": chunk(shown=SHOWN, retrieved=RETRIEVED)}) == "UNSUPPORTED"


def test_a_claim_with_no_citation_is_rejected() -> None:
    uncited = _GeneratedClaim(text="Anything at all.", type="fact", citation_ids=[])
    assert _deterministic_support(uncited, {}) == "UNSUPPORTED"


@pytest.mark.parametrize("figure", ["65 kAIC", "480 V", "Form 3b"])
def test_figures_present_in_the_retrieved_evidence_are_found(figure: str) -> None:
    assert figure in _evidence_text(chunk(shown=SHOWN, retrieved=RETRIEVED))
