import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base, Document


def test_dashboard_can_list_project_scoped_documents_with_cors(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'dashboard-api.db'}")

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    try:
        with TestClient(app) as client:
            app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
            project = client.post("/projects", json={"name": "Dashboard API test"}).json()
            project_id = uuid.UUID(project["id"])

            async def seed() -> None:
                async with app.state.session_factory() as session:
                    session.add(Document(
                        project_id=project_id,
                        filename="synthetic.md",
                        storage_path="/tmp/synthetic.md",
                        document_type="specification",
                        status="completed",
                        content_sha256="d" * 64,
                        mime_type="text/markdown",
                        size_bytes=1,
                        metadata_json={},
                    ))
                    await session.commit()

            asyncio.run(seed())
            assert any(item["id"] == project["id"] for item in client.get("/projects").json())
            response = client.get(f"/projects/{project['id']}/documents", headers={"Origin": "http://localhost:3000"})
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
            assert response.json()[0]["project_id"] == project["id"]
            route = client.post(
                f"/projects/{project['id']}/query-plan",
                json={"question": "Show critical path delay risk.", "history": []},
            )
            assert route.status_code == 200
            assert route.json()["plan"]["project_id"] == project["id"]
            assert route.json()["service"] == "schedule"
    finally:
        asyncio.run(engine.dispose())
