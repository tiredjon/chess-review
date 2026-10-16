"""Конфигурация приложения: все значения берутся из env / .env."""

import secrets
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BeforeValidator, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.rates import Rate


class LLMProviderName(StrEnum):
    NONE = "none"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


def _rate(value: object) -> object:
    return Rate.parse(value) if isinstance(value, str) else value


# NoDecode: в env — строка «30/hour», а не JSON (Rate — составной тип для pydantic-settings).
RateSetting = Annotated[Rate, NoDecode, BeforeValidator(_rate)]


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

    # Dev-пользователь из начальной миграции: до сессии 10 все запросы шли от него.
    # Первый зарегистрированный получает эту запись вместе с данными (AUTH_CLAIM_DEV_USER).
    default_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    default_user_email: str = "dev@localhost"

    # Auth (`app/auth/`). Без JWT_SECRET в dev/test ключ случайный на процесс: после
    # перезапуска API access-токены недействительны, сессии продлеваются refresh-токеном.
    jwt_secret: SecretStr | None = None
    access_token_ttl_s: int = Field(default=15 * 60, ge=30)
    refresh_token_ttl_days: int = Field(default=30, ge=1)
    # Повтор только что заменённого refresh-токена (две вкладки обновились разом)
    # в этом окне — 401 без отзыва сессии; позже — признак кражи, отзывается вся цепочка.
    refresh_reuse_grace_s: int = Field(default=10, ge=0)
    # Токен для EventSource (SSE не умеет заголовки): короткий и только на один анализ.
    stream_token_ttl_s: int = Field(default=60, ge=5)
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_claim_dev_user: bool = True

    # Лимиты «N/период» (период: s, m, h, d или second / minute / hour / day, можно
    # с числом: 10/30s). Импорт, анализ и LLM — на пользователя, вход и регистрация — на IP.
    rate_limit_enabled: bool = True
    rate_limit_import: RateSetting = Rate(30, 3600)
    rate_limit_analyze: RateSetting = Rate(100, 3600)
    rate_limit_llm: RateSetting = Rate(300, 3600)
    rate_limit_login: RateSetting = Rate(10, 60)
    rate_limit_register: RateSetting = Rate(10, 3600)
    # IP клиента из X-Forwarded-For (только за своим reverse proxy).
    trust_forwarded_for: bool = False

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
    llm_timeout_s: float = Field(default=30.0, gt=0)
    # Одновременных запросов к LLM при пакетном объяснении ходов разбора.
    llm_max_concurrency: int = Field(default=4, ge=1)

    @model_validator(mode="after")
    def _jwt_secret(self) -> "Settings":
        if self.jwt_secret is None or not self.jwt_secret.get_secret_value():
            if self.app_env == "prod":
                raise ValueError("JWT_SECRET обязателен при APP_ENV=prod")
            self.jwt_secret = SecretStr(secrets.token_urlsafe(32))
        return self

    @property
    def jwt_key(self) -> str:
        assert self.jwt_secret is not None
        return self.jwt_secret.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
