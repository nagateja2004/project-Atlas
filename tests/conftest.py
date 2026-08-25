"""
Isolates the test session from the developer's local environment.

`Settings` reads `.env`, and OS environment variables outrank it, so without
this the suite inherits whatever the machine happens to have configured. With a
real `GROQ_API_KEY` present that is not a cosmetic problem: LLMQueryPlanner
builds a live client and the planner tests call the provider for real. That
makes results depend on network and quota, slows the suite by roughly 4x, spends
billable tokens, and eventually fails with 429 once the daily limit is reached.

Tests must see the same configuration CI does — code defaults, plus whatever an
individual test passes explicitly — so this fixture drops `.env` for the session
and blanks the variables that would otherwise reach an external service.
"""

import os

import pytest

from app.config import Settings, get_settings

# Every alias Settings resolves that points at a credential or an external
# endpoint. Blanked rather than deleted: deleting an OS variable would just let
# the `.env` value through on the next lookup.
EXTERNAL_ENV_VARS = (
    "GROQ_API_KEY",
    "ATLAS_GROQ_API_KEY",
    "GROQ_MODEL",
    "ATLAS_GROQ_MODEL",
    "QDRANT_API_KEY",
    "ATLAS_QDRANT_API_KEY",
    "QDRANT_URL",
    "ATLAS_QDRANT_URL",
    "SUPABASE_URL",
    "ATLAS_SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "ATLAS_SUPABASE_SERVICE_ROLE_KEY",
    "JWT_SECRET_KEY",
    "ATLAS_JWT_SECRET_KEY",
)

# Blanking keys is not sufficient on its own: an anonymous provider resolves
# without credentials, so leaving it in the order let the suite make real
# network calls to a public endpoint. Pin a keyed-only order for the session -
# with every key blanked above, no route resolves and nothing reaches a network.
KEYED_ONLY_PROVIDERS = "groq,openrouter"


@pytest.fixture(scope="session", autouse=True)
def _isolate_environment_from_dotenv() -> None:
    original_env_file = Settings.model_config.get("env_file")
    saved = {name: os.environ.get(name) for name in EXTERNAL_ENV_VARS}

    # Ignore .env entirely for the session.
    Settings.model_config["env_file"] = None
    for name in EXTERNAL_ENV_VARS:
        os.environ.pop(name, None)
    # Any ATLAS_* override would silently change retrieval or ingestion behaviour.
    atlas_overrides = {name: os.environ.pop(name) for name in list(os.environ) if name.startswith("ATLAS_")}
    os.environ["ATLAS_LLM_PROVIDERS"] = KEYED_ONLY_PROVIDERS
    get_settings.cache_clear()

    yield

    Settings.model_config["env_file"] = original_env_file
    os.environ.pop("ATLAS_LLM_PROVIDERS", None)
    for name, value in saved.items():
        if value is not None:
            os.environ[name] = value
    os.environ.update(atlas_overrides)
    get_settings.cache_clear()

