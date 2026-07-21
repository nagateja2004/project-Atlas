import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base, Document, Equipment, ImpactEvent, ScheduleTask


def test_csv_supply_chain_risk_boundaries_and_impact_events(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'supply-workflow.db'}")

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        with TestClient(app) as client:
            app.state.session_factory = sessions
            project = client.post("/projects", json={"name": "Supply workflow"}).json()
            other = client.post("/projects", json={"name": "Other project"}).json()
            project_id = uuid.UUID(project["id"])

            async def seed() -> None:
                async with sessions() as session:
                    schedule = Document(
                        project_id=project_id,
                        filename="schedule.csv",
                        storage_path=str(tmp_path / "schedule.csv"),
                        document_type="schedule",
                        status="completed",
                        content_sha256="f" * 64,
                        mime_type="text/csv",
                        size_bytes=1,
                        metadata_json={},
                    )
                    session.add(schedule)
                    await session.flush()
                    for equipment_id, task_id, available_float in (
                        ("UPS-01", "DEL-UPS", 2),
                        ("CRAC-1", "DEL-CRAC", 5),
                        ("SWGR-A", "DEL-SWGR", 3),
                    ):
                        session.add(Equipment(project_id=project_id, equipment_id=equipment_id, name=equipment_id))
                        session.add(ScheduleTask(
                            project_id=project_id,
                            equipment_id=equipment_id,
                            document_id=schedule.id,
                            task_id=task_id,
                            name=f"{equipment_id} delivery milestone",
                            status="open",
                            dependencies=[],
                            available_float_days=available_float,
                            citation={},
                        ))
                    await session.commit()

            asyncio.run(seed())
            csv_data = "\n".join([
                "equipment_id,vendor,planned_date,current_eta,required_on_site_date,status,location",
                "UPS-01,Apex Power,2026-08-10,2026-08-10,2026-08-12,on_track,Singapore",
                "CRAC-1,Polar Air,2026-08-10,2026-08-15,2026-08-12,delayed,Osaka",
                "SWGR-A,Grid Point,2026-08-10,2026-09-10,2026-08-12,critical,Hamburg",
            ])
            imported = client.post(
                f"/projects/{project['id']}/supply-chain/import",
                files={"file": ("shipments.csv", csv_data, "text/csv")},
            )
            assert imported.status_code == 201, imported.text
            by_equipment = {item["equipment_id"]: item for item in imported.json()["assessments"]}

            assert by_equipment["UPS-01"]["eta_variance_days"] == 0
            assert by_equipment["UPS-01"]["schedule_exposure_days"] == 0
            assert by_equipment["UPS-01"]["severity"] == "on_track"
            assert by_equipment["UPS-01"]["first_alert_at"] is None

            assert by_equipment["CRAC-1"]["eta_variance_days"] == 5
            assert by_equipment["CRAC-1"]["available_float_days"] == 5
            assert by_equipment["CRAC-1"]["schedule_exposure_days"] == 0
            assert by_equipment["CRAC-1"]["severity"] == "medium"
            assert by_equipment["CRAC-1"]["affected_task"] == "DEL-CRAC"

            critical = by_equipment["SWGR-A"]
            assert critical["eta_variance_days"] == 31
            assert critical["schedule_exposure_days"] == 26
            assert critical["severity"] == "critical"
            assert critical["affected_task"] == "DEL-SWGR"
            assert critical["alert_lead_time_days"] is not None
            assert critical["impact_event_id"] is not None

            alerts = client.get(f"/projects/{project['id']}/supply-chain/alerts").json()
            assert {item["equipment_id"] for item in alerts} == {"CRAC-1", "SWGR-A"}
            timeline = client.get(
                f"/projects/{project['id']}/supply-chain/shipments/{critical['shipment_id']}/timeline"
            ).json()
            assert [item["event_type"] for item in timeline["events"]] == ["CSV_IMPORTED", "RISK_ALERT"]
            assert client.get(f"/projects/{other['id']}/supply-chain/assessments").json() == []
            assert client.get(
                f"/projects/{other['id']}/supply-chain/shipments/{critical['shipment_id']}/timeline"
            ).status_code == 404

            async def delivery_events() -> list[ImpactEvent]:
                async with sessions() as session:
                    return list((await session.scalars(select(ImpactEvent).where(
                        ImpactEvent.project_id == project_id,
                        ImpactEvent.type == "DELIVERY_RISK",
                    ))).all())

            assert {item.equipment_id for item in asyncio.run(delivery_events())} == {"CRAC-1", "SWGR-A"}
    finally:
        asyncio.run(engine.dispose())
