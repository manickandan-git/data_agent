from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    openai_api_key: str = Field(..., description="API key for OpenAI")
    anthropic_api_key: str = Field(..., description="API key for Anthropic")


@lru_cache
def get_config() -> Settings:
    return Settings()

