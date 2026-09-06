from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SOURCE_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = (SOURCE_ROOT / ".env", Path.cwd() / ".env")
Environment = Literal["development", "test", "staging", "production"]


def environment_files(environment: str) -> tuple[Path, ...]:
    """Return base and profile files in increasing precedence order."""
    roots = (SOURCE_ROOT, Path.cwd())
    candidates = [path for root in roots for path in (root / ".env", root / f".env.{environment}")]
    return tuple(dict.fromkeys(candidates))


class EnvironmentSelector(BaseSettings):
    """Resolve the profile before validating the complete configuration."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_environment: Environment = "development"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_environment: Environment = "development"
    llm_provider: str = "openai"
    llm_model_low: str | None = None
    llm_model_medium: str | None = None
    llm_model_high: str | None = None
    llm_temperature: float = Field(default=0, ge=0, le=1)
    llm_timeout_seconds: float = Field(default=60, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_max_tokens: int = Field(default=4096, gt=0)
    openai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "low"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    observability_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    observability_json_logs: bool = True
    otel_enabled: bool = False
    otel_service_name: str = Field(default="data-agent", min_length=1, max_length=128)
    otel_exporter_endpoint: str | None = None
    otel_metrics_exporter_endpoint: str | None = None
    otel_export_timeout_seconds: float = Field(default=10, gt=0, le=60)
    otel_metric_export_interval_seconds: float = Field(default=60, ge=5, le=300)
    otel_trace_sample_ratio: float = Field(default=1, ge=0, le=1)
    otel_excluded_urls: str = "/health"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65_535)
    api_workers: int = Field(default=1, ge=1, le=32)
    api_reload: bool = False
    api_docs_enabled: bool | None = None
    api_auth_enabled: bool | None = None
    api_keys: SecretStr | None = None
    api_rate_limit_requests: int = Field(default=60, ge=1, le=100_000)
    api_rate_limit_window_seconds: float = Field(default=60, ge=1, le=3_600)
    api_max_concurrent_requests: int = Field(default=4, ge=1, le=1_000)
    api_max_request_bytes: int = Field(default=16_384, ge=1_024, le=1_048_576)
    database_url: SecretStr | None = None
    database_schema: str = Field(default="public", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    sql_row_limit: int = Field(default=10, ge=1, le=100_000)
    sql_timeout_seconds: float = Field(default=30, gt=0, le=300)
    sql_categorical_value_limit: int = Field(default=50, ge=1, le=200)
    sql_categorical_columns: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "payments": ["payment_method", "payment_status"],
            "ratings": ["rating"],
            "rides": ["status", "cancellation_reason"],
            "users": ["user_type", "city", "province", "is_active"],
            "vehicles": ["make", "model", "color", "is_active"],
        }
    )
    etl_timeout_seconds: float = Field(default=30, gt=0, le=120)
    etl_max_retries: int = Field(default=2, ge=0, le=5)
    etl_max_pages: int = Field(default=20, ge=1, le=100)
    etl_max_rows: int = Field(default=100_000, ge=1, le=1_000_000)
    etl_bearer_token: SecretStr | None = None
    etl_auth_origin: str = ""

    @field_validator("sql_categorical_columns")
    @classmethod
    def validate_categorical_columns(cls, value):
        import re

        identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        if any(not identifier.fullmatch(table) for table in value):
            raise ValueError("Categorical table names must be SQL identifiers.")
        if any(
            not identifier.fullmatch(column) for columns in value.values() for column in columns
        ):
            raise ValueError("Categorical column names must be SQL identifiers.")
        if any(len(columns) != len(set(columns)) for columns in value.values()):
            raise ValueError("Categorical column names must be unique per table.")
        return value

    @model_validator(mode="after")
    def validate_environment_safety(self) -> Self:
        if self.api_reload and self.api_workers != 1:
            raise ValueError("API_RELOAD requires API_WORKERS=1.")
        if self.app_environment in {"staging", "production"} and self.api_reload:
            raise ValueError("API_RELOAD must be disabled in staging and production.")
        if self.app_environment == "production" and self.observability_log_level == "DEBUG":
            raise ValueError("DEBUG logging must be disabled in production.")
        if self.otel_enabled and not self.otel_exporter_endpoint:
            raise ValueError("OTEL_EXPORTER_ENDPOINT is required when OTEL_ENABLED=true.")
        if self.api_docs_enabled is None:
            self.api_docs_enabled = self.app_environment != "production"
        if self.api_auth_enabled is None:
            self.api_auth_enabled = self.app_environment == "production"
        if self.app_environment == "production" and not self.api_auth_enabled:
            raise ValueError("API authentication cannot be disabled in production.")
        if self.api_auth_enabled:
            keys = self.configured_api_keys()
            if not keys:
                raise ValueError("API_KEYS is required when API authentication is enabled.")
            if any(len(key) < 32 for key in keys):
                raise ValueError("Every API key must contain at least 32 characters.")
        return self

    def configured_api_keys(self) -> tuple[str, ...]:
        """Return configured bearer keys without exposing them in model output."""
        if not self.api_keys:
            return ()
        return tuple(
            key.strip() for key in self.api_keys.get_secret_value().split(",") if key.strip()
        )

    def require_database_url(self) -> str:
        if not self.database_url or not self.database_url.get_secret_value():
            raise ValueError("DATABASE_URL is required for database operations.")
        return self.database_url.get_secret_value()


@lru_cache
def get_config() -> Settings:
    bootstrap = EnvironmentSelector(_env_file=ENV_FILES)
    return Settings(_env_file=environment_files(bootstrap.app_environment))
