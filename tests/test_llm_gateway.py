from types import SimpleNamespace

import httpx
import openai
import pytest

from app.compliance import ComplianceExplainer
from app.config import Settings
from app.ingestion import IngestionError
from app.llm import PROVIDERS, LLMGateway, Route
from app.schedule import ScheduleNarrator

REQUEST = httpx.Request("POST", "https://example.test/v1/chat/completions")


def _status_error(kind: type[openai.APIStatusError], code: int) -> openai.APIStatusError:
    response = httpx.Response(code, request=REQUEST, json={"error": {"message": "provider said no"}})
    return kind("provider said no", response=response, body=None)


def _rate_limited() -> openai.RateLimitError:
    return _status_error(openai.RateLimitError, 429)


def _auth_failure() -> openai.AuthenticationError:
    return _status_error(openai.AuthenticationError, 401)


class Completions:
    """Mirrors the real client surface: client.chat.completions.create(...)."""

    def __init__(self, *, content: str | None = "ok", error: Exception | None = None) -> None:
        self.content, self.error = content, error
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def _client(completions: Completions) -> SimpleNamespace:
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def _gateway(*completions: Completions, providers: tuple[str, ...] = ("groq",)) -> LLMGateway:
    """A gateway whose routes are stubs, one per supplied Completions."""
    gateway = LLMGateway(Settings(groq_api_key="test-key"))
    gateway.routes = [
        Route(provider=PROVIDERS[providers[index % len(providers)]], model="stub-model", client=_client(item))
        for index, item in enumerate(completions)
    ]
    # One attempt and no backoff by default: retry behaviour is asserted
    # explicitly by the tests that care, and real sleeps would slow the suite.
    gateway.attempts_per_provider, gateway.retry_backoff_seconds = 1, 0
    return gateway


# --------------------------------------------------------------------------
# Provider resolution
# --------------------------------------------------------------------------

def test_provider_order_is_configurable_and_deduplicated_by_available_keys(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    gateway = LLMGateway(Settings(groq_api_key="g", llm_providers="groq, openrouter, nvidia"))

    # nvidia has no key, so it is skipped rather than raising.
    assert gateway.providers == ["groq", "openrouter"]


def test_a_provider_without_a_key_is_skipped_not_fatal(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    gateway = LLMGateway(Settings(groq_api_key="", llm_providers="openrouter"))

    assert gateway.routes == []
    assert gateway.client is None


def test_an_unknown_provider_name_is_ignored_with_a_warning(caplog) -> None:
    gateway = LLMGateway(Settings(groq_api_key="g", llm_providers="groq,does-not-exist"))

    assert gateway.providers == ["groq"]


def test_every_registry_entry_is_openai_compatible_and_complete() -> None:
    for name, provider in PROVIDERS.items():
        assert provider.name == name
        assert provider.base_url.startswith("https://"), name
        assert provider.key_env.isupper(), name
        assert provider.default_model, name


def test_per_provider_model_override_beats_the_registry_default(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "some/other-model:free")

    gateway = LLMGateway(Settings(llm_providers="openrouter"))

    assert gateway.routes[0].model == "some/other-model:free"


# --------------------------------------------------------------------------
# Failover - the reason this router exists
# --------------------------------------------------------------------------

async def test_a_rate_limited_provider_rolls_to_the_next_one() -> None:
    """
    The case that took the demo down: one provider's daily token cap returned
    429 and generation failed outright, even though other free tiers were idle.
    """
    exhausted = Completions(error=_rate_limited())
    healthy = Completions(content="second provider answered")
    gateway = _gateway(exhausted, healthy, providers=("groq", "openrouter"))

    assert await gateway.generate("instructions", "content") == "second provider answered"
    assert len(exhausted.calls) == 1 and len(healthy.calls) == 1  # one attempt each here


async def test_failover_covers_outages_timeouts_and_bad_credentials() -> None:
    for error in (
        _rate_limited(),
        _auth_failure(),
        openai.APIConnectionError(request=REQUEST),
        openai.APITimeoutError(request=REQUEST),
        _status_error(openai.InternalServerError, 500),
    ):
        gateway = _gateway(Completions(error=error), Completions(content="fallback"), providers=("groq", "openrouter"))
        assert await gateway.generate("i", "c") == "fallback", type(error).__name__


async def test_an_empty_response_also_rolls_to_the_next_provider() -> None:
    gateway = _gateway(Completions(content=None), Completions(content="real answer"), providers=("groq", "openrouter"))

    assert await gateway.generate("i", "c") == "real answer"


async def test_exhausting_every_provider_is_a_502() -> None:
    gateway = _gateway(
        Completions(error=_rate_limited()),
        Completions(error=_rate_limited()),
        providers=("groq", "openrouter"),
    )

    with pytest.raises(IngestionError) as caught:
        await gateway.generate("instructions", "content")

    assert (caught.value.code, caught.value.status_code) == ("model_gateway_error", 502)


async def test_a_malformed_request_fails_immediately_without_burning_other_quotas() -> None:
    """A 400 would be rejected identically everywhere, so failing over is waste."""
    first = Completions(error=_status_error(openai.BadRequestError, 400))
    second = Completions(content="never reached")
    gateway = _gateway(first, second, providers=("groq", "openrouter"))

    with pytest.raises(IngestionError) as caught:
        await gateway.generate("instructions", "content")

    assert caught.value.status_code == 502
    assert second.calls == [], "must not try the next provider on a request-shaped error"


async def test_the_first_healthy_provider_is_used_and_the_rest_untouched() -> None:
    first = Completions(content="primary")
    second = Completions(content="should not run")
    gateway = _gateway(first, second, providers=("groq", "openrouter"))

    assert await gateway.generate("i", "c") == "primary"
    assert second.calls == []


# --------------------------------------------------------------------------
# Contract preserved from the single-provider gateway
# --------------------------------------------------------------------------

async def test_no_configured_provider_is_a_503_before_any_request(monkeypatch) -> None:
    for provider in PROVIDERS.values():
        monkeypatch.delenv(provider.key_env, raising=False)
        monkeypatch.delenv(f"ATLAS_{provider.key_env}", raising=False)
    # Keyed providers only: the default order ends with an anonymous provider,
    # which resolves without credentials and would never leave the list empty.
    gateway = LLMGateway(Settings(groq_api_key="", llm_providers="groq,openrouter"))

    assert gateway.client is None
    with pytest.raises(IngestionError) as caught:
        await gateway.generate("instructions", "content")

    assert (caught.value.code, caught.value.status_code) == ("generation_unavailable", 503)


async def test_gateway_errors_never_leak_provider_detail() -> None:
    gateway = _gateway(Completions(error=_auth_failure()))

    with pytest.raises(IngestionError) as caught:
        await gateway.generate("instructions", "content")

    assert "provider said no" not in str(caught.value).lower()


async def test_successful_generation_strips_content_and_sends_the_data_boundary() -> None:
    completions = Completions(content="  the answer  ")
    gateway = _gateway(completions)

    assert await gateway.generate("Answer briefly.", "question", json_output=True) == "the answer"

    sent = completions.calls[0]
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["temperature"] == 0
    assert sent["model"] == "stub-model"
    assert sent["messages"][0]["role"] == "system"
    assert "untrusted data" in sent["messages"][0]["content"].lower()
    assert sent["messages"][1] == {"role": "user", "content": "question"}


# --------------------------------------------------------------------------
# Optional enrichment must degrade, never fail the caller
# --------------------------------------------------------------------------

async def test_optional_compliance_explanation_falls_back_to_deterministic_text() -> None:
    explainer = ComplianceExplainer(Settings(groq_api_key="test-key"))
    explainer.gateway.routes = [
        Route(provider=PROVIDERS["groq"], model="stub", client=_client(Completions(error=_auth_failure())))
    ]
    draft = SimpleNamespace(explanation="Deterministic result.", model_dump=lambda **_kwargs: {})

    assert await explainer.explain(draft) == "Deterministic result."


async def test_optional_schedule_narrative_falls_back_to_deterministic_result() -> None:
    narrator = ScheduleNarrator(Settings(groq_api_key="test-key"))
    narrator.gateway.routes = [
        Route(provider=PROVIDERS["groq"], model="stub", client=_client(Completions(error=_auth_failure())))
    ]
    risk = SimpleNamespace(model_dump=lambda **_kwargs: {})

    assert await narrator.enrich(risk) is risk


# --------------------------------------------------------------------------
# Anonymous providers - the zero-setup last resort
# --------------------------------------------------------------------------

def test_an_anonymous_provider_is_usable_without_any_key(monkeypatch) -> None:
    """
    llm7 serves a limited catalogue with no credential, so it stays available
    when every keyed provider is exhausted. Verified live: with Groq rate
    limited, generation failed over to llm7 and still returned a cited answer.
    """
    monkeypatch.delenv("LLM7_API_KEY", raising=False)

    gateway = LLMGateway(Settings(groq_api_key="", llm_providers="llm7"))

    assert gateway.providers == ["llm7"]
    assert gateway.routes[0].client is not None


def test_a_keyed_provider_without_its_key_is_still_skipped(monkeypatch) -> None:
    """Only providers flagged anonymous get the exemption."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM7_API_KEY", raising=False)

    gateway = LLMGateway(Settings(groq_api_key="", llm_providers="openrouter,llm7"))

    assert gateway.providers == ["llm7"]


def test_only_llm7_is_marked_anonymous() -> None:
    """A wrongly-flagged provider would send unauthenticated requests forever."""
    assert {name for name, p in PROVIDERS.items() if p.anonymous} == {"llm7"}


def test_the_default_order_keeps_an_anonymous_fallback_last() -> None:
    # The declared default, not Settings().llm_provider_order: the test session
    # deliberately pins a keyed-only order so nothing reaches a live endpoint.
    order = [name.strip() for name in Settings.model_fields["llm_providers"].default.split(",")]

    assert order[-1] == "llm7", "the unauthenticated tier must be the last resort"
    assert len(order) > 1, "a single provider leaves no failover path"


# --------------------------------------------------------------------------
# Key resolution from .env - the bug that made the whole router single-provider
# --------------------------------------------------------------------------

def test_a_provider_key_set_only_in_dotenv_is_found(tmp_path, monkeypatch) -> None:
    """
    pydantic-settings loads .env into declared fields, never into os.environ.
    Resolving provider keys from os.environ alone meant every provider except
    groq - the one with a typed field - reported no key when it was set in
    .env, so a configured fallback silently never existed.
    """
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", str(env))

    gateway = LLMGateway(Settings(groq_api_key="", llm_providers="gemini"))

    assert gateway.providers == ["gemini"]


def test_the_process_environment_outranks_the_dotenv_file(tmp_path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_MODEL=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_MODEL", "from-environment")
    monkeypatch.setitem(Settings.model_config, "env_file", str(env))

    gateway = LLMGateway(Settings(llm_providers="openrouter"))

    assert gateway.routes[0].model == "from-environment"


# --------------------------------------------------------------------------
# Transient retry - free endpoints fail intermittently, not permanently
# --------------------------------------------------------------------------

class FlakyCompletions:
    """Fails `failures` times with a transient error, then succeeds."""

    def __init__(self, failures: int, error: Exception) -> None:
        self.remaining, self.error, self.calls = failures, error, 0

    async def create(self, **_kwargs):
        self.calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="recovered"))])


async def test_a_transiently_overloaded_provider_is_retried_before_failover() -> None:
    """
    Measured on a hosted flash model: only 2 of 4 back-to-back calls answered,
    the rest "503 model is overloaded". Treating that as fatal made three
    healthy-but-flaky providers fail a request outright.
    """
    flaky = FlakyCompletions(2, _status_error(openai.InternalServerError, 503))
    gateway = _gateway(Completions(content="unused"))
    gateway.routes[0].client = _client(flaky)
    gateway.attempts_per_provider, gateway.retry_backoff_seconds = 3, 0

    assert await gateway.generate("i", "c") == "recovered"
    assert flaky.calls == 3, "should have retried the same provider twice before succeeding"


async def test_retries_are_bounded_then_failover_happens() -> None:
    exhausted = FlakyCompletions(99, _rate_limited())
    healthy = Completions(content="next provider")
    gateway = _gateway(Completions(), Completions(), providers=("groq", "openrouter"))
    gateway.routes[0].client = _client(exhausted)
    gateway.routes[1].client = _client(healthy)
    gateway.attempts_per_provider, gateway.retry_backoff_seconds = 2, 0

    assert await gateway.generate("i", "c") == "next provider"
    assert exhausted.calls == 2, "must stop at the configured attempt limit"


async def test_a_terminal_error_is_not_retried() -> None:
    """A bad key or retired model fails identically every time."""
    dead = FlakyCompletions(99, _auth_failure())
    gateway = _gateway(Completions(), Completions(content="next"), providers=("groq", "openrouter"))
    gateway.routes[0].client = _client(dead)
    gateway.attempts_per_provider, gateway.retry_backoff_seconds = 3, 0

    assert await gateway.generate("i", "c") == "next"
    assert dead.calls == 1, "no point retrying a credential or model-name failure"
