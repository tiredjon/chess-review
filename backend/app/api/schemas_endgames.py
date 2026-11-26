"""Схемы API тренажёра эндшпиля (сессия 16.3)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.endgames.catalog import Category, Goal
from app.endgames.tablebase import TbCategory


class ProgressOut(BaseModel):
    attempts: int
    successes: int


class CatalogPositionOut(ProgressOut):
    id: str
    category: Category
    fen: str
    goal: Goal
    difficulty: int
    # Цвет ученика — сторона на ходу в `fen`.
    color: Literal["white", "black"]
    pieces: int


class CatalogOut(BaseModel):
    # Порядок показа категорий.
    categories: list[Category]
    positions: list[CatalogPositionOut]


class GamePositionOut(ProgressOut):
    # Id хода (ключ попытки с `source=game`).
    key: str
    fen: str
    goal: Goal
    game_id: uuid.UUID
    ply: int
    played_at: datetime | None
    opponent: str
    san: str
    best_san: str | None
    # Win% до хода глазами пользователя.
    win_before: float
    pieces: int


class MineOut(BaseModel):
    positions: list[GamePositionOut]


class TablebaseMoveOut(BaseModel):
    uci: str
    san: str
    # Глазами ходящего: `win` — ход выигрывает.
    category: TbCategory
    dtz: int | None
    dtm: int | None


class TablebaseOut(BaseModel):
    """Глазами стороны на ходу; ходы — от лучшего к худшему (при проигрыше — самая упорная
    защита первой)."""

    category: TbCategory
    dtz: int | None
    dtm: int | None
    checkmate: bool
    stalemate: bool
    moves: list[TablebaseMoveOut]


class AttemptIn(BaseModel):
    source: Literal["catalog", "game"]
    key: str = Field(min_length=1, max_length=64)
    goal: Goal
    success: bool
    # Полуходов сыграно с начальной позиции.
    plies: int = Field(ge=0, le=2000)
