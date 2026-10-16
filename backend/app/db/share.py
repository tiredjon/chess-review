"""Публичные ссылки на разбор партии (`{PUBLIC_WEB_URL}/share/{token}`): ответ бота
и «Поделиться» в приложении. Токен — в `games.share_token`; без него партия не видна."""

import secrets

from app.core.config import Settings
from app.db.models import Game

# token_urlsafe(16) — 22 символа (колонка — 32): 128 бит, перебором не угадать.
SHARE_TOKEN_BYTES = 16


def new_share_token() -> str:
    return secrets.token_urlsafe(SHARE_TOKEN_BYTES)


def ensure_share_token(game: Game) -> str:
    """Токен партии: существующий или новый. Партию — заблокировать (`FOR UPDATE`),
    чтобы два запроса не выдали разные ссылки; коммит — за вызывающим."""
    if game.share_token is None:
        game.share_token = new_share_token()
    return game.share_token


def share_url(settings: Settings, token: str, *, ply: int | None = None) -> str:
    """Ссылка на страницу разбора; `ply` — открыть сразу на этом полуходе."""
    url = f"{settings.public_web_url.rstrip('/')}/share/{token}"
    return url if ply is None else f"{url}?ply={ply}"
