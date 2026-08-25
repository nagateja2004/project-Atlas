"""
Guards agreement between the local datastore config files.

The suite runs on SQLite and an in-memory Qdrant, so a wrong host port in
docker-compose.yml, alembic.ini, .env.example or the Settings default cannot be
caught by any other test: everything passes while the application and
`alembic upgrade head` are both unable to connect. These checks compare the
files directly.
"""

import re
from pathlib import Path

import yaml

from app.config import Settings

ROOT = Path(__file__).parents[1]


def _published_host_port(service: str, container_port: int) -> int:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    for mapping in compose["services"][service]["ports"]:
        host, _, container = str(mapping).partition(":")
        if container.split("/")[0] == str(container_port):
            return int(host)
    raise AssertionError(f"docker-compose.yml publishes no {service} port for {container_port}")


def _port_in(text: str) -> int:
    match = re.search(r"localhost:(\d+)/atlas", text)
    assert match, "no localhost:<port>/atlas connection string found"
    return int(match.group(1))


def test_settings_default_targets_the_port_compose_publishes() -> None:
    default = Settings.model_fields["database_url"].default
    assert _port_in(default) == _published_host_port("postgres", 5432)


def test_alembic_targets_the_port_compose_publishes() -> None:
    ini = (ROOT / "alembic.ini").read_text(encoding="utf-8")
    assert _port_in(ini) == _published_host_port("postgres", 5432)


def test_env_example_targets_the_port_compose_publishes() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert _port_in(example) == _published_host_port("postgres", 5432)


def test_env_example_qdrant_url_matches_compose() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    match = re.search(r"QDRANT_URL=http://localhost:(\d+)", example)
    assert match, "QDRANT_URL not set in .env.example"
    assert int(match.group(1)) == _published_host_port("qdrant", 6333)


def test_env_example_uses_the_async_postgres_driver() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "postgresql+asyncpg://" in example, "DATABASE_URL must use the asyncpg driver"


def test_env_example_copies_into_a_loadable_configuration(tmp_path, monkeypatch) -> None:
    """
    `cp .env.example .env` must produce a config the app can actually start
    from. A blank value is a parse error for any typed field, not a default, so
    an over-eager template previously made Settings() raise 16 validation errors.
    """
    env = tmp_path / ".env"
    env.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    for key in [name for name in __import__("os").environ if name.startswith("ATLAS_")]:
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=str(env))

    assert settings.embedding_dimensions > 0
    assert settings.groq_model
    assert settings.ingestion_timeout_seconds > 0


def test_render_declares_every_variable_the_start_script_requires() -> None:
    render = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    declared = {item["key"] for item in render["services"][0]["envVars"]}
    script = (ROOT / "scripts" / "start_production.sh").read_text(encoding="utf-8")
    # PORT is injected by the platform, so it is required but never declared.
    required = set(re.findall(r"\$\{([A-Z_]+):\?", script)) - {"PORT"}
    assert required <= declared, f"render.yaml is missing {sorted(required - declared)}"


def test_render_embedding_dimensions_match_the_declared_model() -> None:
    """A width that disagrees with the model makes every ingest fail with 409."""
    render = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    env = {item["key"]: item.get("value") for item in render["services"][0]["envVars"]}
    widths = {"sentence-transformers/all-MiniLM-L6-v2": "384"}
    model = env.get("ATLAS_EMBEDDING_MODEL")
    if model in widths:
        assert env.get("ATLAS_EMBEDDING_DIMENSIONS") == widths[model]


def test_session_is_isolated_from_the_model_provider() -> None:
    """
    Fails loudly if tests/conftest.py stops isolating the session.

    A visible GROQ_API_KEY makes LLMQueryPlanner build a live client, so the
    planner tests call the provider for real: non-deterministic, ~4x slower, and
    billable until the daily token limit returns 429.
    """
    settings = Settings()

    assert settings.groq_api_key is None, "GROQ_API_KEY leaked into the test session"
    assert settings.qdrant_api_key is None, "QDRANT_API_KEY leaked into the test session"


def test_session_ignores_a_local_dotenv() -> None:
    assert Settings.model_config.get("env_file") is None, (
        ".env is being read during tests, so results depend on the developer's machine"
    )


def test_session_resolves_no_llm_route_at_all() -> None:
    """
    Blanking keys is not enough once a provider can run anonymously: it would
    resolve without credentials and the suite would call a public endpoint for
    real. tests/conftest.py pins a keyed-only order; this proves it holds.
    """
    from app.llm import PROVIDERS, LLMGateway

    gateway = LLMGateway(Settings())

    assert gateway.routes == [], f"tests can reach {gateway.providers}"
    assert not any(
        PROVIDERS[name].anonymous for name in Settings().llm_provider_order if name in PROVIDERS
    ), "an anonymous provider in the test order reopens live network access"
