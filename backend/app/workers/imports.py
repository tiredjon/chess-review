"""ARQ-задача импорта партий с Lichess / Chess.com: страницы источника → `games`.

Каждая страница сохраняется отдельной транзакцией вместе со счётчиками задачи —
`GET /imports/{id}` показывает прогресс по ходу импорта. Повтор задачи (ARQ
перезапускает прерванные) начинает заново: уже сохранённые партии отсекаются
уникальным ключом, а не дублируются.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import update

from app.core.config import Settings
from app.db.models import GameSource, ImportJob, ImportStatus, User
from app.db.session import Database
from app.importers.chesscom import ChessComClient
from app.importers.http import RetryPolicy, SourceError
from app.importers.lichess import LichessClient
from app.importers.sources import SourceGame, convert_page
from app.importers.store import insert_games

log = structlog.get_logger(__name__)

TASK_NAME = "import_games"
ERROR_MAX_LEN = 500


def job_id(import_id: uuid.UUID) -> str:
    return f"import:{import_id}"


async def enqueue_import(arq: Any, import_id: uuid.UUID) -> None:
    """Ставит импорт в очередь ARQ; повторная постановка того же импорта игнорируется."""
    await arq.enqueue_job(TASK_NAME, str(import_id), _job_id=job_id(import_id))


def source_pages(
    job: ImportJob, settings: Settings, http: httpx.AsyncClient
) -> AsyncIterator[list[SourceGame]]:
    policy = RetryPolicy.from_settings(settings)
    if job.source == GameSource.LICHESS:
        token = settings.lichess_token.get_secret_value() if settings.lichess_token else None
        lichess = LichessClient(
            http, base_url=settings.lichess_api_url, token=token or None, policy=policy
        )
        return lichess.games(job.username, job.max_games or 1)
    if job.source == GameSource.CHESSCOM:
        chesscom = ChessComClient(http, base_url=settings.chesscom_api_url, policy=policy)
        return chesscom.games(job.username, job.months or 1, today=datetime.now(UTC).date())
    raise ValueError(f"Импорт из {job.source} не поддерживается")


async def import_games(ctx: dict[str, Any], import_id: str) -> str:
    """Задача ARQ. В `ctx`: settings, db, http (httpx.AsyncClient с User-Agent)."""
    settings: Settings = ctx["settings"]
    db: Database = ctx["db"]
    http: httpx.AsyncClient = ctx["http"]
    import_uuid = uuid.UUID(import_id)
    log_ = log.bind(import_id=import_id)

    async with db.sessionmaker() as session:
        job = await session.get(ImportJob, import_uuid)
        if job is None:
            log_.warning("import.missing")
            return "missing"
        if job.status == ImportStatus.DONE:
            return "done"
        user = await session.get(User, job.user_id)
        if user is None:  # pragma: no cover — каскад удаляет задачи вместе с пользователем
            return "missing"
        job.status = ImportStatus.RUNNING
        job.started_at = datetime.now(UTC)
        job.finished_at = None
        job.error = None
        job.fetched = job.imported = job.skipped = 0
        await session.commit()

    log_.info("import.started", source=job.source, username=job.username)
    try:
        async for page in source_pages(job, settings, http):
            # Разбор PGN и поиск дебюта — CPU.
            games = await asyncio.to_thread(convert_page, page, job.username)
            async with db.sessionmaker() as session:
                new = await insert_games(session, user, job.source, games)
                await session.execute(
                    update(ImportJob)
                    .where(ImportJob.id == import_uuid)
                    .values(
                        fetched=ImportJob.fetched + len(page),
                        imported=ImportJob.imported + new,
                        skipped=ImportJob.skipped + len(page) - len(games),
                    )
                )
                await session.commit()
        await _finish(db, job, user)
    except asyncio.CancelledError:
        await asyncio.shield(_fail(db, import_uuid, "Импорт прерван"))
        raise
    except SourceError as exc:
        log_.warning("import.source_failed", error=str(exc))
        await _fail(db, import_uuid, str(exc))
        return "failed"
    except Exception as exc:
        log_.exception("import.failed")
        await _fail(db, import_uuid, f"{type(exc).__name__}: {exc}")
        return "failed"
    log_.info("import.done")
    return "done"


async def _finish(db: Database, job: ImportJob, user: User) -> None:
    async with db.sessionmaker() as session:
        await session.execute(
            update(ImportJob)
            .where(ImportJob.id == job.id)
            .values(status=ImportStatus.DONE, finished_at=datetime.now(UTC))
        )
        # Первый импорт с площадки запоминает ник: по нему определяется цвет
        # пользователя во вставленных PGN. Уже заданный ник не перезаписывается.
        column = {
            GameSource.LICHESS: User.lichess_username,
            GameSource.CHESSCOM: User.chesscom_username,
        }[job.source]
        await session.execute(
            update(User).where(User.id == user.id, column.is_(None)).values({column: job.username})
        )
        await session.commit()


async def _fail(db: Database, import_id: uuid.UUID, error: str) -> None:
    async with db.sessionmaker() as session:
        await session.execute(
            update(ImportJob)
            .where(ImportJob.id == import_id)
            .values(
                status=ImportStatus.FAILED,
                error=error[:ERROR_MAX_LEN],
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()
