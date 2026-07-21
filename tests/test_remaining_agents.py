import asyncio
import hashlib
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.commissioning import CommissioningService, EngineerObservation
from app.config import Settings
from app.main import app
from app.models import AuditEvent, Base, Document, NonConformance, Project
from app.procurement import ProcurementItemInput, ProcurementRiskService

DATASET = Path(__file__).parents[1] / "data" / "synthetic_epc"
UPS_PROCEDURE = DATASET / "commissioning" / "UPS_Procedure_Template.md"


def config(tmp_path: Path) -> Settings:
    return Settings(upload_dir=str(tmp_path / "uploads"), graph_dir=str(tmp_path / "graphs"))


def procedure_document(project_id: uuid.UUID) -> Document:
    return Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename=UPS_PROCEDURE.name,
        storage_path=str(UPS_PROCEDURE),
        document_type="commissioning_record",
        status="completed",
        content_sha256=hashlib.sha256(UPS_PROCEDURE.read_bytes()).hexdigest(),
        mime_type="text/markdown",
        size_bytes=UPS_PROCEDURE.stat().st_size,
        metadata_json={},
    )


@pytest.mark.asyncio
async def test_commissioning_records_failed_acceptance_with_coverage(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commissioning.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            project = Project(name="Commissioning test")
            session.add(project)
            await session.flush()
            document = procedure_document(project.id)
            session.add(document)
            await session.commit()

            service = CommissioningService(config(tmp_path))
            procedure = service.procedure(document)
            battery_step = next(step for step in procedure.steps if "15-minute design autonomy" in step.instruction)
            result = await service.record(
                session, document, [EngineerObservation(step_index=battery_step.index, observation="Battery autonomy demonstrated for 10 minutes.")]
            )

            assert result.status == "fail"
            assert result.coverage_percent == round(100 / len(procedure.steps), 1)
            assert result.non_conformances[0].step_index == battery_step.index
            assert result.non_conformances[0].citation.page == 2
            assert len((await session.scalars(select(NonConformance))).all()) == 1
            assert (await session.scalars(select(AuditEvent))).one().event_type == "commissioning_test_recorded"
    finally:
        await engine.dispose()


def test_procurement_dashboard_is_mock_only_and_does_not_invent_tracking() -> None:
    dashboard = ProcurementRiskService().dashboard(
        [
            ProcurementItemInput(
                equipment_tag="SWGR-A",
                vendor="Synthetic Vendor",
                purchase_order_status="in_progress",
                planned_delivery="2026-05-20",
                forecast_delivery="2026-06-24",
                lead_time_days=120,
            ),
            ProcurementItemInput(
                equipment_tag="UPS-A",
                vendor="Synthetic Vendor",
                purchase_order_status="complete",
                planned_delivery="2026-04-10",
            ),
        ]
    )
    assert dashboard.mode == "demo_mock" and not dashboard.live_data_available
    assert dashboard.cards[0].delay_days == 35 and dashboard.cards[0].risk_level == "high"
    assert dashboard.cards[1].risk_level == "needs_live_data"
    assert all(item.status == "roadmap_unavailable" for item in dashboard.integrations)


def test_commissioning_and_procurement_apis_are_project_scoped(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agents-api.db'}")

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    try:
        with TestClient(app) as client:
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            app.state.commissioning_service = CommissioningService(config(tmp_path))
            project = client.post("/projects", json={"name": "Agent API test"}).json()
            project_id = uuid.UUID(project["id"])

            async def seed() -> uuid.UUID:
                async with app.state.session_factory() as session:
                    document = procedure_document(project_id)
                    session.add(document)
                    await session.commit()
                    return document.id

            procedure_id = asyncio.run(seed())
            procedure = client.get(f"/projects/{project['id']}/commissioning/procedures/{procedure_id}")
            assert procedure.status_code == 200
            response = client.post(
                f"/projects/{project['id']}/commissioning/records",
                json={"procedure_document_id": str(procedure_id), "observations": [{"step_index": 1, "observation": "Verified complete."}]},
            )
            assert response.status_code == 201
            record = client.get(f"/projects/{project['id']}/commissioning/records/{response.json()['id']}")
            assert record.status_code == 200 and record.json()["coverage_percent"] > 0
            dashboard = client.post(
                f"/projects/{project['id']}/procurement/dashboard",
                json={"items": [{"equipment_tag": "SWGR-A", "vendor": "Synthetic Vendor", "purchase_order_status": "in_progress", "planned_delivery": "2026-05-20"}]},
            )
            assert dashboard.status_code == 200
            assert dashboard.json()["live_data_available"] is False
    finally:
        asyncio.run(engine.dispose())
