from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    database_url: SecretStr | None = None
    database_schema: str = Field(default="public", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    sql_row_limit: int = Field(default=10, ge=1, le=100_000)
    sql_timeout_seconds: float = Field(default=30, gt=0, le=300)

    def require_database_url(self) -> str:
        if not self.database_url or not self.database_url.get_secret_value():
            raise ValueError("DATABASE_URL is required for database operations.")
        return self.database_url.get_secret_value()


@lru_cache
def get_config() -> Settings:
    return Settings()

