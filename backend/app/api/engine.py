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
from app.api.schemas import (
    ClassifyIn,
    ClassifyOut,
    EngineConfigOut,
    ExploreIn,
    ExploreLineOut,
    ExploreOut,
)
from app.engine.analyzer import PositionEngine
from app.engine.cache import DbEvalCache, fen_key
from app.engine.external import ExternalEvalError, game_evals
from app.engine.pool import EngineError
from app.review.classify import classify_move
from app.review.evaluate import evaluate_game, replay, terminal_eval
from app.review.openings import default_openings
from app.workers.serialize import engine_line_json, split_score

# Линий в режиме исследования — как в анализе Chess.com.
EXPLORE_LINES = 3

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


def _board(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, "Некорректный FEN"
        ) from exc
    if not board.is_valid():
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, "Невозможная позиция"
        )
    return board


@router.post("/engine/analyse", dependencies=[limit_user("explore")])
async def analyse_position(
    body: ExploreIn, settings: SettingsDep, db: DatabaseDep, engine: ExploreEngineDep
) -> ExploreOut:
    """Оценка и до трёх лучших линий позиции на глубине `EXPLORE_DEPTH`."""
    board = _board(body.fen)
    cache = DbEvalCache(db.sessionmaker)
    depth, key = settings.explore_depth, fen_key(board)
    try:
        result = terminal_eval(board) or await cache.get(key, depth, EXPLORE_LINES)
        if result is None:
            result = await engine.analyse(board, depth=depth, multipv=EXPLORE_LINES)
            await cache.put(key, depth, EXPLORE_LINES, result)
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


@router.post("/engine/classify")
async def classify(body: ClassifyIn, user: CurrentUser) -> ClassifyOut:
    """Класс хода в режиме исследования по оценкам позиций до и после — той же логикой,
    что разбор партии (`review/classify.py`, книга дебютов, жертвы, «упущение»). Движок
    не вызывается: оценки присылает клиент (свой движок в браузере или `/engine/analyse`)."""
    board = _board(body.fen)
    move = chess.Move.from_uci(body.move)
    if not board.is_legal(move):
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.INVALID_FEN, "Нелегальный ход"
        )
    data = [body.before.model_dump(), None if body.after is None else body.after.model_dump()]
    try:
        evals = game_evals(replay(board, [move]), data)
    except ExternalEvalError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.ENGINE_DATA_INVALID,
            f"Некорректные оценки движка: {exc}",
            params={"index": exc.index},
        ) from exc
    (evaluated,) = evaluate_game(board, [move], evals).moves
    result = classify_move(
        evaluated,
        in_book=default_openings().is_book(board, move),
        previous=body.previous,
        prior=None if body.prior_fen is None else _board(body.prior_fen),
    )
    best = evaluated.best_move
    eval_before_cp, mate_before = split_score(evaluated.eval_before)
    eval_after_cp, mate_after = split_score(evaluated.eval_after)
    return ClassifyOut(
        move_class=result.move_class,
        is_miss=result.is_miss,
        best_uci=None if best is None else best.uci(),
        best_san=None if best is None else board.san(best),
        eval_before_cp=eval_before_cp,
        eval_after_cp=eval_after_cp,
        mate_before=mate_before,
        mate_after=mate_after,
        accuracy=evaluated.accuracy,
    )
