"""Импорт партий с Lichess / Chess.com: постановка задачи воркеру и её статус."""

import uuid

import structlog
from fastapi import APIRouter, Response, status
from sqlalchemy import func, select

from app.api.deps import ArqDep, CurrentUser, SessionDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import UserLimiter, UserLimiterDep
from app.api.schemas import ChessComImportIn, ImportJobOut, LichessImportIn
from app.db.models import GameSource, ImportJob, ImportStatus, User
from app.workers.imports import enqueue_import

router = APIRouter(tags=["imports"])
log = structlog.get_logger(__name__)

ACTIVE = (ImportStatus.QUEUED, ImportStatus.RUNNING)


async def _start_import(
    session: SessionDep,
    arq: ArqDep,
    *,
    user: User,
    response: Response,
    job: ImportJob,
    limiter: UserLimiter,
) -> ImportJobOut:
    """Ставит импорт в очередь. Если импорт того же ника с той же площадки уже
    в очереди или идёт — возвращает его (200), новый не создаётся."""
    # Блокировка пользователя: двойной клик не создаст два импорта.
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    existing = await session.scalar(
        select(ImportJob)
        .where(
            ImportJob.user_id == user.id,
            ImportJob.source == job.source,
            func.lower(ImportJob.username) == job.username.lower(),
            ImportJob.status.in_(ACTIVE),
        )
        .order_by(ImportJob.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        await session.commit()
        if existing.status == ImportStatus.QUEUED:
            # Задача могла потеряться (Redis очищен); ARQ не дублирует задачу с тем же id.
            await enqueue_import(arq, existing.id)
        response.status_code = status.HTTP_200_OK
        return ImportJobOut.model_validate(existing)

    # Лимит — только на новый импорт: повторный клик возвращает идущий.
    await limiter.hit("import")
    session.add(job)
    await session.commit()
    try:
        await enqueue_import(arq, job.id)
    except Exception as exc:
        log.exception("import.enqueue_failed", import_id=str(job.id))
        job.status = ImportStatus.FAILED
        job.error = "Не удалось поставить импорт в очередь"
        job.error_code = ErrorCode.ENQUEUE_FAILED
        await session.commit()
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorCode.QUEUE_UNAVAILABLE,
            "Очередь импорта недоступна",
        ) from exc
    await session.refresh(job)
    return ImportJobOut.model_validate(job)


@router.post("/imports/lichess", status_code=status.HTTP_202_ACCEPTED)
async def import_lichess(
    body: LichessImportIn,
    *,
    session: SessionDep,
    arq: ArqDep,
    user: CurrentUser,
    limiter: UserLimiterDep,
    response: Response,
) -> ImportJobOut:
    """Импорт последних `max` партий пользователя Lichess (в фоне)."""
    job = ImportJob(
        user_id=user.id, source=GameSource.LICHESS, username=body.username, max_games=body.max
    )
    return await _start_import(session, arq, user=user, response=response, job=job, limiter=limiter)


@router.post("/imports/chesscom", status_code=status.HTTP_202_ACCEPTED)
async def import_chesscom(
    body: ChessComImportIn,
    *,
    session: SessionDep,
    arq: ArqDep,
    user: CurrentUser,
    limiter: UserLimiterDep,
    response: Response,
) -> ImportJobOut:
    """Импорт партий пользователя Chess.com за `months` последних месяцев (в фоне)."""
    job = ImportJob(
        user_id=user.id, source=GameSource.CHESSCOM, username=body.username, months=body.months
    )
    return await _start_import(session, arq, user=user, response=response, job=job, limiter=limiter)


@router.get("/imports/{job_id}")
async def get_import(job_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> ImportJobOut:
    """Статус и счётчики импорта (для полинга)."""
    job = await session.scalar(
        select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user.id)
    )
    if job is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.IMPORT_NOT_FOUND, "Импорт не найден")
    return ImportJobOut.model_validate(job)
