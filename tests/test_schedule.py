import asyncio
import hashlib
import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.ingestion import IngestionError
from app.main import app
from app.models import Base, Document, Project
from app.schedule import ScheduleScenario, ScheduleService, calculate_cpm, load_schedule, validate_dependencies

DATASET = Path(__file__).parents[1] / "data" / "synthetic_epc"
SCHEDULE = DATASET / "schedules" / "atlas_demo_schedule.csv"


def config(tmp_path: Path) -> Settings:
    return Settings(upload_dir=str(tmp_path / "uploads"), graph_dir=str(tmp_path / "graphs"))


def schedule_document(project_id: uuid.UUID) -> Document:
    return Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename=SCHEDULE.name,
        storage_path=str(SCHEDULE),
        document_type="schedule",
        status="completed",
        content_sha256=hashlib.sha256(SCHEDULE.read_bytes()).hexdigest(),
        mime_type="text/csv",
        size_bytes=SCHEDULE.stat().st_size,
        metadata_json={},
    )


@pytest.mark.asyncio
async def test_synthetic_schedule_matches_ground_truth_risk(tmp_path: Path) -> None:
    project_id = uuid.uuid4()
    analysis = await ScheduleService(config(tmp_path)).analyze(
        schedule_document(project_id), ScheduleScenario(analysis_date="2026-04-15")
    )
    truth = json.loads((DATASET / "ground_truth.json").read_text())["expected_schedule_risks"][0]
    risk = next(item for item in analysis.risks if item.affected_task == truth["task_id"])

    assert risk.predicted_delay_days == truth["forecast_delay_days"]
    assert risk.severity == truth["risk_level"]
    assert risk.dependency_chain[-1].startswith("T-140")
    assert any(item.startswith("T-120") for item in risk.dependency_chain)
    assert risk.risk_lead_time_days == 35
    assert risk.evidence[0].filename == SCHEDULE.name
    assert "scenario-based" in risk.analysis_type
    timing = next(item for item in analysis.snapshot.tasks if item.task_id == "T-180")
    assert timing.critical is True
    assert timing.earliest_finish == timing.latest_finish
    assert analysis.snapshot.affected_completion_date >= analysis.snapshot.baseline_completion_date


def test_dependency_validation_rejects_missing_and_cyclic_tasks() -> None:
    valid = load_schedule(SCHEDULE)
    timings = calculate_cpm(valid, validate_dependencies(valid))
    assert timings["T-180"].total_float_days == 0

    tasks = load_schedule(SCHEDULE)
    tasks["T-100"].dependencies = ["MISSING"]
    with pytest.raises(IngestionError, match="missing dependency"):
        validate_dependencies(tasks)

    tasks = load_schedule(SCHEDULE)
    tasks["T-100"].dependencies = ["T-180"]
    with pytest.raises(IngestionError, match="cycle"):
        validate_dependencies(tasks)


@pytest.mark.asyncio
async def test_weather_and_workforce_scenarios_propagate_additional_delay(tmp_path: Path) -> None:
    service, project_id = ScheduleService(config(tmp_path)), uuid.uuid4()
    base = await service.analyze(schedule_document(project_id), ScheduleScenario(analysis_date="2026-04-15"))
    constrained = await service.analyze(
        schedule_document(project_id),
        ScheduleScenario(
            analysis_date="2026-04-15",
            procurement={"T-120": {"status": "delayed", "lead_time_days": 130}},
            workforce_availability=0.5,
            weather_impact_days={"T-160": 2},
        ),
    )
    base_delay = next(risk.predicted_delay_days for risk in base.risks if risk.affected_task == "T-160")
    constrained_risk = next(risk for risk in constrained.risks if risk.affected_task == "T-160")
    procurement_risk = next(risk for risk in constrained.risks if risk.affected_task == "T-120")
    assert constrained_risk.predicted_delay_days > base_delay
    assert "weather" in constrained_risk.root_cause or "shortage" in constrained_risk.root_cause
    assert "lead time" in procurement_risk.root_cause
    assert any("Workforce availability" in item for item in constrained_risk.assumptions)


@pytest.mark.asyncio
async def test_delivery_noncritical_critical_and_mitigation_recalculation(tmp_path: Path) -> None:
    service, project_id = ScheduleService(config(tmp_path)), uuid.uuid4()
    document = schedule_document(project_id)
    delivery = await service.analyze(
        document,
        ScheduleScenario(analysis_date="2026-04-15", equipment_delivery_dates={"T-220": "2026-06-01"}),
    )
    delivery_risk = next(risk for risk in delivery.risks if risk.affected_task == "T-230")
    assert delivery_risk.affected_completion_date > date.fromisoformat("2026-06-08")
    assert delivery_risk.affected_equipment == ["UPS-A"]
    assert "equipment delivery date" in delivery_risk.root_cause

    noncritical = await service.analyze(
        document,
        ScheduleScenario(analysis_date="2026-04-15", procurement={"T-210": {"delay_days": 5}}),
    )
    noncritical_risk = next(risk for risk in noncritical.risks if risk.affected_task == "T-210")
    assert noncritical_risk.predicted_delay_days <= noncritical_risk.available_float_days
    assert noncritical_risk.severity != "critical"

    base = await service.analyze(document, ScheduleScenario(analysis_date="2026-04-15"))
    mitigated = await service.analyze(
        document,
        ScheduleScenario(analysis_date="2026-04-15", mitigation_recovery_days={"T-120": 10}),
    )
    base_critical = next(risk for risk in base.risks if risk.affected_task == "T-180")
    mitigated_critical = next(risk for risk in mitigated.risks if risk.affected_task == "T-180")
    assert base_critical.severity == "critical"
    assert mitigated_critical.predicted_delay_days == base_critical.predicted_delay_days - 10
    assert mitigated_critical.mitigation_inputs["recovery_days"] == 10


def test_schedule_analysis_api_returns_scenario_based_evidence(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'schedule-api.db'}")

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    try:
        with TestClient(app) as client:
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app.state.schedule_service = ScheduleService(config(tmp_path))
            project = client.post("/projects", json={"name": "Schedule API test"}).json()
            project_id = uuid.UUID(project["id"])

            async def seed_schedule() -> uuid.UUID:
                async with app.state.session_factory() as session:
                    document = schedule_document(project_id)
                    session.add(document)
                    await session.commit()
                    return document.id

            document_id = asyncio.run(seed_schedule())
            response = client.post(
                f"/projects/{project['id']}/schedule/analysis",
                json={"schedule_document_id": str(document_id), "analysis_date": "2026-04-15"},
            )
            assert response.status_code == 200
            risk = next(item for item in response.json()["risks"] if item["affected_task"] == "T-140")
            assert risk["severity"] == "critical"
            assert risk["evidence"][0]["section"] == "Task T-120"
            snapshots = client.get(f"/projects/{project['id']}/schedule/snapshots")
            assert snapshots.status_code == 200
            assert snapshots.json()[0]["snapshot_id"] == response.json()["snapshot"]["snapshot_id"]
            other_project = client.post("/projects", json={"name": "Other project"}).json()
            assert client.get(f"/projects/{other_project['id']}/schedule/snapshots").json() == []
    finally:
        asyncio.run(engine.dispose())
