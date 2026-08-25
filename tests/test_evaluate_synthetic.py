from scripts.evaluate_synthetic import run_evaluation
from scripts.evaluate_rag import evaluate

import pytest


def test_synthetic_end_to_end_evaluation_reports_planted_results() -> None:
    result = run_evaluation()

    assert result["ingestion"] == {"uploaded_documents": 27, "completed_documents": 27}
    assert result["compliance"] == {
        "true_positive": 6,
        "false_positive": 0,
        "false_negative": 0,
        "true_negative": 6,
        "precision": 1,
        "recall": 1,
        "f1": 1,
    }
    assert result["rfi"]["recall_at_k"] == 1
    assert all(rank <= result["rfi"]["k"] for rank in result["rfi"]["expected_pair_ranks"].values())
    assert result["citation_correctness"]["rate"] == 1
    assert result["schedule"]["risk_lead_time_days"] == 35
    assert result["commissioning"] == {"coverage_percent": 100, "status": "pass"}


@pytest.mark.asyncio
async def test_rag_evaluation_uses_held_out_split_and_writes_both_reports(tmp_path) -> None:
    result = await evaluate(tmp_path)

    # Sizes, not exact counts: the labelled set grows, and an assertion that
    # has to be edited every time one is added stops guarding anything. What
    # must hold is that both splits are real and the held-out set is large
    # enough that a single case cannot swing a reported metric - the earlier
    # three-case test split let one extra citation move precision by a third.
    development_cases = result["methodology"]["development_cases"]
    test_cases = result["methodology"]["test_cases"]
    assert development_cases >= 4
    assert test_cases >= 10, "a held-out split this small cannot separate a result from noise"
    assert set(result["test"]) == {"baseline", "advanced"}
    comparison = result["contextual_retrieval_comparison"]
    assert set(comparison) == {"scope", "contextual", "non_contextual"}
    assert set(comparison["contextual"]["metrics"]) == {"recall_at_5", "recall_at_12", "mrr"}
    assert len(comparison["contextual"]["cases"]) == len(comparison["non_contextual"]["cases"])
    assert comparison["contextual"]["cases"]
    assert (tmp_path / "rag_evaluation.json").is_file()
    assert (tmp_path / "rag_evaluation.md").is_file()
    if result["conclusion"].startswith("Advanced RAG beat"):
        assert result["test"]["advanced"]["metrics"]["citation_completeness"] >= result["test"]["baseline"]["metrics"]["citation_completeness"]


@pytest.mark.asyncio
async def test_the_parameter_search_does_not_depend_on_how_fast_the_machine_was(tmp_path) -> None:
    """Two runs of the same script must select the same parameters.

    The tuner ranked trials on quality and broke ties on measured wall-clock
    latency. The quality terms tie on most trials, so the tiebreaker decided,
    and it is a property of the host rather than the pipeline: consecutive runs
    picked different parameters and reported different test numbers. A result
    that moves when nothing changed cannot support a comparison, in either
    direction.
    """
    first = await evaluate(tmp_path / "first")
    second = await evaluate(tmp_path / "second")

    assert first["selected_parameters"] == second["selected_parameters"]

    for arm in ("baseline", "advanced"):
        left = first["test"][arm]["metrics"]
        right = second["test"][arm]["metrics"]
        # Latency is the one metric allowed to differ - it is the wall clock.
        moved = {
            key: (left[key], right[key])
            for key in left
            if not key.startswith("average_latency") and left[key] != right[key]
        }
        assert not moved, f"{arm} metrics moved between identical runs: {moved}"
