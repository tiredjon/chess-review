"""Анализы: статус и результат, SSE-прогресс."""

import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RedisDep, SessionDep
from app.api.schemas import AnalysisOut, MoveOut, Progress
from app.db.models import Analysis, AnalysisStatus, Game, Move
from app.workers.progress import ProgressEvent, channel, parse_message, read_state

router = APIRouter(tags=["analyses"])

# Как часто SSE-поток без событий перепроверяет статус в БД: событие могло потеряться
# (воркер упал, Redis перезапустился), а клиент не должен ждать вечно.
STATUS_RECHECK_S = 5.0

ACTIVE = (AnalysisStatus.QUEUED, AnalysisStatus.RUNNING)
# Поля AnalysisOut, которых нет у строки `analyses`.
_COMPUTED = frozenset({"moves", "progress"})


async def latest_analyses(
    session: AsyncSession, game_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Analysis]:
    """Последний анализ каждой партии."""
    if not game_ids:
        return {}
    rows = await session.scalars(
        select(Analysis)
        .where(Analysis.game_id.in_(game_ids))
        .order_by(Analysis.game_id, Analysis.created_at.desc(), Analysis.id)
        .ext(distinct_on(Analysis.game_id))
    )
    return {analysis.game_id: analysis for analysis in rows}


async def analysis_out(session: AsyncSession, redis: Redis, analysis: Analysis) -> AnalysisOut:
    """Анализ с ходами (если готов) или прогрессом (если идёт)."""
    # Поля — явно: `moves` у ORM-объекта — ленивая связь, её нельзя трогать в async.
    fields: dict[str, Any] = {
        name: getattr(analysis, name) for name in AnalysisOut.model_fields.keys() - _COMPUTED
    }
    if analysis.status == AnalysisStatus.DONE:
        moves = await session.scalars(
            select(Move).where(Move.analysis_id == analysis.id).order_by(Move.ply)
        )
        fields["moves"] = [MoveOut.model_validate(move) for move in moves]
    elif analysis.status in ACTIVE:
        state = await read_state(redis, analysis.id)
        if state is not None and state.total:
            fields["progress"] = Progress(done=state.done, total=state.total)
    return AnalysisOut.model_validate(fields)


async def owned_analysis(
    analysis_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Analysis:
    analysis = await session.scalar(
        select(Analysis).join(Game).where(Analysis.id == analysis_id, Game.user_id == user.id)
    )
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Анализ не найден")
    return analysis


OwnedAnalysis = Annotated[Analysis, Depends(owned_analysis)]


@router.get("/analyses/{analysis_id}")
async def get_analysis(
    analysis: OwnedAnalysis, session: SessionDep, redis: RedisDep
) -> AnalysisOut:
    return await analysis_out(session, redis, analysis)


async def _current_event(
    session: AsyncSession, redis: Redis, analysis_id: uuid.UUID
) -> ProgressEvent:
    """Состояние анализа: статус — из БД (источник истины), счётчики — из Redis."""
    row = (
        await session.execute(
            select(Analysis.status, Analysis.error).where(Analysis.id == analysis_id)
        )
    ).one()
    # Не держать соединение с БД, пока поток ждёт событий.
    await session.close()
    state = await read_state(redis, analysis_id)
    done, total = (state.done, state.total) if state is not None else (0, 0)
    return ProgressEvent(status=row.status, done=done, total=total, error=row.error)


def _sse(event: ProgressEvent) -> ServerSentEvent:
    return ServerSentEvent(data=event, event="progress")


@router.get("/analyses/{analysis_id}/events", response_class=EventSourceResponse)
async def analysis_events(
    analysis: OwnedAnalysis, session: SessionDep, redis: RedisDep
) -> AsyncIterator[ServerSentEvent]:
    """SSE: события `progress` с `{status, done, total, error}`; поток закрывается
    после финального статуса (done / failed)."""
    pubsub = redis.pubsub()
    # Подписка до чтения состояния: событие между ними не потеряется.
    await pubsub.subscribe(channel(analysis.id))
    try:
        event = await _current_event(session, redis, analysis.id)
        yield _sse(event)
        while not event.is_final:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=STATUS_RECHECK_S
            )
            if message is not None:
                event = parse_message(message)
                yield _sse(event)
                continue
            current = await _current_event(session, redis, analysis.id)
            if current.is_final or current.status != event.status:
                event = current
                yield _sse(event)
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()  # type: ignore[no-untyped-call]
