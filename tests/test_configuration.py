from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from config import Settings
from utils.llm_pick import (
    PROVIDERS,
    LLMFactory,
    ProviderAdapter,
    pick_llm,
    structured_llm,
)


@pytest.fixture
def settings_factory(monkeypatch):
    # Do not read developer credentials or machine-specific settings.
    import os
    for name in list(os.environ):
        if name.lower() in Settings.model_fields:
            monkeypatch.delenv(name)
    return lambda **values: Settings(_env_file=None, **values)


def test_defaults_do_not_require_provider_keys(settings_factory):
    settings = settings_factory()
    assert settings.llm_provider == "openai"
    assert settings.anthropic_api_key is None
    assert settings.sql_timeout_seconds == 30
    assert settings.observability_log_level == "INFO"
    assert settings.observability_json_logs is True
    assert settings.api_max_request_bytes == 16_384


def test_default_categorical_columns_cover_safe_seed_dimensions(settings_factory):
    assert settings_factory().sql_categorical_columns == {
        "payments": ["payment_method", "payment_status"],
        "ratings": ["rating"],
        "rides": ["status", "cancellation_reason"],
        "users": ["user_type", "city", "province", "is_active"],
        "vehicles": ["make", "model", "color", "is_active"],
    }


def test_secrets_are_redacted(settings_factory):
    settings = settings_factory(openai_api_key="private-value")
    assert "private-value" not in repr(settings)
    assert "private-value" not in settings.model_dump_json()


@pytest.mark.parametrize("field,value", [
    ("sql_timeout_seconds", 0), ("sql_row_limit", -1),
    ("llm_max_retries", -1), ("database_schema", "public; DROP TABLE users"),
    ("observability_log_level", "TRACE"),
    ("api_max_request_bytes", 100),
    ("sql_categorical_columns", {"payments; DROP": ["payment_method"]}),
    ("sql_categorical_columns", {"payments": ["payment_method", "payment_method"]}),
])
def test_invalid_configuration_is_rejected(settings_factory, field, value):
    with pytest.raises(ValidationError):
        settings_factory(**{field: value})


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_provider_and_model_selection(settings_factory, monkeypatch, provider):
    builder = Mock(return_value=object())
    monkeypatch.setitem(PROVIDERS, provider, ProviderAdapter(builder))
    settings = settings_factory(llm_provider=provider, llm_model_medium="chosen-model")
    assert pick_llm("medium", settings) is builder.return_value
    builder.assert_called_once_with(settings, "chosen-model")


@pytest.mark.parametrize("method", [None, "function_calling"])
def test_structured_output_options_are_adapter_owned(settings_factory, monkeypatch, method):
    client = Mock()
    monkeypatch.setitem(PROVIDERS, "fake", ProviderAdapter(lambda *_: client, method))
    settings = settings_factory(llm_provider="fake", llm_model_medium="test-model")
    structured_llm("medium", Settings, settings)
    expected = {"method": method} if method else {}
    client.with_structured_output.assert_called_once_with(Settings, **expected)


def test_anthropic_requires_its_own_model(settings_factory):
    with pytest.raises(ValueError, match="LLM_MODEL_MEDIUM"):
        pick_llm("medium", settings_factory(llm_provider="anthropic"))


def test_missing_selected_key_has_clear_error(settings_factory):
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        pick_llm("low", settings_factory())


def test_invalid_provider_and_level(settings_factory):
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        pick_llm("low", settings_factory(llm_provider="missing"))
    with pytest.raises(ValueError, match="Invalid difficulty"):
        pick_llm("unknown", settings_factory())


def test_database_configuration_required_only_when_used(settings_factory):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        settings_factory().require_database_url()


@pytest.mark.parametrize("provider,module,constructor,key_field", [
    ("openai", "langchain_openai", "ChatOpenAI", "openai_api_key"),
    ("anthropic", "langchain_anthropic", "ChatAnthropic", "anthropic_api_key"),
])
def test_native_adapter_forwards_configuration(
    settings_factory, monkeypatch, provider, module, constructor, key_field,
):
    import importlib
    builder = Mock()
    monkeypatch.setattr(importlib.import_module(module), constructor, builder)
    settings = settings_factory(
        llm_provider=provider, llm_model_medium="configured-model",
        llm_timeout_seconds=12, llm_max_retries=1, **{key_field: "test-key"},
    )
    pick_llm("medium", settings)
    assert builder.call_args.kwargs["model"] == "configured-model"
    assert builder.call_args.kwargs["api_key"] == "test-key"
    assert builder.call_args.kwargs["timeout"] == 12
    assert builder.call_args.kwargs["max_retries"] == 1


def test_factory_reuses_clients(settings_factory, monkeypatch):
    builder = Mock(return_value=object())
    monkeypatch.setitem(PROVIDERS, "openai", ProviderAdapter(builder))
    factory = LLMFactory(settings_factory())
    assert factory.get("medium") is factory.get("MEDIUM")
    assert builder.call_count == 1
    assert builder.call_args.args[1] == "gpt-5.6-terra"


@pytest.mark.parametrize("level,model", [
    ("low", "gpt-5.6-luna"), ("medium", "gpt-5.6-terra"),
    ("high", "gpt-5.6-sol"),
])
def test_modern_request_payload_offline(settings_factory, level, model):
    settings = settings_factory(openai_api_key="test-key")
    client = pick_llm(level, settings)
    payload = client._get_request_payload("Return hello")
    assert payload["model"] == model
    assert payload["reasoning"]["effort"] == "low"
    assert payload["max_output_tokens"] == 4096
    assert "temperature" not in payload
    assert "input" in payload
    assert client.output_version == "v0"


def test_legacy_override_retains_chat_parameters(settings_factory):
    client = pick_llm("low", settings_factory(
        openai_api_key="test-key", llm_model_low="gpt-4o", llm_temperature=0.2,
    ))
    payload = client._get_request_payload("hello")
    assert "messages" in payload
    assert payload["temperature"] == 0.2
    assert "reasoning" not in payload
