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
    # Таймаут анализа одной позиции; после него процесс перезапускается.
    engine_timeout_s: float = Field(default=60.0, gt=0)
    analysis_depth: int = Field(default=18, ge=1, le=40)
    analysis_multipv: int = Field(default=3, ge=1, le=5)
    # Партий одновременно в одном воркере (они делят пул движков).
    worker_max_jobs: int = Field(default=2, ge=1)
    # Анализ дольше этого считается зависшим и помечается failed.
    analysis_job_timeout_s: int = Field(default=1800, ge=60)

    # Импорт партий. Lichess отвечает 404 на дефолтные User-Agent библиотек
    # (curl/…, python-httpx/…) — нужен собственный.
    import_user_agent: str = "ChessReview/0.1 (self-hosted game review)"
    lichess_api_url: str = "https://lichess.org"
    # Необязателен: с токеном Lichess отдаёт партии быстрее (30 в секунду вместо 20).
    lichess_token: SecretStr | None = None
    chesscom_api_url: str = "https://api.chess.com"
    import_http_timeout_s: float = Field(default=30.0, gt=0)
    # Попыток на запрос при 429 / 5xx / сетевой ошибке.
    import_max_attempts: int = Field(default=3, ge=1)
    # Пауза после 429 без Retry-After: Lichess просит ждать минуту.
    import_rate_limit_wait_s: float = Field(default=60.0, ge=0)
    import_job_timeout_s: int = Field(default=1800, ge=60)

    llm_provider: LLMProviderName = LLMProviderName.NONE
    llm_model: str | None = None
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
