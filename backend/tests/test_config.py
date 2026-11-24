"""Конфигурация: в prod API не стартует с небезопасными значениями."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SAFE_PROD: dict[str, Any] = {
    "app_env": "prod",
    "jwt_secret": "x" * 44,
    "cookie_secure": True,
    "cors_origins": ["https://review.example.org"],
    "public_web_url": "https://review.example.org",
    "auth_claim_dev_user": False,
    "rate_limit_enabled": True,
    "database_url": "postgresql+asyncpg://chess:s3cret-pass@postgres:5432/chess_review",
}


def prod(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **{**SAFE_PROD, **overrides})


def test_safe_prod_config_starts() -> None:
    assert prod().app_env == "prod"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"jwt_secret": None}, "JWT_SECRET обязателен"),
        ({"jwt_secret": "short"}, "JWT_SECRET короче"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"cors_origins": ["http://review.example.org"]}, "CORS_ORIGINS"),
        ({"cors_origins": ["https://localhost:3000"]}, "CORS_ORIGINS"),
        ({"public_web_url": "http://localhost:3000"}, "PUBLIC_WEB_URL"),
        ({"auth_claim_dev_user": True}, "AUTH_CLAIM_DEV_USER"),
        ({"rate_limit_enabled": False}, "RATE_LIMIT_ENABLED"),
        (
            {"database_url": "postgresql+asyncpg://chess:chess@postgres:5432/chess_review"},
            "POSTGRES_PASSWORD",
        ),
    ],
)
def test_unsafe_prod_config_is_rejected(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        prod(**overrides)


def test_dev_defaults_are_allowed_outside_prod() -> None:
    settings = Settings(_env_file=None, app_env="dev")
    assert not settings.cookie_secure
    assert settings.auth_claim_dev_user
