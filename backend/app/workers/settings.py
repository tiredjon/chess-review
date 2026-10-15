"""Настройки ARQ-воркера: `arq app.workers.settings.WorkerSettings`."""

from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import Database
from app.engine.probe import stockfish_version

log = structlog.get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings)
    # Без движка воркер бесполезен — падаем сразу и громко.
    ctx["engine_version"] = await stockfish_version(settings.stockfish_path)
    ctx["db"] = Database(settings.database_url)
    log.info("worker.startup", engine=ctx["engine_version"])


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["db"].dispose()
    log.info("worker.shutdown")


async def ping(ctx: dict[str, Any]) -> str:
    """Проверочная задача; реальные задачи анализа появятся в сессии 5."""
    return "pong"


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ping]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
