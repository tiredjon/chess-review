"""Публичные ссылки на разбор (`/share/{token}` в веб-приложении, ответ Telegram-бота).

`/shared/{token}…` — без входа, только чтение: партия, её последний анализ, объяснения
ходов и общий разбор. Токен — `games.share_token` (`app/db/share.py`); неизвестный
или отозванный — 404 `share_not_found`. Владелец партии включает и отзывает ссылку
через `POST` / `DELETE /games/{id}/share`.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.analyses import analysis_out, latest_analyses
from app.api.deps import CurrentUser, ExplainerDep, RedisDep, SessionDep, SettingsDep
from app.api.errors import ApiError, ErrorCode
from app.api.explain import explain_one, summarize
from app.api.ratelimit import client_ip, hit
from app.api.schemas import ExplainIn, ExplainLang, GameDetail, MoveExplanationOut, SummaryOut
from app.db.models import Analysis, Game, Move
from app.db.share import ensure_share_token, share_url

router = APIRouter(tags=["shared"])

# Токен — token_urlsafe: больше 64 символов не бывает, дальше даже не ищем.
ShareToken = Annotated[str, Path(min_length=1, max_length=64)]
# Без входа языка профиля нет: по умолчанию — русский, как у новых пользователей.
DEFAULT_LANG: ExplainLang = "ru"


class ShareOut(BaseModel):
    token: str
    # `{PUBLIC_WEB_URL}/share/{token}`.
    url: str


async def limit_llm_ip(request: Request, redis: RedisDep, settings: SettingsDep) -> None:
    """Лимит LLM на IP (входа нет): как `LimitLLM`, шаблоны не режем."""
    if request.app.state.llm is not None:
        await hit(redis, settings, "llm", client_ip(request, settings))


LimitLLMByIP = Depends(limit_llm_ip)


async def _shared_game(session: AsyncSession, token: str) -> Game:
    game = await session.scalar(select(Game).where(Game.share_token == token))
    if game is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.SHARE_NOT_FOUND, "Ссылка не найдена")
    return game


async def _latest(session: AsyncSession, game: Game) -> Analysis | None:
    return (await latest_analyses(session, [game.id])).get(game.id)


@router.get("/shared/{token}")
async def get_shared_game(token: ShareToken, session: SessionDep, redis: RedisDep) -> GameDetail:
    """Партия по ссылке — как `GET /games/{id}`: последний анализ с ходами (если готов)
    или прогрессом (если идёт)."""
    game = await _shared_game(session, token)
    result = GameDetail.model_validate(game)
    analysis = await _latest(session, game)
    if analysis is not None:
        result.analysis = await analysis_out(session, redis, analysis)
    return result


@router.post("/shared/{token}/moves/{move_id}/explain", dependencies=[LimitLLMByIP])
async def explain_shared_move(
    token: ShareToken,
    move_id: int,
    session: SessionDep,
    explainer: ExplainerDep,
    body: Annotated[ExplainIn | None, Body()] = None,
) -> MoveExplanationOut:
    """Объяснение хода последнего анализа партии по ссылке."""
    game = await _shared_game(session, token)
    analysis = await _latest(session, game)
    move = (
        None
        if analysis is None
        else await session.scalar(
            select(Move).where(Move.id == move_id, Move.analysis_id == analysis.id)
        )
    )
    if move is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.MOVE_NOT_FOUND, "Ход не найден")
    lang = body.lang if body is not None and body.lang is not None else DEFAULT_LANG
    return await explain_one(session, explainer, move, lang)


@router.get("/shared/{token}/summary", dependencies=[LimitLLMByIP])
async def shared_summary(
    token: ShareToken,
    session: SessionDep,
    explainer: ExplainerDep,
    lang: Annotated[ExplainLang | None, Query()] = None,
) -> SummaryOut:
    """Общий разбор последнего анализа партии по ссылке; анализ не готов — 409."""
    game = await _shared_game(session, token)
    analysis = await _latest(session, game)
    if analysis is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.ANALYSIS_NOT_FOUND, "Анализа нет")
    return await summarize(session, explainer, analysis, lang or DEFAULT_LANG)


# --- Владелец партии: включить, посмотреть, отозвать ссылку ---


async def _owned_game(
    session: AsyncSession, user: CurrentUser, game_id: uuid.UUID, *, lock: bool = False
) -> Game:
    stmt = select(Game).where(Game.id == game_id, Game.user_id == user.id)
    game = await session.scalar(stmt.with_for_update() if lock else stmt)
    if game is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.GAME_NOT_FOUND, "Партия не найдена")
    return game


@router.post("/games/{game_id}/share")
async def share_game(
    game_id: uuid.UUID, session: SessionDep, user: CurrentUser, settings: SettingsDep
) -> ShareOut:
    """Публичная ссылка на разбор; повторный вызов возвращает ту же ссылку."""
    # Блокировка: два одновременных запроса не выдадут разные токены.
    game = await _owned_game(session, user, game_id, lock=True)
    token = ensure_share_token(game)
    await session.commit()
    return ShareOut(token=token, url=share_url(settings, token))


@router.get("/games/{game_id}/share")
async def get_game_share(
    game_id: uuid.UUID, session: SessionDep, user: CurrentUser, settings: SettingsDep
) -> ShareOut:
    """Текущая ссылка; партия не опубликована — 404 `share_not_found`."""
    game = await _owned_game(session, user, game_id)
    if game.share_token is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND, ErrorCode.SHARE_NOT_FOUND, "Партия не опубликована"
        )
    return ShareOut(token=game.share_token, url=share_url(settings, game.share_token))


@router.delete("/games/{game_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def unshare_game(game_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> Response:
    """Отзывает ссылку: прежний токен перестаёт работать (новая ссылка — другой токен)."""
    game = await _owned_game(session, user, game_id, lock=True)
    game.share_token = None
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
