import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base


def test_benchmark_hours_separation_validation_and_project_isolation(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'benchmarks.db'}")

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    client = TestClient(app)
    try:
        app.state.session_factory = sessions
        project = client.post("/projects", json={"name": "Benchmark project"}).json()
        other = client.post("/projects", json={"name": "Other project"}).json()
        base = {
                "project_id": project["id"],
                "measurement_source": "Synthetic timed demo run",
                "synthetic_data": True,
        }
        measured = client.post("/api/benchmarks", json={
                **base,
                "workflow_type": "rfi_search",
                "manual_baseline_seconds": 420,
                "atlas_execution_seconds": 60,
                "sample_count": 2,
                "measurement_kind": "measured",
        })
        assert measured.status_code == 201, measured.text
        assert measured.json()["hours_saved"] == 0.1
        assert measured.json()["total_hours_saved"] == 0.2

        projected = client.post("/api/benchmarks", json={
                **base,
                "workflow_type": "coordination_report_preparation",
                "manual_baseline_seconds": 3900,
                "atlas_execution_seconds": 300,
                "sample_count": 10,
                "measurement_kind": "projected",
        })
        assert projected.status_code == 201, projected.text

        summary = client.get(
            "/api/benchmarks/summary", params={"project_id": project["id"]}
        ).json()
        assert summary["measured_hours_saved"] == 0.2
        assert summary["projected_monthly_hours_saved"] == 10.0
        assert summary["measured_sample_count"] == 2
        assert summary["projected_monthly_sample_count"] == 10
        assert summary["synthetic_data_present"] is True
        assert "synthetic" in summary["label"].lower()
        assert len(summary["workflows"]) == 5

        isolated = client.get(
            "/api/benchmarks/summary", params={"project_id": other["id"]}
        ).json()
        assert isolated["record_count"] == 0
        assert isolated["measured_hours_saved"] == 0
        assert client.post("/api/benchmarks", json={
                **base,
                "workflow_type": "unsupported_workflow",
                "manual_baseline_seconds": 1,
                "atlas_execution_seconds": 1,
                "sample_count": 0,
                "measurement_kind": "measured",
        }).status_code == 422
    finally:
        client.close()
        asyncio.run(engine.dispose())
