"""Анализ партии движком в браузере (Stockfish WASM, сессия 11): клиент присылает оценки
позиций, сервер делает тот же разбор, что и воркер (`review_game`: точность, классы,
мотивы, дебют), и сохраняет его обычным анализом с `runner = browser`.

Пазлы: генерации нужны вторые линии движка в позициях решений, а их знает только браузер.
Поэтому ответ на сохранение содержит пробы (`collect_probes`), браузер их считает
и присылает в `POST /analyses/{id}/browser-puzzles` — пазлы строятся той же
`generate_puzzles`, только движок заменён ответами браузера. Если проб нет (каждое решение
кончается матом в один ход или ошибок нет), пазлы строятся сразу при сохранении.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import chess
import structlog
from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.analyses import analysis_out
from app.api.deps import CurrentUser, DatabaseDep, RedisDep, SessionDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import UserLimiterDep
from app.api.schemas import (
    BrowserAnalysisIn,
    BrowserAnalysisOut,
    BrowserPuzzlesIn,
    BrowserPuzzlesOut,
    PuzzleProbeOut,
)
from app.db.models import Analysis, AnalysisRunner, AnalysisStatus, Game
from app.engine.cache import fen_key
from app.engine.external import ExternalEvalError, ProbeAnalyser, game_evals, parse_external_eval
from app.importers.pgn import parse_game
from app.puzzles.generate import collect_probes, generate_puzzles
from app.review.evaluate import replay
from app.review.pipeline import review_game
from app.review.types import PositionEval
from app.workers.analysis import save_review

router = APIRouter(tags=["analyses"])
log = structlog.get_logger(__name__)


def _invalid(exc: ExternalEvalError) -> ApiError:
    return ApiError(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.ENGINE_DATA_INVALID,
        f"Некорректные оценки движка: {exc}",
        params={"index": exc.index},
    )


@router.post("/games/{game_id}/browser-analysis", status_code=status.HTTP_201_CREATED)
async def save_browser_analysis(
    game_id: uuid.UUID,
    body: BrowserAnalysisIn,
    *,
    session: SessionDep,
    db: DatabaseDep,
    redis: RedisDep,
    user: CurrentUser,
    settings: SettingsDep,
    limiter: UserLimiterDep,
) -> BrowserAnalysisOut:
    """Разбор по оценкам из браузера; создаёт новый готовый анализ партии (последний
    анализ — тот, что показывается)."""
    if body.depth < settings.browser_min_depth:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.DEPTH_TOO_LOW,
            f"Глубина анализа меньше {settings.browser_min_depth}",
            params={"min": settings.browser_min_depth},
        )
    game = await session.scalar(select(Game).where(Game.id == game_id, Game.user_id == user.id))
    if game is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.GAME_NOT_FOUND, "Партия не найдена")

    parsed = parse_game(game.pgn)
    start, moves = parsed.board(), list(parsed.mainline_moves())
    try:
        evals = game_evals(
            replay(start, moves), [None if p is None else p.model_dump() for p in body.positions]
        )
    except ExternalEvalError as exc:
        raise _invalid(exc) from exc
    await limiter.hit("browser")
    # Разбор — ~1 с CPU: в поток, как в воркере.
    review = await asyncio.to_thread(review_game, start, moves, evals)

    now = datetime.now(UTC)
    analysis = Analysis(
        game_id=game.id,
        depth=body.depth,
        status=AnalysisStatus.RUNNING,
        runner=AnalysisRunner.BROWSER,
        engine_version=body.engine,
        started_at=now,
    )
    session.add(analysis)
    await session.commit()
    await save_review(db, analysis.id, review)
    await session.refresh(analysis)
    log.info("analysis.browser_saved", analysis_id=str(analysis.id), moves=len(review.moves))

    probes = await collect_probes(db, analysis.id)
    if not probes:
        # Решениям не нужны линии движка (например, мат в 1) — пазлы сразу, без второго шага.
        await generate_puzzles(
            db, ProbeAnalyser({}), analysis.id, skip_users=(settings.bot_user_id,)
        )
    return BrowserAnalysisOut(
        analysis=await analysis_out(session, redis, analysis),
        puzzle_probes=[PuzzleProbeOut(fen=probe.fen, move=probe.move) for probe in probes],
    )


@router.post("/analyses/{analysis_id}/browser-puzzles")
async def save_browser_puzzles(
    analysis_id: uuid.UUID,
    body: BrowserPuzzlesIn,
    *,
    session: SessionDep,
    db: DatabaseDep,
    user: CurrentUser,
    limiter: UserLimiterDep,
) -> BrowserPuzzlesOut:
    """Пазлы из анализа в браузере по ответам на пробы. Повтор безопасен (пазлы уникальны
    по позиции); пробы, которых нет в ответе, пазла не дают."""
    analysis = await session.scalar(
        select(Analysis).join(Game).where(Analysis.id == analysis_id, Game.user_id == user.id)
    )
    if analysis is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.ANALYSIS_NOT_FOUND, "Анализ не найден")
    if analysis.status != AnalysisStatus.DONE or analysis.runner != AnalysisRunner.BROWSER:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            ErrorCode.ANALYSIS_NOT_READY,
            "Пазлы по пробам — только для готового анализа из браузера",
        )
    await session.commit()

    evals: dict[tuple[str, str], PositionEval] = {}
    for index, probe in enumerate(body.probes):
        try:
            board = chess.Board(probe.fen)
        except ValueError as exc:
            raise _invalid(ExternalEvalError(index, "некорректный FEN")) from exc
        try:
            evals[(fen_key(board), probe.move)] = parse_external_eval(
                index, board, probe.eval.model_dump()
            )
        except ExternalEvalError as exc:
            raise _invalid(exc) from exc
    await limiter.hit("browser")
    count = await generate_puzzles(db, ProbeAnalyser(evals), analysis_id)
    log.info("puzzles.browser_generated", analysis_id=str(analysis_id), count=count)
    return BrowserPuzzlesOut(puzzles=count)
