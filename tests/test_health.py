import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.main import app


class ReadyQdrant:
    async def get_collections(self):
        return []


class BrokenQdrant:
    async def get_collections(self):
        raise RuntimeError("unavailable")


def test_health_is_liveness_and_ready_checks_dependencies() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    client = TestClient(app)
    try:
        assert client.get("/health").json() == {"status": "ok", "components": {"api": "ok"}}
        app.state.db_engine = engine
        app.state.qdrant = ReadyQdrant()
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["components"] == {"api": "ok", "database": "ok", "qdrant": "ok"}
        app.state.qdrant = BrokenQdrant()
        assert client.get("/ready").status_code == 503
    finally:
        client.close()
        asyncio.run(engine.dispose())
