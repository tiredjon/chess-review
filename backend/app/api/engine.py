"""Движок для клиента (сессия 11): настройки анализа для браузерного движка и оценка
любой позиции для режима исследования на доске разбора.

Исследование через API считает свой небольшой пул Stockfish в процессе API
(`LazyEnginePool`, `EXPLORE_POOL_SIZE`): через очередь воркера ответ ждал бы окончания
анализов партий, а здесь нужна секунда-другая. Оценки берутся из общего кэша
`position_evals` и пишутся в него (они серверные — им можно доверять).
"""

from typing import Annotated

import chess
import structlog
from fastapi import APIRouter, Depends, Request, status

from app.api.deps import CurrentUser, DatabaseDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import limit_user
from app.api.schemas import EngineConfigOut, ExploreIn, ExploreLineOut, ExploreOut
from app.engine.analyzer import Analyzer, PositionEngine
from app.engine.cache import DbEvalCache
from app.engine.pool import EngineError
from app.workers.serialize import engine_line_json

router = APIRouter(tags=["engine"])
log = structlog.get_logger(__name__)


def get_explore_engine(request: Request) -> PositionEngine:
    engine: PositionEngine = request.app.state.explore_engine
    return engine


ExploreEngineDep = Annotated[PositionEngine, Depends(get_explore_engine)]


@router.get("/engine/config")
async def engine_config(settings: SettingsDep, user: CurrentUser) -> EngineConfigOut:
    """Глубина и MultiPV анализа — браузерный движок считает так же, как воркер."""
    return EngineConfigOut(
        analysis_depth=settings.analysis_depth,
        analysis_multipv=settings.analysis_multipv,
        browser_min_depth=settings.browser_min_depth,
        explore_depth=settings.explore_depth,
    )


@router.post("/engine/analyse", dependencies=[limit_user("explore")])
async def analyse_position(
    body: ExploreIn, settings: SettingsDep, db: DatabaseDep, engine: ExploreEngineDep
) -> ExploreOut:
    """Оценка и лучшая линия позиции на глубине `EXPLORE_DEPTH`."""
    try:
        board = chess.Board(body.fen)
    except ValueError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, "Некорректный FEN"
        ) from exc
    if not board.is_valid():
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, "Невозможная позиция"
        )
    analyzer = Analyzer(engine, DbEvalCache(db.sessionmaker))
    try:
        result = await analyzer.analyse(board, depth=settings.explore_depth, multipv=1)
    except (EngineError, OSError) as exc:
        log.warning("explore.engine_failed", error=repr(exc))
        raise ApiError(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            ErrorCode.ENGINE_UNAVAILABLE,
            "Движок недоступен",
        ) from exc
    return ExploreOut(
        fen=body.fen,
        depth=result.depth,
        lines=[ExploreLineOut(**engine_line_json(board, line)) for line in result.lines],
    )
