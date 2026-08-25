import uuid

from fastapi.testclient import TestClient

from app.config import Settings
from app.ingestion import Chunk
from app.main import app
from app.vector import project_filter, vector_payload
from app.workflow import build_workflow


def test_settings_accept_connection_overrides() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@db:5432/atlas",
        qdrant_url="http://qdrant:6333",
    )

    assert settings.database_url.endswith("/atlas")
    assert settings.qdrant_url == "http://qdrant:6333"


def test_settings_accept_groq_configuration() -> None:
    settings = Settings(groq_api_key="test-key", groq_model="llama-3.1-8b-instant")

    assert settings.groq_api_key == "test-key"
    assert settings.groq_model == "llama-3.1-8b-instant"


def test_blank_optional_api_keys_are_unset() -> None:
    settings = Settings(qdrant_api_key="", groq_api_key="")

    assert settings.qdrant_api_key is None
    assert settings.groq_api_key is None


def test_blank_example_variables_fall_back_to_local_defaults(tmp_path, monkeypatch) -> None:
    for key in ("DATABASE_URL", "QDRANT_URL", "FRONTEND_URL"):
        monkeypatch.delenv(key, raising=False)
    template = tmp_path / ".env"
    template.write_text("DATABASE_URL=\nQDRANT_URL=\nFRONTEND_URL=\n")

    settings = Settings(_env_file=template)

    assert settings.database_url == "postgresql+asyncpg://atlas:atlas@localhost:5433/atlas"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.allowed_cors_origins == ["http://localhost:3000"]


def test_cors_origins_come_from_environment_configuration() -> None:
    settings = Settings(cors_origins="https://atlas.example, https://review.example/")

    assert settings.allowed_cors_origins == ["https://atlas.example", "https://review.example"]


def test_deployment_variable_aliases_are_supported() -> None:
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@supabase:5432/atlas",
        QDRANT_URL="https://qdrant.example",
        QDRANT_API_KEY="qdrant-key",
        GROQ_API_KEY="groq-key",
        GROQ_MODEL="llama-3.1-8b-instant",
        FRONTEND_URL="https://atlas.example/",
    )

    assert settings.database_url.endswith("/atlas")
    assert settings.qdrant_url == "https://qdrant.example"
    assert settings.qdrant_api_key == "qdrant-key"
    assert settings.allowed_cors_origins == ["https://atlas.example"]
    assert settings.groq_api_key == "groq-key"
    assert settings.groq_model == "llama-3.1-8b-instant"


def test_vectors_and_workflow_are_project_scoped() -> None:
    project_id, document_id = uuid.uuid4(), uuid.uuid4()
    payload = vector_payload(
        Chunk(project_id, document_id, "RFI", "rfi.md", 1, "General", 0, "project-scoped text")
    )

    assert payload["project_id"] == str(project_id)
    assert payload["document_id"] == str(document_id)
    assert project_filter(project_id).must[0].match.value == str(project_id)
    assert build_workflow().invoke({"project_id": str(project_id), "status": "new"})["status"] == "ready"


def test_startup_initializes_local_clients() -> None:
    with TestClient(app):
        assert app.state.db_engine is not None
        assert app.state.qdrant is not None
        assert app.state.workflow is not None
