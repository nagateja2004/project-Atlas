import json

import pytest

from evaluation.run_all import EvaluationInputError, evaluate_all


@pytest.mark.asyncio
async def test_run_all_writes_complete_reports_without_inventing_manual_effort(tmp_path) -> None:
    report = await evaluate_all(output_dir=tmp_path)

    assert set(report["rag"]) == {"baseline", "advanced"}
    assert {"recall_at_5", "recall_at_12", "mrr", "citation_precision"} <= set(report["rag"]["advanced"])
    assert report["compliance"]["true_positive"] == 6
    assert report["schedule"]["cases"][0]["prediction_error_days"] == 0
    assert report["supply_chain"]["shipments_represented"] == 5
    assert report["commissioning"]["total_steps"] == 21
    assert report["commissioning"]["ncr_correctness"] is True
    assert report["manual_effort"]["status"] == "NOT_MEASURED"
    assert report["manual_effort"]["hours_saved"] is None
    assert json.loads((tmp_path / "latest.json").read_text()) == report
    assert (tmp_path / "latest.md").is_file()


@pytest.mark.asyncio
async def test_run_all_fails_when_required_ground_truth_is_missing(tmp_path) -> None:
    missing = tmp_path / "missing-ground-truth.json"
    with pytest.raises(EvaluationInputError, match="Required evaluation input is missing"):
        await evaluate_all(output_dir=tmp_path, ground_truth_path=missing)
