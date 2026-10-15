"""Объяснения ходов и общий разбор партии (SPEC §6, §8). Генерация ленивая: по клику
на ход или пакетом при открытии разбора; результат кэшируется в `explanations`."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query, status
from sqlalchemy import select

from app.api.analyses import OwnedAnalysis
from app.api.deps import CurrentUser, ExplainerDep, SessionDep
from app.api.schemas import ExplainIn, ExplainLang, MoveExplanationOut, SummaryOut
from app.db.models import Analysis, AnalysisStatus, Game, Move, User
from app.explain.facts import GameInfo, is_explained

router = APIRouter(tags=["explain"])


def _lang(requested: ExplainLang | None, user: User) -> ExplainLang:
    if requested is not None:
        return requested
    return "en" if user.lang == "en" else "ru"


@router.post("/moves/{move_id}/explain")
async def explain_move(
    move_id: int,
    session: SessionDep,
    user: CurrentUser,
    explainer: ExplainerDep,
    body: Annotated[ExplainIn | None, Body()] = None,
) -> MoveExplanationOut:
    """Объяснение хода на основе фактов разбора (LLM или шаблон)."""
    move = await session.scalar(
        select(Move)
        .join(Analysis, Move.analysis_id == Analysis.id)
        .join(Game, Analysis.game_id == Game.id)
        .where(Move.id == move_id, Game.user_id == user.id)
    )
    if move is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ход не найден")
    # Не держать соединение, пока ждём LLM.
    await session.close()
    result = await explainer.explain_move(move, _lang(body.lang if body else None, user))
    return MoveExplanationOut(
        move_id=move.id,
        ply=move.ply,
        text=result.text,
        provider=result.provider,
        cached=result.cached,
    )


async def _done_moves(session: SessionDep, analysis: Analysis) -> list[Move]:
    if analysis.status != AnalysisStatus.DONE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Анализ ещё не готов")
    moves = await session.scalars(
        select(Move).where(Move.analysis_id == analysis.id).order_by(Move.ply)
    )
    return list(moves)


@router.post("/analyses/{analysis_id}/explanations")
async def explain_analysis(
    analysis: OwnedAnalysis,
    session: SessionDep,
    user: CurrentUser,
    explainer: ExplainerDep,
    body: Annotated[ExplainIn | None, Body()] = None,
) -> list[MoveExplanationOut]:
    """Пакет: объяснения всех разбираемых ходов (ошибки, brilliant, great, miss)."""
    moves = [move for move in await _done_moves(session, analysis) if is_explained(move)]
    lang = _lang(body.lang if body else None, user)
    await session.close()
    results = await explainer.explain_moves(moves, lang)
    return [
        MoveExplanationOut(
            move_id=move.id,
            ply=move.ply,
            text=result.text,
            provider=result.provider,
            cached=result.cached,
        )
        for move, result in zip(moves, results, strict=True)
    ]


def _shown_accuracy(*candidates: float | None) -> float | None:
    """Та же точность, что на плашках (`GameOut.accuracy_of`): официальная Chess.com,
    иначе наша «как у Chess.com», иначе — по формуле Lichess."""
    return next((value for value in candidates if value is not None), None)


@router.get("/analyses/{analysis_id}/summary")
async def analysis_summary(
    analysis: OwnedAnalysis,
    session: SessionDep,
    user: CurrentUser,
    explainer: ExplainerDep,
    lang: Annotated[ExplainLang | None, Query()] = None,
) -> SummaryOut:
    """Общий разбор партии: 3–5 пунктов по точности, ключевым моментам и типичным ошибкам."""
    moves = await _done_moves(session, analysis)
    game = await session.get(Game, analysis.game_id)
    assert game is not None
    phase_accuracy: Any = analysis.phase_accuracy
    info = GameInfo(
        white=game.white,
        black=game.black,
        white_elo=game.white_elo,
        black_elo=game.black_elo,
        result=game.result,
        opening_name=game.opening_name,
        user_color=game.user_color.value if game.user_color else None,
        white_accuracy=_shown_accuracy(
            game.source_white_accuracy, analysis.cc_white_accuracy, analysis.white_accuracy
        ),
        black_accuracy=_shown_accuracy(
            game.source_black_accuracy, analysis.cc_black_accuracy, analysis.black_accuracy
        ),
        phase_accuracy=phase_accuracy,
    )
    await session.close()
    result = await explainer.summarize(info, moves, _lang(lang, user))
    return SummaryOut(
        analysis_id=analysis.id, text=result.text, provider=result.provider, cached=result.cached
    )
