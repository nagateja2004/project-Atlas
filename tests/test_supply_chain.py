import asyncio
import csv
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base


def test_synthetic_shipments_alert_latency_schedule_links_and_alternatives(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'supply-chain.db'}")

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    try:
        with TestClient(app) as client:
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            project = client.post("/projects", json={"name": "Synthetic supply-chain test"}).json()
            project_id = project["id"]

            seeded = client.post(f"/projects/{project_id}/supply-chain/seed")
            assert seeded.status_code == 200
            payload = seeded.json()
            assert payload["synthetic_simulation"] is True
            assert len(payload["shipments"]) == 5
            assert all(len(item["supplier_tiers"]) == 3 for item in payload["shipments"])
            assert all(item["live_position"] is None for item in payload["shipments"])
            schedule_path = Path(__file__).parents[1] / "data" / "synthetic_epc" / "schedules" / "atlas_demo_schedule.csv"
            with schedule_path.open() as stream:
                schedule_task_ids = {row["task_id"] for row in csv.DictReader(stream)}
            assert {item["schedule_task_id"] for item in payload["shipments"]} <= schedule_task_ids

            switchgear = next(item for item in payload["shipments"] if item["reference"] == "SYN-SHP-001")
            risk = client.get(
                f"/projects/{project_id}/supply-chain/shipments/{switchgear['shipment_id']}/risk"
            ).json()
            assert risk["forecast_delay_days"] == 35
            assert risk["schedule_task_id"] == "T-140"
            assert risk["schedule_float_consumed_days"] == 7
            assert risk["critical_path_impact_days"] == 28
            assert risk["severity"] == "critical"
            assert risk["alert_latency_minutes"] == 90
            assert risk["alternative_option"]["recovery_days"] == 18

            event = client.post(
                f"/projects/{project_id}/supply-chain/shipments/{switchgear['shipment_id']}/risk-events",
                json={
                    "event_type": "synthetic_port_hold",
                    "description": "Synthetic customs-document hold; no live position used.",
                    "occurred_at": "2026-04-20T10:00:00Z",
                    "alert_generated_at": "2026-04-20T11:15:00Z",
                    "forecast_delay_days": 42,
                },
            )
            assert event.status_code == 201
            assert event.json()["alert_latency_minutes"] == 75
            updated_risk = client.get(
                f"/projects/{project_id}/supply-chain/shipments/{switchgear['shipment_id']}/risk"
            ).json()
            assert updated_risk["forecast_delay_days"] == 42
            assert updated_risk["alert_latency_minutes"] == 75

            alternatives = client.get(
                f"/projects/{project_id}/supply-chain/shipments/{switchgear['shipment_id']}/alternatives"
            ).json()
            assert alternatives["synthetic_simulation"] is True
            assert alternatives["options"][0]["residual_delay_days"] == 24

            reset = client.post(f"/projects/{project_id}/demo/reset")
            assert reset.status_code == 200
            restored_risk = client.get(
                f"/projects/{project_id}/supply-chain/shipments/{switchgear['shipment_id']}/risk"
            ).json()
            assert restored_risk["forecast_delay_days"] == 35
            assert restored_risk["alert_latency_minutes"] == 90

            assert len(client.post(f"/projects/{project_id}/supply-chain/seed").json()["shipments"]) == 5
            other = client.post("/projects", json={"name": "Other project"}).json()
            assert client.get(f"/projects/{other['id']}/supply-chain/shipments").json()["shipments"] == []
    finally:
        asyncio.run(engine.dispose())
