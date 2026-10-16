"""Лимиты запросов в Redis: фиксированное окно на (вид лимита, пользователь или IP).

Ключ `rl:{scope}:{subject}:{номер окна}` — счётчик INCR с TTL окна. Превышение — 429
с `Retry-After` (секунды до конца окна) и `params` для текста в интерфейсе.
Недоступный Redis лимит не применяет (логируется): лимиты — защита, а не условие работы.
"""

import math
import time
from typing import Annotated, Any, Literal

import structlog
from fastapi import Depends, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.deps import CurrentUser, RedisDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.core.config import Settings
from app.core.rates import Rate

log = structlog.get_logger(__name__)

Scope = Literal["import", "analyze", "llm", "login", "register", "browser", "explore", "bot"]


def rate_for(settings: Settings, scope: Scope) -> Rate:
    rate: Rate = getattr(settings, f"rate_limit_{scope}")
    return rate


async def hit(
    redis: Redis, settings: Settings, scope: Scope, subject: str, *, now: float | None = None
) -> None:
    """Засчитывает запрос; сверх лимита — ApiError 429."""
    if not settings.rate_limit_enabled:
        return
    rate = rate_for(settings, scope)
    now = time.time() if now is None else now
    window = int(now // rate.period_s)
    key = f"rl:{scope}:{subject}:{window}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, rate.period_s + 1, nx=True)
            count, _ = await pipe.execute()
    except RedisError as exc:
        log.warning("ratelimit.redis_failed", scope=scope, error=repr(exc))
        return
    if count <= rate.limit:
        return
    retry_after = max(1, math.ceil((window + 1) * rate.period_s - now))
    log.info("ratelimit.exceeded", scope=scope, subject=subject, retry_after=retry_after)
    raise ApiError(
        status.HTTP_429_TOO_MANY_REQUESTS,
        ErrorCode.RATE_LIMITED,
        f"Слишком много запросов ({scope}): не больше {rate.limit} за {rate.period_s} с. "
        f"Повторите через {retry_after} с.",
        params={
            "scope": scope,
            "limit": rate.limit,
            "period_s": rate.period_s,
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        if first := forwarded.split(",")[0].strip():
            return first
    return request.client.host if request.client else "unknown"


class UserLimiter:
    """Лимит на текущего пользователя; вызывается из роута, когда запрос точно что-то
    стоит (например, анализ создаётся, а не возвращается уже готовый)."""

    def __init__(self, redis: Redis, settings: Settings, user: CurrentUser) -> None:
        self._redis, self._settings, self._user = redis, settings, user

    async def hit(self, scope: Scope) -> None:
        await hit(self._redis, self._settings, scope, str(self._user.id))


def get_user_limiter(redis: RedisDep, settings: SettingsDep, user: CurrentUser) -> UserLimiter:
    return UserLimiter(redis, settings, user)


UserLimiterDep = Annotated[UserLimiter, Depends(get_user_limiter)]


def limit_user(scope: Scope) -> Any:
    """Зависимость роута: лимит `scope` на пользователя для каждого запроса."""

    async def dependency(limiter: UserLimiterDep) -> None:
        await limiter.hit(scope)

    return Depends(dependency)


def limit_ip(scope: Scope) -> Any:
    """Зависимость роута: лимит `scope` на IP клиента (вход, регистрация)."""

    async def dependency(request: Request, redis: RedisDep, settings: SettingsDep) -> None:
        await hit(redis, settings, scope, client_ip(request, settings))

    return Depends(dependency)


async def limit_llm(request: Request, limiter: UserLimiterDep) -> None:
    """Лимит LLM: только когда объяснения пишет модель. Шаблоны (LLM_PROVIDER=none)
    мгновенные и бесплатные — их не режем."""
    if request.app.state.llm is not None:
        await limiter.hit("llm")


LimitLLM = Depends(limit_llm)
