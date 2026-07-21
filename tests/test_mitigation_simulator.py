import asyncio
import uuid
from copy import deepcopy
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base, Document, Equipment, ImpactEvent, MitigationScenario, ScheduleTask, Shipment


def test_counterfactual_simulation_does_not_mutate_project_state(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'mitigations.db'}")

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        with TestClient(app) as client:
            app.state.session_factory = sessions
            project = client.post("/projects", json={"name": "Mitigation project"}).json()
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
                        content_sha256="a" * 64,
                        mime_type="text/csv",
                        size_bytes=1,
                        metadata_json={},
                    )
                    session.add_all([
                        schedule,
                        Equipment(project_id=project_id, equipment_id="SWGR-A", name="Switchgear A"),
                    ])
                    await session.flush()
                    session.add_all([
                        ScheduleTask(
                            project_id=project_id,
                            equipment_id="SWGR-A",
                            document_id=schedule.id,
                            task_id="DEL-SWGR",
                            name="SWGR-A delivery milestone",
                            status="open",
                            dependencies=[],
                            planned_finish=date(2026, 8, 12),
                            forecast_finish=date(2026, 9, 10),
                            available_float_days=3,
                            citation={},
                        ),
                        ScheduleTask(
                            project_id=project_id,
                            equipment_id="SWGR-A",
                            document_id=schedule.id,
                            task_id="INSTALL-SWGR",
                            name="Install and commission SWGR-A",
                            status="not_started",
                            dependencies=["DEL-SWGR"],
                            planned_finish=date(2026, 9, 15),
                            forecast_finish=date(2026, 10, 10),
                            available_float_days=0,
                            citation={},
                        ),
                    ])
                    await session.commit()

            asyncio.run(seed())
            imported = client.post(
                f"/projects/{project['id']}/supply-chain/import",
                files={"file": (
                    "risk.csv",
                    "equipment_id,vendor,planned_date,current_eta,required_on_site_date,status,location\n"
                    "SWGR-A,Grid Point,2026-08-10,2026-09-10,2026-08-12,critical,Hamburg\n",
                    "text/csv",
                )},
            ).json()["assessments"][0]

            async def snapshot() -> tuple[dict, dict, int]:
                async with sessions() as session:
                    shipment = await session.get(Shipment, uuid.UUID(imported["shipment_id"]))
                    task = await session.scalar(select(ScheduleTask).where(ScheduleTask.task_id == "INSTALL-SWGR"))
                    count = await session.scalar(select(func.count()).select_from(ImpactEvent))
                    return (
                        deepcopy({
                            "planned": shipment.planned_delivery,
                            "eta": shipment.forecast_delivery,
                            "required": shipment.required_on_site_date,
                            "status": shipment.status,
                        }),
                        deepcopy({"planned": task.planned_finish, "forecast": task.forecast_finish, "status": task.status}),
                        count,
                    )

            before = asyncio.run(snapshot())
            response = client.post(
                "/api/mitigations/simulate",
                json={
                    "project_id": project["id"],
                    "shipment_id": imported["shipment_id"],
                    "impact_event_id": imported["impact_event_id"],
                    "rules": {
                        "expedite_recovery_days": 10,
                        "expedite_additional_cost": 12000,
                        "resequence_recovery_days": 20,
                        "resequence_additional_cost": 4000,
                    },
                },
            )
            assert response.status_code == 201, response.text
            simulation = response.json()
            assert [item["key"] for item in simulation["scenarios"]] == [
                "do_nothing", "expedite_shipment", "resequence_installation",
            ]
            do_nothing, expedite, resequence = simulation["scenarios"]
            assert (do_nothing["projected_delay_days"], do_nothing["critical_path_exposure_days"], do_nothing["additional_cost"]) == (31, 26, 0)
            assert (expedite["projected_delay_days"], expedite["critical_path_exposure_days"], expedite["additional_cost"]) == (21, 16, 12000)
            assert (resequence["projected_delay_days"], resequence["critical_path_exposure_days"], resequence["additional_cost"]) == (31, 6, 4000)
            assert expedite["commissioning_date"] == "2026-09-30"
            assert expedite["assumptions"] and expedite["evidence_references"]
            assert asyncio.run(snapshot()) == before

            selected = client.post(
                f"/api/mitigations/{simulation['simulation_id']}/select",
                json={"project_id": project["id"], "scenario_key": "expedite_shipment"},
            )
            assert selected.status_code == 200, selected.text
            chain = selected.json()["recalculated_impact_chain"]
            assert chain["projected_schedule_delay_days"] == 21
            assert chain["projected_critical_path_exposure_days"] == 16
            assert asyncio.run(snapshot()) == before
            assert client.post(
                f"/api/mitigations/{simulation['simulation_id']}/select",
                json={"project_id": other["id"], "scenario_key": "expedite_shipment"},
            ).status_code == 404

            async def selected_count() -> int:
                async with sessions() as session:
                    return await session.scalar(select(func.count()).select_from(MitigationScenario).where(
                        MitigationScenario.project_id == project_id,
                        MitigationScenario.status == "selected",
                    ))

            assert asyncio.run(selected_count()) == 1
    finally:
        asyncio.run(engine.dispose())
