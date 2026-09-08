from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTIC_API_",
        env_file=".env",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8088
    log_level: str = "INFO"
    max_context_bytes: int = Field(default=1_000_000, ge=10_000)
    max_scenarios: int = Field(default=250, ge=10, le=2_000)
    model_provider: Literal["disabled", "openai"] = "disabled"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "AGENTIC_API_OPENAI_API_KEY"),
    )
    openai_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_MODEL", "AGENTIC_API_OPENAI_MODEL"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
