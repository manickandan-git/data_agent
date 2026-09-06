"""Provider adapters shared by every agent workflow."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Any

from opentelemetry.trace import Status, StatusCode

from data_agent.config import Settings, get_config
from data_agent.utils.observability import record_operation, record_value, start_operation_span


@dataclass(frozen=True)
class ProviderAdapter:
    build: Callable[[Settings, str], Any]
    structured_method: str | None = None


def _key(settings: Settings, field: str) -> str:
    secret = getattr(settings, field)
    if not secret or not secret.get_secret_value():
        raise ValueError(f"{field.upper()} is required for the selected LLM provider.")
    return secret.get_secret_value()


def _openai(settings: Settings, model: str):
    from langchain_openai import ChatOpenAI

    # Use the modern endpoint for the verified model family, while preserving
    # legacy/custom model overrides and their existing request contract.
    modern = model.startswith("gpt-5.6")
    options = (
        {
            "reasoning": {"effort": settings.openai_reasoning_effort},
            "use_responses_api": True,
            "output_version": "v0",
        }
        if modern
        else {"temperature": settings.llm_temperature, "use_responses_api": False}
    )
    return ChatOpenAI(
        model=model,
        api_key=_key(settings, "openai_api_key"),
        base_url=settings.openai_base_url or None,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        max_tokens=settings.llm_max_tokens,
        **options,
    )


def _anthropic(settings: Settings, model: str):
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        api_key=_key(settings, "anthropic_api_key"),
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        max_tokens=settings.llm_max_tokens,
    )


PROVIDERS = {
    "openai": ProviderAdapter(_openai, "function_calling"),
    "anthropic": ProviderAdapter(_anthropic),
}
OPENAI_DEFAULTS = {
    "low": "gpt-5.6-luna",
    "medium": "gpt-5.6-terra",
    "high": "gpt-5.6-sol",
}


def register_provider(name: str, adapter: ProviderAdapter) -> None:
    """Register an application-owned adapter before invoking the graphs."""
    PROVIDERS[name.lower()] = adapter
    get_llm_factory.cache_clear()


def _resolve(level: str, settings: Settings):
    level = level.lower()
    if level not in OPENAI_DEFAULTS:
        raise ValueError(f"Invalid difficulty level: {level}")
    provider = settings.llm_provider.lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    model = getattr(settings, f"llm_model_{level}")
    if not model:
        if provider != "openai":
            raise ValueError(f"LLM_MODEL_{level.upper()} is required for provider {provider}.")
        model = OPENAI_DEFAULTS[level]
    return PROVIDERS[provider], model


class LLMFactory:
    """Own reusable clients for a settings snapshot; injectable in tests."""

    def __init__(self, settings: Settings):
        self.settings = settings.model_copy(deep=True)
        self._clients: dict[tuple[str, str], Any] = {}

    def get(self, level: str):
        adapter, model = _resolve(level, self.settings)
        key = (self.settings.llm_provider.lower(), model)
        if key not in self._clients:
            self._clients[key] = adapter.build(self.settings, model)
        return self._clients[key]


@lru_cache(maxsize=1)
def get_llm_factory() -> LLMFactory:
    return LLMFactory(get_config())


def reset_llm_clients() -> None:
    """Reload configuration and discard cached clients after credential changes."""
    get_llm_factory.cache_clear()
    get_config.cache_clear()


def pick_llm(level: str, settings: Settings | None = None):
    if settings is None:
        return get_llm_factory().get(level)
    return LLMFactory(settings).get(level)


def structured_llm(level: str, schema: type, settings: Settings | None = None):
    client = pick_llm(level, settings)
    effective_settings = settings if settings is not None else get_llm_factory().settings
    adapter, _ = _resolve(level, effective_settings)
    options = {"method": adapter.structured_method} if adapter.structured_method else {}
    return client.with_structured_output(schema, **options)


def observed_llm_invoke(runnable, payload, level: str, settings: Settings | None = None):
    """Invoke an LLM with provider metadata, never prompt or response content."""
    effective_settings = settings if settings is not None else get_llm_factory().settings
    _, model = _resolve(level, effective_settings)
    attributes = {
        "gen_ai.provider.name": effective_settings.llm_provider.lower(),
        "gen_ai.request.model": model,
        "data_agent.difficulty": level.lower(),
    }
    started = perf_counter()
    with start_operation_span("llm.invoke", attributes) as span:
        try:
            response = runnable.invoke(payload)
        except Exception as error:
            duration_ms = (perf_counter() - started) * 1000
            if span.is_recording():
                span.set_attribute("exception.type", type(error).__name__)
                span.set_status(Status(StatusCode.ERROR))
            record_operation("llm.invoke", duration_ms, outcome="error", attributes=attributes)
            raise

        duration_ms = (perf_counter() - started) * 1000
        record_operation("llm.invoke", duration_ms, outcome="success", attributes=attributes)
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = usage.get(key)
                if isinstance(value, int):
                    record_value("llm.invoke", value, kind=key, attributes=attributes)
        return response
