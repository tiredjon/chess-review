"""Идеи позиции по пешечной структуре на языке пользователя (сессия 13).

Чистый расчёт без движка и БД (`app/plans/`, миллисекунды), поэтому без лимита запросов.
"""

from typing import Annotated, Literal

import chess
from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.api.errors import ApiError, ErrorCode
from app.plans.ideas import position_ideas
from app.plans.templates import render
from app.plans.types import PositionIdeas, RenderedIdeas

router = APIRouter(tags=["plans"])

PlansLang = Literal["ru", "en"]


class PlansOut(BaseModel):
    ideas: PositionIdeas
    rendered: RenderedIdeas


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


@router.get("/plans")
async def plans(
    fen: Annotated[str, Query(max_length=100)],
    user: CurrentUser,
    lang: Annotated[PlansLang | None, Query()] = None,
) -> PlansOut:
    """Структура, прорывы, форпосты, слабости и планы обеих сторон; язык по умолчанию —
    язык пользователя."""
    board = _board(fen)
    ideas = position_ideas(board)
    chosen: PlansLang = lang if lang is not None else ("en" if user.lang == "en" else "ru")
    return PlansOut(ideas=ideas, rendered=render(ideas, chosen))
