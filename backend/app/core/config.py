"""Конфигурация приложения: все значения берутся из env / .env."""

from enum import StrEnum
from functools import lru_cache
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderName(StrEnum):
    NONE = "none"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str = "postgresql+asyncpg://chess:chess@localhost:5432/chess_review"
    redis_url: str = "redis://localhost:6379/0"

    # До сессии 10 (auth) все запросы идут от имени этого пользователя.
    default_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    default_user_email: str = "dev@localhost"

    stockfish_path: str = "stockfish"
    engine_pool_size: int = Field(default=4, ge=1)
    engine_threads: int = Field(default=1, ge=1)
    engine_hash_mb: int = Field(default=128, ge=16)
    analysis_depth: int = Field(default=18, ge=1, le=40)
    analysis_multipv: int = Field(default=3, ge=1, le=5)

    llm_provider: LLMProviderName = LLMProviderName.NONE
    llm_model: str | None = None
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
