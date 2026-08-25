"""Weather and workforce are read off a document, not handed to the analysis.

Both used to arrive as scenario knobs. A caller passed
`weather_impact_days={"T-160": 4}` and `workforce_availability=0.8`, the
schedule added the days, and the explanation read "synthetic weather impact
adds 4 days". Nothing anywhere said where the 4 came from - in a product whose
whole claim is that every figure points back at a document, those two were the
figures that pointed at nothing.

These tests cover the derivation, the arithmetic that keeps a lost day from
being charged twice, and the provenance the reviewer is shown.
"""

import uuid
from datetime import date
from pathlib import Path

import pytest

from app.ingestion import IngestionError
from app.models import Document
from app.schedule import (
    ScheduleScenario,
    ScheduleTask,
    conditions_citation,
    load_site_conditions,
    mitigation_inputs,
    scenario_effect,
)

HEADER = (
    "project_id,data_classification,record_date,task_id,task_name,weather_condition,"
    "lost_workday,planned_crew,present_crew,absence_reason,notes\n"
)


def write_log(tmp_path: Path, rows: list[str], name: str = "site_conditions_log.csv") -> Path:
    path = tmp_path / name
    path.write_text(HEADER + "".join(rows), encoding="utf-8")
    return path


def row(day: str, task: str, *, lost: bool, planned: int, present: int, reason: str = "") -> str:
    condition = "monsoon rain" if lost else "fair"
    return (
        f"p,SYNTHETIC,{day},{task},Task {task},{condition},"
        f"{'true' if lost else 'false'},{planned},{present},{reason},note\n"
    )


def task(task_id: str = "T-1", *, category: str = "Construction") -> ScheduleTask:
    return ScheduleTask(
        task_id=task_id,
        name=f"Task {task_id}",
        dependencies=[],
        category=category,
        is_delivery_milestone=False,
        baseline_start=date(2026, 6, 1),
        baseline_finish=date(2026, 6, 11),
        forecast_start=date(2026, 6, 1),
        forecast_finish=date(2026, 6, 11),
        procurement_status="in_progress",
        reported_delay_days=0,
        equipment_id=None,
        notes="",
    )


def document(path: Path) -> Document:
    record = Document()
    record.id = uuid.uuid4()
    record.document_type = "site_conditions"
    record.filename = path.name
    record.storage_path = str(path)
    return record


# ── derivation ──────────────────────────────────────────────────────────────


def test_weather_days_are_counted_from_the_rows_flagged_as_lost(tmp_path: Path) -> None:
    path = write_log(
        tmp_path,
        [
            row("2026-06-01", "T-1", lost=True, planned=8, present=0),
            row("2026-06-02", "T-1", lost=False, planned=8, present=8),
            row("2026-06-03", "T-1", lost=True, planned=8, present=0),
            row("2026-06-04", "T-2", lost=True, planned=4, present=0),
        ],
    )
    conditions = load_site_conditions(path)

    assert conditions.weather_impact_days == {"T-1": 2, "T-2": 1}
    assert conditions.weather_dates["T-1"] == [date(2026, 6, 1), date(2026, 6, 3)]
    assert conditions.record_count == 4
    assert (conditions.window_start, conditions.window_end) == (date(2026, 6, 1), date(2026, 6, 4))


def test_a_weather_day_is_not_also_charged_as_a_crew_shortfall(tmp_path: Path) -> None:
    """The arithmetic that matters.

    A weather stand-down shows zero crew present. Counting those rows in
    availability would charge the same lost day twice - once as a weather day
    added to the duration, and again as reduced productivity stretching it. Only
    days the crew could actually have worked count.
    """
    path = write_log(
        tmp_path,
        [
            row("2026-06-01", "T-1", lost=True, planned=10, present=0),
            row("2026-06-02", "T-1", lost=False, planned=10, present=8, reason="reported sick"),
        ],
    )
    conditions = load_site_conditions(path)

    assert conditions.workforce_availability == 0.8  # 8/10, not 8/20
    assert conditions.workforce_planned_crew_days == 10
    assert conditions.workforce_present_crew_days == 8
    assert conditions.workforce_absence_reasons == ["reported sick"]


def test_a_fully_manned_log_reports_full_availability(tmp_path: Path) -> None:
    path = write_log(tmp_path, [row("2026-06-02", "T-1", lost=False, planned=6, present=6)])
    assert load_site_conditions(path).workforce_availability == 1.0


# ── what the analysis does with it ──────────────────────────────────────────


def test_evidenced_conditions_replace_the_caller_supplied_numbers(tmp_path: Path) -> None:
    path = write_log(
        tmp_path,
        [
            row("2026-06-01", "T-1", lost=True, planned=8, present=0),
            row("2026-06-02", "T-1", lost=True, planned=8, present=0),
            row("2026-06-03", "T-1", lost=False, planned=8, present=8),
        ],
    )
    conditions = load_site_conditions(path)
    # A caller asking for nine weather days does not get nine.
    scenario = ScheduleScenario(weather_impact_days={"T-1": 9}, workforce_availability=0.5)

    evidenced, _ = scenario_effect(task(), scenario, conditions)
    asserted, _ = scenario_effect(task(), scenario)

    assert evidenced == 2
    assert asserted == 19  # 9 weather days plus 10 lost to the invented 50% crew


def test_the_cause_names_the_document_and_the_dates(tmp_path: Path) -> None:
    path = write_log(
        tmp_path,
        [
            row("2026-06-01", "T-1", lost=True, planned=8, present=0),
            row("2026-06-02", "T-1", lost=False, planned=8, present=8),
        ],
    )
    conditions = load_site_conditions(path)

    _, cause = scenario_effect(task(), ScheduleScenario(), conditions)

    assert "site_conditions_log.csv" in cause
    assert "2026-06-01" in cause
    assert "synthetic weather impact" not in cause


def test_without_a_log_the_output_says_the_figure_was_supplied(tmp_path: Path) -> None:
    scenario = ScheduleScenario(weather_impact_days={"T-1": 3})
    inputs = mitigation_inputs(task(), scenario)

    assert inputs["weather_and_workforce_source"] == "caller-supplied scenario input"
    assert inputs["weather_dates"] == []
    assert inputs["weather_impact_days"] == 3


def test_with_a_log_the_output_names_its_source_and_dates(tmp_path: Path) -> None:
    path = write_log(tmp_path, [row("2026-06-01", "T-1", lost=True, planned=8, present=0)])
    conditions = load_site_conditions(path)

    inputs = mitigation_inputs(task(), ScheduleScenario(), conditions)

    assert "site_conditions_log.csv" in inputs["weather_and_workforce_source"]
    assert "1 daily records" in inputs["weather_and_workforce_source"]
    assert inputs["weather_dates"] == ["2026-06-01"]


# ── provenance ──────────────────────────────────────────────────────────────


def test_the_log_is_cited_when_it_moved_the_task(tmp_path: Path) -> None:
    path = write_log(
        tmp_path,
        [
            row("2026-06-01", "T-1", lost=True, planned=8, present=0),
            row("2026-06-05", "T-1", lost=True, planned=8, present=0),
        ],
    )
    record = document(path)
    conditions = load_site_conditions(path, record)

    cited = conditions_citation(conditions, "T-1")

    assert cited is not None
    assert cited.document_id == record.id
    assert cited.filename == "site_conditions_log.csv"
    assert cited.section == "Lost workdays 2026-06-01 to 2026-06-05"


def test_no_citation_when_the_log_did_not_move_the_task(tmp_path: Path) -> None:
    """A fully manned task with no lost days has nothing in the log to point at."""
    path = write_log(tmp_path, [row("2026-06-01", "T-1", lost=False, planned=8, present=8)])
    conditions = load_site_conditions(path, document(path))

    assert conditions_citation(conditions, "T-2") is None


def test_a_log_read_off_disk_without_a_document_is_not_cited(tmp_path: Path) -> None:
    """No document id means no citation a reviewer could open. Better none."""
    path = write_log(tmp_path, [row("2026-06-01", "T-1", lost=True, planned=8, present=0)])
    assert conditions_citation(load_site_conditions(path), "T-1") is None


# ── refusing bad input ──────────────────────────────────────────────────────


def test_an_empty_log_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text(HEADER, encoding="utf-8")
    with pytest.raises(IngestionError):
        load_site_conditions(path)


@pytest.mark.parametrize(
    "bad",
    [
        "p,SYNTHETIC,not-a-date,T-1,Task,fair,false,8,8,,note\n",
        "p,SYNTHETIC,2026-06-01,T-1,Task,fair,false,eight,8,,note\n",
    ],
)
def test_a_malformed_row_is_rejected_rather_than_guessed(tmp_path: Path, bad: str) -> None:
    with pytest.raises(IngestionError):
        load_site_conditions(write_log(tmp_path, [bad]))


# ── the shipped corpus ──────────────────────────────────────────────────────


def test_the_synthetic_log_matches_the_schedule_it_describes() -> None:
    """Guards the corpus: the log must reference tasks the schedule contains."""
    conditions = load_site_conditions(
        Path("data/synthetic_epc/site_conditions/site_conditions_log.csv")
    )
    schedule = Path("data/synthetic_epc/schedules/atlas_demo_schedule.csv").read_text(encoding="utf-8")

    assert conditions.record_count == 46
    for task_id in conditions.weather_impact_days:
        assert f",{task_id}," in schedule, f"{task_id} is not in the schedule"
    assert 0 < conditions.workforce_availability < 1


# ── getting the log into a project ──────────────────────────────────────────


def test_the_log_can_be_uploaded_at_all() -> None:
    """Without this the analysis endpoint could never be used.

    Uploads were gated on `document_type != "schedule" and suffix == ".csv"`,
    so a site conditions CSV was rejected outright - and the schedule endpoint
    resolves the log by document id, meaning the feature had no way in.
    """
    from app.config import Settings
    from app.ingestion import extract_document, validate_upload

    path = Path("data/synthetic_epc/site_conditions/site_conditions_log.csv")
    validate_upload(path.name, "site_conditions", path.stat().st_size, Settings())

    extracted = extract_document(path, Settings())
    assert len(extracted.pages) == 46
    assert extracted.pages[0].section.startswith("Task ")


@pytest.mark.parametrize(
    ("filename", "document_type"),
    [
        ("notes.csv", "specification"),  # a CSV still needs a row-keyed type
        ("log.md", "site_conditions"),  # and this type still needs a CSV
    ],
)
def test_widening_the_csv_gate_did_not_open_it(filename: str, document_type: str) -> None:
    from app.config import Settings
    from app.ingestion import validate_upload

    with pytest.raises(IngestionError):
        validate_upload(filename, document_type, 100, Settings())


def test_the_demo_seed_includes_the_log() -> None:
    """Seeded, or the deployed demo cannot show an evidenced weather day."""
    from scripts.seed_demo import LAYOUT

    assert ("site_conditions", "*.csv", "site_conditions") in LAYOUT
