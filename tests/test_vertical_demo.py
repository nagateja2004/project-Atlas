import asyncio
import hashlib
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commissioning import CommissioningService
from app.compliance import ComplianceService
from app.config import Settings
from app.main import app
from app.models import (
    Base,
    CommissioningStep,
    ComplianceFinding,
    Document,
    Equipment,
    ImpactEvent,
    MitigationScenario,
    ScheduleTask,
    ShipmentEvent,
)

DATASET = Path(__file__).parents[1] / "data" / "synthetic_epc"


def _document(project_id, path: Path, document_type: str, equipment_id: str | None) -> Document:
    return Document(
        project_id=project_id,
        equipment_id=equipment_id,
        filename=path.name,
        storage_path=str(path),
        document_type=document_type,
        status="completed",
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        mime_type="text/csv" if path.suffix == ".csv" else "text/markdown",
        size_bytes=path.stat().st_size,
        metadata_json={"approval_status": "approved", "revision": "1", "equipment_tags": [equipment_id] if equipment_id else []},
    )


def test_switchgear_vertical_scenario_is_complete_and_idempotent(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'vertical.db'}")
    sqlalchemy_event.listen(
        engine.sync_engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = TestClient(app)
    try:
        app.state.session_factory = sessions
        settings = Settings(gemini_api_key=None, auto_create_schema=False)
        app.state.compliance_service = ComplianceService(settings)
        app.state.commissioning_service = CommissioningService(settings)
        project = client.post("/projects", json={"name": "Switchgear vertical demo"}).json()
        project_id = uuid.UUID(project["id"])

        async def seed_documents() -> None:
            async with sessions() as session:
                specification = _document(project_id, DATASET / "specifications" / "Switchgear_Specification.md", "specification", "SWGR-A")
                submittal = _document(project_id, DATASET / "submittals" / "SWGR-002_ArcLine_SWGR-A.md", "submittal", "SWGR-A")
                schedule = _document(project_id, DATASET / "schedules" / "atlas_demo_schedule.csv", "schedule", None)
                procedure = _document(project_id, DATASET / "commissioning" / "Switchgear_Procedure_Template.md", "commissioning_record", "SWGR-A")
                session.add_all([specification, submittal, schedule, procedure, Equipment(project_id=project_id, equipment_id="SWGR-A", name="Main switchgear", equipment_type="Switchgear")])
                await session.flush()
                session.add_all([
                    ScheduleTask(project_id=project_id, equipment_id="SWGR-A", document_id=schedule.id, task_id="T-140", name="SWGR-A delivery milestone", status="critical", dependencies=["T-130"], planned_finish=None, forecast_finish=None, citation={}),
                    ScheduleTask(project_id=project_id, equipment_id="SWGR-A", document_id=schedule.id, task_id="T-160", name="Install SWGR-A", status="not_started", dependencies=["T-140"], planned_finish=None, forecast_finish=None, citation={}),
                    *(CommissioningStep(project_id=project_id, equipment_id="SWGR-A", procedure_document_id=procedure.id, step_index=index, prerequisite=[], instruction=f"Synthetic step {index}", acceptance_criterion="Verified", evidence=["Synthetic procedure"], status="PASS", citation={}) for index in (1, 2, 3)),
                ])
                await session.commit()

        asyncio.run(seed_documents())
        first = client.post(f"/projects/{project_id}/demo/vertical-scenario")
        second = client.post(f"/projects/{project_id}/demo/vertical-scenario")
        assert first.status_code == second.status_code == 200, first.text
        result = second.json()
        assert result["synthetic_data"] is True
        assert result["compliance_finding"]["parameter"] == "interrupting_rating"
        assert result["compliance_finding"]["status"] == "NON_COMPLIANT"
        assert result["compliance_finding"]["specification_citation"]["page"] == 2
        assert result["compliance_finding"]["submittal_citation"]["page"] == 1
        assert [item["type"] for item in result["impact_chain"]["events"]] == [
            "SPEC_DEVIATION", "VENDOR_RESUBMISSION", "DELIVERY_RISK", "SCHEDULE_IMPACT", "COMMISSIONING_IMPACT",
        ]
        assert result["shipment_risk"]["eta_variance_days"] == 35
        assert result["shipment_risk"]["available_float_days"] == 7
        assert result["shipment_risk"]["schedule_exposure_days"] == 28
        assert result["commissioning_readiness_after"] < result["commissioning_readiness_before"]
        assert result["commissioning_readiness"]["score"] == result["commissioning_readiness_after"]
        assert result["mitigation"]["baseline_exposure_days"] == 28
        assert result["recommended_mitigation"]["critical_path_exposure_days"] < 28
        assert result["recommended_mitigation"]["projected_delay_days"] < result["mitigation"]["baseline_delay_days"]
        assert result["digital_thread"]["current_specification"]["filename"] == "Switchgear_Specification.md"
        assert result["digital_thread"]["current_submittal"]["filename"] == "SWGR-002_ArcLine_SWGR-A.md"

        summary = client.get(f"/projects/{project_id}/executive-summary").json()
        assert summary["critical_deviations"] == 2
        assert summary["equipment_at_risk"] == 1
        assert summary["schedule_exposure_days"] == 28
        assert summary["recommended_mitigation"] == "Expedite shipment"
        assert summary["evidence_confidence"] == 0.985

        async def counts() -> tuple[int, int, int, int]:
            async with sessions() as session:
                values = []
                for model in (ImpactEvent, MitigationScenario, ShipmentEvent, ComplianceFinding):
                    values.append(await session.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)))
                return tuple(values)

        assert asyncio.run(counts()) == (5, 3, 1, 2)
    finally:
        client.close()
        asyncio.run(engine.dispose())
