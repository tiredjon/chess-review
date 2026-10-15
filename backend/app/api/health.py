import asyncio

import structlog
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import DatabaseDep, RedisDep

router = APIRouter(tags=["health"])
log = structlog.get_logger(__name__)

CHECK_TIMEOUT_S = 2.0


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: процесс жив и отвечает, внешние зависимости не трогаем."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(db: DatabaseDep, redis: RedisDep, response: Response) -> dict[str, object]:
    """Readiness: доступны ли PostgreSQL и Redis."""

    async def check_db() -> None:
        async with db.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def check_redis() -> None:
        await redis.ping()

    checks: dict[str, str] = {}
    for name, check in (("database", check_db), ("redis", check_redis)):
        try:
            await asyncio.wait_for(check(), CHECK_TIMEOUT_S)
            checks[name] = "ok"
        except Exception as exc:
            log.warning("health.check_failed", check=name, error=repr(exc))
            checks[name] = "error"

    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "error", "checks": checks}
