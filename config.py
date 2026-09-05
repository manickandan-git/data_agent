from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
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
    api_max_request_bytes: int = Field(default=16_384, ge=1_024, le=1_048_576)
    database_url: SecretStr | None = None
    database_schema: str = Field(default="public", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    sql_row_limit: int = Field(default=10, ge=1, le=100_000)
    sql_timeout_seconds: float = Field(default=30, gt=0, le=300)
    sql_categorical_value_limit: int = Field(default=50, ge=1, le=200)
    sql_categorical_columns: dict[str, list[str]] = Field(default_factory=lambda: {
        "payments": ["payment_method", "payment_status"],
        "ratings": ["rating"],
        "rides": ["status", "cancellation_reason"],
        "users": ["user_type", "city", "province", "is_active"],
        "vehicles": ["make", "model", "color", "is_active"],
    })
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
        if any(not identifier.fullmatch(column) for columns in value.values() for column in columns):
            raise ValueError("Categorical column names must be SQL identifiers.")
        if any(len(columns) != len(set(columns)) for columns in value.values()):
            raise ValueError("Categorical column names must be unique per table.")
        return value

    def require_database_url(self) -> str:
        if not self.database_url or not self.database_url.get_secret_value():
            raise ValueError("DATABASE_URL is required for database operations.")
        return self.database_url.get_secret_value()


@lru_cache
def get_config() -> Settings:
    return Settings()

