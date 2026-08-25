"""A mean over one case is that case, and reads like a score.

The schedule evaluation reported `mean_absolute_prediction_error_days` over a
single planted risk, and the supply-chain evaluation reported
`mean_alert_latency_minutes` over two events that were both fast and both on the
tier-1 supplier. Neither number could move, so neither number said anything -
and both looked like measurements.

These tests hold the two things that fix required: enough cases that one of them
cannot decide the figure, and the spread reported next to the mean.
"""

import json
from pathlib import Path

import pytest

from evaluation.run_all import _distribution

DATASET = Path("data/synthetic_epc")


# ── the statistic ───────────────────────────────────────────────────────────


def test_a_distribution_reports_the_ends_not_just_the_middle() -> None:
    result = _distribution([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    assert result["n"] == 10
    assert result["min"] == 1
    assert result["max"] == 10
    assert result["median"] == 6
    assert result["min"] <= result["p25"] <= result["median"] <= result["p75"] <= result["p90"] <= result["max"]


def test_a_single_value_is_reported_as_itself_at_every_point() -> None:
    """Honest degenerate case: one sample has no spread to describe."""
    result = _distribution([7])

    assert result == {"n": 1, "min": 7.0, "p25": 7.0, "median": 7.0, "p75": 7.0, "p90": 7.0, "max": 7.0}


def test_an_empty_sample_produces_nothing_rather_than_a_zero() -> None:
    """A zero would read as a measured result. There is no measurement."""
    assert _distribution([]) == {}


def test_order_of_the_input_does_not_change_the_result() -> None:
    assert _distribution([9, 1, 5, 3]) == _distribution([1, 3, 5, 9])


def test_every_reported_point_is_a_value_that_actually_occurred() -> None:
    """No interpolation: on a sample this size a fractional figure would claim
    precision the data does not carry."""
    sample = [2, 4, 40, 400]
    result = _distribution(sample)

    for key in ("min", "p25", "median", "p75", "p90", "max"):
        assert result[key] in {float(item) for item in sample}, key


# ── the datasets those statistics run on ────────────────────────────────────


def test_the_schedule_set_has_enough_cases_to_show_a_spread() -> None:
    truth = json.loads((DATASET / "ground_truth.json").read_text(encoding="utf-8"))
    risks = truth["expected_schedule_risks"]

    assert len(risks) >= 8, "a prediction-error mean over one case is that case"
    # More than one analysis date, or every case shares a lead time and the
    # lead-time distribution collapses to a single point.
    assert len({str(item["analysis_date"]) for item in risks}) >= 2
    assert len({item["task_id"] for item in risks}) >= 4


def test_every_schedule_case_names_a_row_of_the_schedule_it_came_from() -> None:
    """The actuals are not invented: each is a `delay_days` value in the CSV."""
    truth = json.loads((DATASET / "ground_truth.json").read_text(encoding="utf-8"))
    schedule = (DATASET / "schedules" / "atlas_demo_schedule.csv").read_text(encoding="utf-8")
    rows = {
        line.split(",")[2]: line.split(",")
        for line in schedule.strip().splitlines()[1:]
    }

    for item in truth["expected_schedule_risks"]:
        task_id = item["task_id"]
        assert task_id in rows, f"{task_id} is not in the schedule"
        recorded = int(rows[task_id][-2])
        assert item["forecast_delay_days"] == recorded, (
            f"{task_id} ground truth says {item['forecast_delay_days']} days, "
            f"the schedule row records {recorded}"
        )


def test_the_alert_set_is_not_made_only_of_fast_alerts_on_failures() -> None:
    """A timeliness figure computed over hand-picked good cases is a selection.

    The set must contain a slow alert, an event that resolved without delay, and
    signals originating below tier 1 - the case the feature exists to catch.
    """
    from datetime import datetime

    data = json.loads((DATASET / "supply_chain" / "shipments.json").read_text(encoding="utf-8"))
    events = [event for shipment in data["shipments"] for event in shipment["risk_events"]]

    def latency(event: dict) -> int:
        stamp = lambda key: datetime.fromisoformat(event[key].replace("Z", "+00:00"))
        return int((stamp("alert_generated_at") - stamp("occurred_at")).total_seconds() // 60)

    assert len(events) >= 6
    assert max(latency(event) for event in events) > 120, "no slow alert in the set"
    assert any(event["forecast_delay_days"] == 0 for event in events), "no event that resolved cleanly"
    assert any("tier3" in event["event_type"] for event in events), "no sub-tier signal"
    assert all(latency(event) >= 0 for event in events)


def test_every_shipment_with_a_forecast_slip_explains_it_with_an_event() -> None:
    """CT-A carried a three-day slip and no event saying why."""
    data = json.loads((DATASET / "supply_chain" / "shipments.json").read_text(encoding="utf-8"))

    for shipment in data["shipments"]:
        slipped = shipment["forecast_arrival"] > shipment["planned_arrival"]
        if slipped:
            assert shipment["risk_events"], f"{shipment['reference']} slipped with no recorded cause"


@pytest.mark.parametrize("reference", ["SYN-SHP-001", "SYN-SHP-004"])
def test_a_disruption_is_recorded_as_a_sequence(reference: str) -> None:
    """One event is an outcome; the sequence is what could have been caught."""
    data = json.loads((DATASET / "supply_chain" / "shipments.json").read_text(encoding="utf-8"))
    shipment = next(item for item in data["shipments"] if item["reference"] == reference)
    events = shipment["risk_events"]

    assert len(events) >= 2
    stamps = [event["occurred_at"] for event in events]
    assert stamps == sorted(stamps), "events are not in the order they happened"
