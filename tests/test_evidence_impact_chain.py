import asyncio
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.impact_chain import ImpactEventCreate, PropagationAssumptions, propagate_event
from app.main import app
from app.models import Base, Equipment, Project

EXPECTED_TYPES = [
    "SPEC_DEVIATION",
    "VENDOR_RESUBMISSION",
    "DELIVERY_RISK",
    "SCHEDULE_IMPACT",
    "COMMISSIONING_IMPACT",
]


@pytest.mark.asyncio
async def test_deterministic_propagation_keeps_evidence_separate_from_assumptions(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'impact-unit.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            project = Project(name="Impact unit")
            session.add(project)
            await session.flush()
            session.add(Equipment(project_id=project.id, equipment_id="UPS-01", name="UPS-01"))
            await session.commit()
            result = await propagate_event(
                session,
                project.id,
                "UPS-01",
                ImpactEventCreate(
                    type="SPEC_DEVIATION",
                    source_id="finding-001",
                    severity="high",
                    confidence=0.9,
                    timestamp=datetime.fromisoformat("2026-04-01T00:00:00+00:00"),
                    assumptions=PropagationAssumptions(
                        vendor_resubmission_days=5,
                        delivery_risk_days=10,
                        schedule_impact_days=3,
                        commissioning_impact_days=0,
                    ),
                    evidence=[{
                        "claim": "UPS voltage differs from the selected specification.",
                        "document": "UPS_Specification.md",
                        "page": 2,
                        "clause": "2.1",
                        "excerpt": "Nominal output voltage shall be 480/277 V.",
                        "model_version": "atlas-rag-v2",
                        "verification_status": "VERIFIED",
                    }],
                ),
            )
            assert [item.type for item in result.events] == EXPECTED_TYPES
            assert [item.delay_days for item in result.edges] == [5, 10, 3, 0]
            assert [item.confidence for item in result.events] == [0.9, 0.855, 0.8122, 0.7716, 0.733]
            assert result.events[0].assumptions["vendor_resubmission_days"] == 5
            assert result.evidence[0].verification_status == "VERIFIED"
            assert result.evidence[0].excerpt.startswith("Nominal output voltage")
    finally:
        await engine.dispose()


def test_impact_chain_api_is_project_scoped(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'impact-api.db'}")

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare())
    try:
        with TestClient(app) as client:
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            first = client.post("/projects", json={"name": "First"}).json()
            second = client.post("/projects", json={"name": "Second"}).json()

            async def seed_equipment() -> None:
                async with app.state.session_factory() as session:
                    session.add_all([
                        Equipment(project_id=uuid.UUID(first["id"]), equipment_id="UPS-01", name="First UPS"),
                        Equipment(project_id=uuid.UUID(second["id"]), equipment_id="UPS-01", name="Second UPS"),
                    ])
                    await session.commit()

            asyncio.run(seed_equipment())
            created = client.post(
                f"/projects/{first['id']}/equipment/UPS-01/impact-chain/events",
                json={
                    "type": "SPEC_DEVIATION",
                    "source_id": "finding-api-001",
                    "severity": "critical",
                    "confidence": 1,
                    "evidence": [{
                        "claim": "Verified deviation",
                        "document": "submittal.pdf",
                        "page": 4,
                        "clause": "3.2",
                        "excerpt": "Observed output is 415/240 V.",
                        "model_version": "atlas-rag-v2",
                        "verification_status": "VERIFIED",
                    }],
                },
            )
            assert created.status_code == 201, created.text
            assert [item["type"] for item in created.json()["events"]] == EXPECTED_TYPES
            assert len(created.json()["edges"]) == 4

            first_chain = client.get(
                f"/projects/{first['id']}/equipment/UPS-01/impact-chain"
            )
            second_chain = client.get(
                f"/projects/{second['id']}/equipment/UPS-01/impact-chain"
            )
            assert len(first_chain.json()["events"]) == 5
            assert second_chain.json()["events"] == []
            assert second_chain.json()["evidence"] == []
            assert client.get(
                f"/projects/{first['id']}/equipment/UNKNOWN/impact-chain"
            ).status_code == 404
    finally:
        asyncio.run(engine.dispose())
