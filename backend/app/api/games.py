"""Партии: импорт PGN, список, карточка, запуск анализа."""

import asyncio
import base64
import binascii
import json
import uuid
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Body, Query, Response, status
from sqlalchemy import Select, and_, or_, select

from app.api.analyses import analysis_out, latest_analyses
from app.api.deps import ArqDep, CurrentUser, RedisDep, SessionDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import UserLimiterDep, limit_user
from app.api.schemas import (
    AnalysisOut,
    AnalysisSummary,
    AnalyzeIn,
    GameDetail,
    GameOut,
    GamePage,
    PgnImportIn,
)
from app.db.models import Analysis, AnalysisRunner, AnalysisStatus, Game, GameSource
from app.importers.pgn import PgnError, parse_pgn
from app.importers.store import save_games
from app.workers.analysis import enqueue_analysis

router = APIRouter(tags=["games"])
log = structlog.get_logger(__name__)


def _game_out(game: Game, analysis: Analysis | None) -> GameOut:
    result = GameOut.model_validate(game)
    if analysis is not None:
        result.analysis = AnalysisSummary.model_validate(analysis)
    return result


@router.post("/games/pgn", dependencies=[limit_user("import")])
async def import_pgn(body: PgnImportIn, session: SessionDep, user: CurrentUser) -> list[GameOut]:
    """Импорт одной или нескольких партий из PGN. Повторный импорт той же партии
    возвращает уже сохранённую."""
    try:
        # Разбор и поиск дебюта — CPU; первый вызов ещё и грузит базу дебютов.
        parsed = await asyncio.to_thread(parse_pgn, body.pgn)
    except PgnError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode(exc.code), str(exc), params=exc.params
        ) from exc
    games = await save_games(session, user, GameSource.PGN, parsed)
    await session.commit()
    latest = await latest_analyses(session, [game.id for game in games])
    return [_game_out(game, latest.get(game.id)) for game in games]


def encode_cursor(game: Game) -> str:
    payload = {"p": game.played_at.isoformat() if game.played_at else None, "id": str(game.id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime | None, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        payload = json.loads(raw)
        played = datetime.fromisoformat(payload["p"]) if payload["p"] is not None else None
        return played, uuid.UUID(payload["id"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_CURSOR, "Некорректный cursor"
        ) from exc


def _after_cursor(stmt: Select[Game], cursor: str) -> Select[Game]:
    """Партии после курсора в порядке (played_at DESC NULLS LAST, id DESC)."""
    played, game_id = decode_cursor(cursor)
    if played is None:
        return stmt.where(Game.played_at.is_(None), Game.id < game_id)
    return stmt.where(
        or_(
            Game.played_at < played,
            and_(Game.played_at == played, Game.id < game_id),
            Game.played_at.is_(None),
        )
    )


@router.get("/games")
async def list_games(
    session: SessionDep,
    user: CurrentUser,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    source: GameSource | None = None,
) -> GamePage:
    """Партии пользователя, новые первыми; партии без даты — в конце."""
    stmt = select(Game).where(Game.user_id == user.id)
    if source is not None:
        stmt = stmt.where(Game.source == source)
    if cursor:
        stmt = _after_cursor(stmt, cursor)
    stmt = stmt.order_by(Game.played_at.desc().nulls_last(), Game.id.desc()).limit(limit + 1)
    games = list(await session.scalars(stmt))
    page, more = games[:limit], len(games) > limit
    latest = await latest_analyses(session, [game.id for game in page])
    return GamePage(
        items=[_game_out(game, latest.get(game.id)) for game in page],
        next_cursor=encode_cursor(page[-1]) if more else None,
    )


async def _owned_game(
    session: SessionDep, user: CurrentUser, game_id: uuid.UUID, *, lock: bool = False
) -> Game:
    stmt = select(Game).where(Game.id == game_id, Game.user_id == user.id)
    game = await session.scalar(stmt.with_for_update() if lock else stmt)
    if game is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.GAME_NOT_FOUND, "Партия не найдена")
    return game


@router.get("/games/{game_id}")
async def get_game(
    game_id: uuid.UUID, session: SessionDep, redis: RedisDep, user: CurrentUser
) -> GameDetail:
    """Партия и её последний анализ (с ходами, если он готов)."""
    game = await _owned_game(session, user, game_id)
    result = GameDetail.model_validate(game)
    analysis = (await latest_analyses(session, [game.id])).get(game.id)
    if analysis is not None:
        result.analysis = await analysis_out(session, redis, analysis)
    return result


@router.post("/games/{game_id}/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_game(
    game_id: uuid.UUID,
    *,
    session: SessionDep,
    arq: ArqDep,
    user: CurrentUser,
    settings: SettingsDep,
    limiter: UserLimiterDep,
    response: Response,
    body: Annotated[AnalyzeIn | None, Body()] = None,
) -> AnalysisOut:
    """Ставит анализ в очередь. Если серверный анализ той же глубины уже в очереди, идёт
    или готов — возвращает его (200), новый не создаётся."""
    depth = body.depth if body is not None and body.depth is not None else settings.analysis_depth
    # Блокировка партии: двойной клик не создаст два анализа.
    game = await _owned_game(session, user, game_id, lock=True)
    existing = await session.scalar(
        select(Analysis)
        .where(
            Analysis.game_id == game.id,
            Analysis.depth == depth,
            Analysis.status != AnalysisStatus.FAILED,
            # Анализ из браузера (другая сеть движка) не заменяет серверный.
            Analysis.runner == AnalysisRunner.SERVER,
        )
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        await session.commit()
        if existing.status == AnalysisStatus.QUEUED:
            # Задача могла потеряться (Redis очищен); ARQ не дублирует задачу с тем же id.
            await enqueue_analysis(arq, existing.id)
        response.status_code = status.HTTP_200_OK
        return await analysis_out(session, arq, existing)

    # Лимит — только на новый анализ: открыть уже идущий или готовый можно всегда.
    await limiter.hit("analyze")
    analysis = Analysis(game_id=game.id, depth=depth, status=AnalysisStatus.QUEUED)
    session.add(analysis)
    await session.commit()
    try:
        await enqueue_analysis(arq, analysis.id)
    except Exception as exc:
        log.exception("analysis.enqueue_failed", analysis_id=str(analysis.id))
        analysis.status = AnalysisStatus.FAILED
        analysis.error = "Не удалось поставить анализ в очередь"
        analysis.error_code = ErrorCode.ENQUEUE_FAILED
        await session.commit()
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorCode.QUEUE_UNAVAILABLE,
            "Очередь анализа недоступна",
        ) from exc
    await session.refresh(analysis)
    return await analysis_out(session, arq, analysis)
