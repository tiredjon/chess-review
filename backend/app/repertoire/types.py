"""Контракт репертуара (сессия 13.3): дерево ходов и список дебютов из партий пользователя.

Узел повторяет поля `CourseNode` (`app/courses/types.py`), чтобы фронт рисовал дерево курса
и дерево репертуара одним компонентом; сверх них — статистика партий через узел."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Mover = Literal["learner", "opponent"]


class RepertoireNode(BaseModel):
    """Позиция после хода `uci` по пути от начальной позиции (переходы не склеиваются).

    Корень (`id` = 0): начальная позиция, `uci` / `san` / `mover` = None. Результат
    партий — с точки зрения пользователя; `games` = `wins + draws + losses`."""

    id: int
    parent: int | None
    children: list[int] = []
    ply: int
    uci: str | None
    san: str | None
    mover: Mover | None
    fen: str
    book: bool
    name: str | None = None
    games: int
    wins: int
    draws: int
    losses: int
    last_played_at: datetime | None = None


class RepertoireTree(BaseModel):
    color: Literal["white", "black"]
    # Партий цвета с известным результатом; у пустого репертуара `nodes` пуст.
    total_games: int
    nodes: list[RepertoireNode]


class RepertoireOpening(BaseModel):
    """Дебют из `games.opening_name` за один цвет."""

    name: str
    eco: str | None
    games: int
    wins: int
    draws: int
    losses: int
    # Самый частый путь из партий до позиции с этим названием.
    line_uci: list[str]
    # Медиана (нижняя) числа первых книжных полуходов по партиям.
    book_exit_ply: int
    last_played_at: datetime | None = None
