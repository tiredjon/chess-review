"""HTTP для импорта с Lichess / Chess.com: общий клиент, ошибки источника, повторы.

Повторяются 429 (пауза из Retry-After, иначе `rate_limit_wait_s` — Lichess просит
ждать минуту), 5xx и сетевые ошибки (пауза растёт вдвое). Остальные ответы
возвращаются как есть: 404 и прочее разбирает клиент источника.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.core.config import Settings

log = structlog.get_logger(__name__)


class SourceError(Exception):
    """Источник не отдал партии. Текст показывается пользователю в статусе импорта."""


class UserNotFoundError(SourceError):
    pass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    rate_limit_wait_s: float = 60.0
    backoff_s: float = 1.0
    sleep: Callable[[float], Awaitable[None]] = field(default=asyncio.sleep)

    @classmethod
    def from_settings(cls, settings: Settings) -> "RetryPolicy":
        return cls(
            attempts=settings.import_max_attempts,
            rate_limit_wait_s=settings.import_rate_limit_wait_s,
        )


def make_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": settings.import_user_agent},
        timeout=settings.import_http_timeout_s,
    )


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After", "")
    return float(value) if value.isdigit() else None


async def get_with_retry(
    http: httpx.AsyncClient,
    url: str,
    *,
    source: str,
    policy: RetryPolicy,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    """GET с повторами; после последней неудачной попытки — SourceError."""
    for attempt in range(1, policy.attempts + 1):
        backoff = policy.backoff_s * 2 ** (attempt - 1)
        try:
            response = await http.get(url, params=params, headers=headers)
        except httpx.TransportError as exc:
            problem, wait = f"{source} недоступен ({type(exc).__name__})", backoff
        else:
            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                problem = f"{source}: превышен лимит запросов"
                wait = _retry_after(response) or policy.rate_limit_wait_s
            elif response.status_code >= 500:
                problem, wait = f"{source}: ошибка сервера {response.status_code}", backoff
            else:
                return response
        if attempt == policy.attempts:
            raise SourceError(problem)
        log.warning("import.http_retry", url=url, problem=problem, attempt=attempt, wait_s=wait)
        await policy.sleep(wait)
    raise AssertionError("unreachable")  # pragma: no cover
