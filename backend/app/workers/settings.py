"""Настройки ARQ-воркера: `arq app.workers.settings.WorkerSettings`."""

from typing import Any, ClassVar

import structlog
from arq import func
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import Database
from app.engine.pool import EnginePool
from app.workers.analysis import TASK_NAME, analyze_game

log = structlog.get_logger(__name__)

settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(settings)
    # Без движка воркер бесполезен — пул запускается сразу и падает громко.
    pool = EnginePool.from_settings(settings)
    await pool.start()
    ctx["settings"] = settings
    ctx["engine"] = pool
    ctx["engine_version"] = pool.version
    ctx["db"] = Database(settings.database_url)
    log.info("worker.startup", engine=pool.version, pool=pool.size)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].close()
    await ctx["db"].dispose()
    log.info("worker.shutdown")


class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        func(analyze_game, name=TASK_NAME, timeout=settings.analysis_job_timeout_s, max_tries=3),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.worker_max_jobs
