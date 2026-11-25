"""ARQ-задача сборки курса: `courses.status` queued → building → ready / failed.

Прогресс 0…100 пишется в `courses.progress` по ходу сборки (страница курса опрашивает
`GET /courses/{id}`). Курс общий для всех пользователей с той же линией и цветом, поэтому
собранный (`ready`) повторно не собирается. Повтор задачи (ARQ перезапускает прерванные)
собирает заново: Explorer и оценки движка уже в кэше БД, второй раз — быстро.

Ошибки — с кодом (`courses.error_code`): Lichess недоступен — `explorer_unavailable`, движок —
`engine_unavailable`, сборка дольше `course_job_timeout_s` — `interrupted`, прочее — `internal`.
Упавший курс можно поставить заново тем же `POST /courses`."""

import asyncio
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import chess
import structlog
from sqlalchemy import update

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.courses.builder import BuildLimits, CourseBuilder
from app.db.models import Color, Course, CourseStatus
from app.db.session import Database
from app.engine.analyzer import PositionEngine
from app.engine.cache import DbEvalCache
from app.engine.pool import EngineError
from app.explorer.cache import make_explorer
from app.explorer.types import ExplorerUnavailableError, OpeningExplorer

log = structlog.get_logger(__name__)

TASK_NAME = "build_course"


def job_id(course_id: uuid.UUID, *, retry: bool = False) -> str:
    """Id задачи ARQ. Повтор упавшего курса — с новым id: результат прежней задачи ARQ
    хранит час и не дал бы поставить задачу с тем же id."""
    base = f"course:{course_id}"
    return f"{base}:{secrets.token_hex(4)}" if retry else base


async def enqueue_course(arq: Any, course_id: uuid.UUID, *, retry: bool = False) -> None:
    """Ставит сборку в очередь; повторная постановка того же курса игнорируется ARQ."""
    await arq.enqueue_job(TASK_NAME, str(course_id), _job_id=job_id(course_id, retry=retry))


def _explorer(ctx: dict[str, Any]) -> OpeningExplorer:
    """Один Explorer на процесс воркера (пауза между запросами к Lichess — общая)."""
    if "explorer" not in ctx:
        ctx["explorer"] = make_explorer(ctx["settings"], ctx["http"], ctx["db"])
    explorer: OpeningExplorer = ctx["explorer"]
    return explorer


async def build_course(ctx: dict[str, Any], course_id: str) -> str:
    """Задача ARQ. В `ctx`: settings, db, engine (пул движков), http; explorer — создаётся
    при первой задаче (в тестах — подставляется фейк)."""
    settings: Settings = ctx["settings"]
    db: Database = ctx["db"]
    engine: PositionEngine = ctx["engine"]
    course_uuid = uuid.UUID(course_id)
    log_ = log.bind(course_id=course_id)

    async with db.sessionmaker() as session:
        course = await session.get(Course, course_uuid)
        if course is None:
            log_.warning("course.missing")
            return "missing"
        if course.status == CourseStatus.READY:
            return "ready"
        course.status = CourseStatus.BUILDING
        course.progress = 0
        course.error_code = None
        await session.commit()
        line = [chess.Move.from_uci(uci) for uci in course.line_uci]
        color = course.color == Color.WHITE

    async def progress(percent: int) -> None:
        # Последний шаг (100) пишет `_finish` вместе с деревом.
        if percent < 100:
            await _update(db, course_uuid, progress=percent)

    builder = CourseBuilder(
        _explorer(ctx),
        engine,
        limits=BuildLimits.from_settings(settings),
        cache=DbEvalCache(db.sessionmaker),
        progress=progress,
    )
    log_.info("course.started", line=" ".join(course.line_uci), color=course.color)
    try:
        async with asyncio.timeout(settings.course_job_timeout_s):
            tree = await builder.build(line, color)
    except asyncio.CancelledError:
        await asyncio.shield(_fail(db, course_uuid, ErrorCode.INTERRUPTED))
        raise
    except Exception as exc:
        await _fail(db, course_uuid, _error_code(exc, log_))
        return "failed"

    await _update(
        db,
        course_uuid,
        status=CourseStatus.READY,
        progress=100,
        tree=tree.model_dump(mode="json"),
        built_at=datetime.now(UTC),
        error_code=None,
    )
    log_.info("course.done", nodes=len(tree.nodes))
    return "ready"


def _error_code(exc: Exception, log_: Any) -> ErrorCode:
    if isinstance(exc, TimeoutError):
        log_.warning("course.timeout")
        return ErrorCode.INTERRUPTED
    if isinstance(exc, ExplorerUnavailableError):
        log_.warning("course.explorer_failed", error=str(exc))
        return ErrorCode.EXPLORER_UNAVAILABLE
    if isinstance(exc, EngineError | OSError):
        log_.warning("course.engine_failed", error=repr(exc))
        return ErrorCode.ENGINE_UNAVAILABLE
    log_.exception("course.failed")
    return ErrorCode.INTERNAL


async def _update(db: Database, course_id: uuid.UUID, **values: Any) -> None:
    async with db.sessionmaker() as session:
        await session.execute(update(Course).where(Course.id == course_id).values(**values))
        await session.commit()


async def _fail(db: Database, course_id: uuid.UUID, code: ErrorCode) -> None:
    await _update(db, course_id, status=CourseStatus.FAILED, error_code=code.value)
