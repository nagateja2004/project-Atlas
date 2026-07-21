import asyncio
import hashlib
import uuid
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import (
    AuditEvent,
    Base,
    CommissioningStep,
    Document,
    Equipment,
    MitigationScenario,
    Project,
    ScheduleTask,
    Shipment,
)

DATASET = Path(__file__).parents[1] / "data" / "synthetic_epc"


def _document(project_id, path, document_type, equipment_id="UPS-01") -> Document:
    return Document(
        id=uuid.uuid4(),
        project_id=project_id,
        equipment_id=equipment_id,
        filename=path.name,
        storage_path=str(path),
        document_type=document_type,
        status="completed",
        content_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        mime_type="text/csv" if path.suffix == ".csv" else "text/markdown",
        size_bytes=path.stat().st_size,
        metadata_json={"approval_status": "approved", "revision": "1"},
    )


def test_ups_01_impact_chain_end_to_end(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'impact-chain.db'}")

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    try:
        with TestClient(app) as client:
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            app.state.session_factory = sessions
            project = client.post("/projects", json={"name": "UPS-01 impact demo"}).json()
            project_id = uuid.UUID(project["id"])

            async def seed():
                async with sessions() as session:
                    specification = _document(
                        project_id, DATASET / "specifications" / "UPS_Specification.md", "specification"
                    )
                    submittal = _document(
                        project_id, DATASET / "submittals" / "UPS-002_VoltEdge_UPS-A.md", "submittal"
                    )
                    schedule = _document(
                        project_id,
                        DATASET / "schedules" / "atlas_demo_schedule.csv",
                        "schedule",
                        equipment_id=None,
                    )
                    procedure = _document(
                        project_id,
                        DATASET / "commissioning" / "UPS_Procedure_Template.md",
                        "commissioning_record",
                    )
                    equipment = Equipment(
                        project_id=project_id,
                        equipment_id="UPS-01",
                        name="UPS-01",
                        equipment_type="UPS",
                    )
                    session.add_all([specification, submittal, schedule, procedure, equipment])
                    await session.flush()
                    shipment = Shipment(
                        project_id=project_id,
                        equipment_id="UPS-01",
                        reference="UPS-01-REPLACEMENT",
                        status="delivered",
                        planned_delivery=date(2026, 4, 10),
                        forecast_delivery=date(2026, 4, 10),
                        evidence={
                            "synthetic_simulation": True,
                            "origin": "Synthetic UPS factory",
                            "destination": "Atlas demo site",
                            "supplier_tiers": [
                                {"tier": index, "supplier": f"Synthetic tier {index}", "location": "Demo"}
                                for index in (1, 2, 3)
                            ],
                            "milestones": [],
                            "schedule_task_id": "T-220",
                            "schedule_float_days": 56,
                            "critical_path": False,
                            "alternatives": [],
                        },
                    )
                    installation = ScheduleTask(
                        project_id=project_id,
                        equipment_id="UPS-01",
                        document_id=schedule.id,
                        task_id="INSTALL-UPS-01",
                        name="Install UPS-01",
                        status="complete",
                        dependencies=[],
                        citation={},
                    )
                    steps = [
                        CommissioningStep(
                            project_id=project_id,
                            equipment_id="UPS-01",
                            procedure_document_id=procedure.id,
                            step_index=index,
                            prerequisite=[],
                            instruction=f"Prerequisite {index}",
                            acceptance_criterion="Verified",
                            evidence=["Synthetic procedure"],
                            status="PASS",
                            citation={},
                        )
                        for index in (1, 2, 3)
                    ]
                    session.add_all([shipment, installation, *steps])
                    await session.commit()
                    return specification.id, submittal.id, schedule.id, shipment.id

            specification_id, submittal_id, schedule_id, shipment_id = asyncio.run(seed())
            compliance = client.post(
                f"/projects/{project_id}/compliance/checks",
                json={
                    "specification_document_id": str(specification_id),
                    "submittal_document_id": str(submittal_id),
                },
            )
            assert compliance.status_code == 200
            voltage = next(item for item in compliance.json()["findings"] if item["parameter"] == "voltage")
            assert voltage["status"] == "NON_COMPLIANT"

            started = client.post(
                f"/projects/{project_id}/impact-chains",
                json={
                    "compliance_finding_id": voltage["id"],
                    "shipment_id": str(shipment_id),
                    "schedule_document_id": str(schedule_id),
                    "replacement_lead_time_days": 60,
                    "replacement_cost": 100000,
                    "analysis_date": "2026-04-15",
                },
            )
            assert started.status_code == 201, started.text
            chain = started.json()
            assert chain["equipment_id"] == "UPS-01"
            assert chain["finding_parameter"] == "voltage"
            assert chain["finding_required_value"] == "480/277 V"
            assert chain["finding_observed_value"].startswith("415/240 V")
            assert chain["procurement"]["replacement_lead_time_days"] == 60
            assert chain["schedule"]["available_float_days"] == 56
            assert chain["schedule"]["predicted_delay_days"] == 60
            assert chain["schedule"]["critical_path_impact_days"] == 4
            assert chain["commissioning_readiness"]["score"] == 80
            assert len(chain["mitigation_scenarios"]) == 3
            assert [item["days_recovered"] for item in chain["mitigation_scenarios"]] == [15, 30, 10]
            assert [item["added_cost"] for item in chain["mitigation_scenarios"]] == [20000, 35000, 10000]
            assert chain["status"] == "AWAITING_HUMAN_DECISION"

            chosen = chain["mitigation_scenarios"][0]
            decided = client.post(
                f"/projects/{project_id}/impact-chains/{chain['chain_id']}/decision",
                json={"action": "APPROVE", "scenario_id": chosen["id"], "note": "Approved for demo."},
            )
            assert decided.status_code == 200, decided.text
            result = decided.json()
            assert result["status"] == "ACTION_CREATED"
            assert result["approved_action"]["action"] == "APPROVE"
            assert result["approved_action"]["created_record_id"] == chosen["id"]

            async def verify_persistence():
                async with sessions() as session:
                    scenarios = (await session.scalars(
                        select(MitigationScenario).where(MitigationScenario.project_id == project_id)
                    )).all()
                    events = (await session.scalars(
                        select(AuditEvent).where(AuditEvent.project_id == project_id)
                    )).all()
                    return scenarios, events

            scenarios, events = asyncio.run(verify_persistence())
            assert len(scenarios) == 3
            assert next(item for item in scenarios if str(item.id) == chosen["id"]).status == "approved"
            event_types = {item.event_type for item in events}
            assert {
                "compliance_finding_created",
                "impact_chain_awaiting_human_decision",
                "impact_action_created",
                "impact_chain_decided",
            } <= event_types
    finally:
        asyncio.run(engine.dispose())
