"""Анализы: статус и результат, SSE-прогресс."""

import uuid
from collections.abc import AsyncIterator, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    BearerDep,
    CurrentUser,
    RedisDep,
    SessionDep,
    SettingsDep,
    get_current_user,
    load_user,
    token_error,
)
from app.api.errors import ApiError, ErrorCode
from app.api.schemas import AnalysisOut, MoveOut, Progress, StreamTokenOut
from app.auth.tokens import TokenError, create_token, decode_token
from app.db.models import Analysis, AnalysisStatus, Game, Move, User
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


async def _find_owned(session: AsyncSession, analysis_id: uuid.UUID, user: User) -> Analysis:
    analysis = await session.scalar(
        select(Analysis).join(Game).where(Analysis.id == analysis_id, Game.user_id == user.id)
    )
    if analysis is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.ANALYSIS_NOT_FOUND, "Анализ не найден")
    return analysis


async def owned_analysis(
    analysis_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Analysis:
    return await _find_owned(session, analysis_id, user)


OwnedAnalysis = Annotated[Analysis, Depends(owned_analysis)]


async def stream_analysis(
    analysis_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    credentials: BearerDep,
    token: Annotated[str | None, Query()] = None,
) -> Analysis:
    """Анализ для SSE: EventSource не умеет заголовки, поэтому вместо access-токена
    можно передать `?token=` из `POST /analyses/{id}/events/token` — короткоживущий
    и только для этого анализа (в логах прокси он бесполезен через минуту)."""
    if token is None:
        user = await get_current_user(session, settings, credentials)
    else:
        try:
            claims = decode_token(settings, token, "stream")
        except TokenError as exc:
            raise token_error(exc) from exc
        if claims.analysis_id != analysis_id:
            raise token_error(TokenError())
        user = await load_user(session, claims.user_id)
    return await _find_owned(session, analysis_id, user)


StreamAnalysis = Annotated[Analysis, Depends(stream_analysis)]


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
            select(Analysis.status, Analysis.error, Analysis.error_code).where(
                Analysis.id == analysis_id
            )
        )
    ).one()
    # Не держать соединение с БД, пока поток ждёт событий.
    await session.close()
    state = await read_state(redis, analysis_id)
    done, total = (state.done, state.total) if state is not None else (0, 0)
    return ProgressEvent(
        status=row.status, done=done, total=total, error=row.error, error_code=row.error_code
    )


def _sse(event: ProgressEvent) -> ServerSentEvent:
    return ServerSentEvent(data=event, event="progress")


@router.post("/analyses/{analysis_id}/events/token")
async def analysis_events_token(
    analysis: OwnedAnalysis, user: CurrentUser, settings: SettingsDep
) -> StreamTokenOut:
    """Токен для `GET /analyses/{id}/events?token=`: проверяется при подключении,
    поток живёт дольше токена."""
    return StreamTokenOut(
        token=create_token(settings, user.id, "stream", analysis_id=analysis.id),
        expires_in=settings.stream_token_ttl_s,
    )


@router.get("/analyses/{analysis_id}/events", response_class=EventSourceResponse)
async def analysis_events(
    analysis: StreamAnalysis, session: SessionDep, redis: RedisDep
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
