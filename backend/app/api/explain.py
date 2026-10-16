"""Объяснения ходов и общий разбор партии (SPEC §6, §8). Генерация ленивая: по клику
на ход или пакетом при открытии разбора; результат кэшируется в `explanations`."""

from typing import Annotated

from fastapi import APIRouter, Body, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analyses import OwnedAnalysis
from app.api.deps import CurrentUser, ExplainerDep, SessionDep
from app.api.errors import ApiError, ErrorCode
from app.api.ratelimit import LimitLLM
from app.api.schemas import ExplainIn, ExplainLang, MoveExplanationOut, SummaryOut
from app.db.models import Analysis, AnalysisStatus, Game, Move, User
from app.explain.facts import is_explained
from app.explain.rows import game_info
from app.explain.service import Explainer

router = APIRouter(tags=["explain"])


def _lang(requested: ExplainLang | None, user: User) -> ExplainLang:
    if requested is not None:
        return requested
    return "en" if user.lang == "en" else "ru"


@router.post("/moves/{move_id}/explain", dependencies=[LimitLLM])
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
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.MOVE_NOT_FOUND, "Ход не найден")
    return await explain_one(session, explainer, move, _lang(body.lang if body else None, user))


async def explain_one(
    session: AsyncSession, explainer: Explainer, move: Move, lang: ExplainLang
) -> MoveExplanationOut:
    """Объяснение найденного хода (общее с `/shared/{token}/…`)."""
    # Не держать соединение, пока ждём LLM.
    await session.close()
    result = await explainer.explain_move(move, lang)
    return MoveExplanationOut(
        move_id=move.id,
        ply=move.ply,
        text=result.text,
        provider=result.provider,
        cached=result.cached,
    )


async def done_moves(session: AsyncSession, analysis: Analysis) -> list[Move]:
    if analysis.status != AnalysisStatus.DONE:
        raise ApiError(
            status.HTTP_409_CONFLICT, ErrorCode.ANALYSIS_NOT_READY, "Анализ ещё не готов"
        )
    moves = await session.scalars(
        select(Move).where(Move.analysis_id == analysis.id).order_by(Move.ply)
    )
    return list(moves)


@router.post("/analyses/{analysis_id}/explanations", dependencies=[LimitLLM])
async def explain_analysis(
    analysis: OwnedAnalysis,
    session: SessionDep,
    user: CurrentUser,
    explainer: ExplainerDep,
    body: Annotated[ExplainIn | None, Body()] = None,
) -> list[MoveExplanationOut]:
    """Пакет: объяснения всех разбираемых ходов (ошибки, brilliant, great, miss)."""
    moves = [move for move in await done_moves(session, analysis) if is_explained(move)]
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


@router.get("/analyses/{analysis_id}/summary", dependencies=[LimitLLM])
async def analysis_summary(
    analysis: OwnedAnalysis,
    session: SessionDep,
    user: CurrentUser,
    explainer: ExplainerDep,
    lang: Annotated[ExplainLang | None, Query()] = None,
) -> SummaryOut:
    """Общий разбор партии: 3–5 пунктов по точности, ключевым моментам и типичным ошибкам."""
    return await summarize(session, explainer, analysis, _lang(lang, user))


async def summarize(
    session: AsyncSession, explainer: Explainer, analysis: Analysis, lang: ExplainLang
) -> SummaryOut:
    """Общий разбор анализа (общий с `/shared/{token}/summary`); не готов — 409."""
    moves = await done_moves(session, analysis)
    game = await session.get(Game, analysis.game_id)
    assert game is not None
    info = game_info(game, analysis, user_color=game.user_color)
    await session.close()
    result = await explainer.summarize(info, moves, lang)
    return SummaryOut(
        analysis_id=analysis.id, text=result.text, provider=result.provider, cached=result.cached
    )
