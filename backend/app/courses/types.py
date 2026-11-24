"""Контракт дерева курса (сессия 13): что сборщик (`builder.py`) пишет в `courses.tree`,
что отдаёт API и что читает тренажёр. Узлы — плоский список, ссылки — индексами.

Узел — позиция после хода `uci` (у корня `uci` = None: позиция после исходной линии
целиком не начинается, корень — начальная позиция). Ход узла сделала сторона `mover`:
"learner" — цвет курса, "opponent" — соперник. Ход за учеником в позиции узла, у которого
дети с mover="learner".

Содержание курса после готовности не меняется (`Course.key` включает `BUILDER_VERSION`),
поэтому `id` узла стабилен — на него ссылаются карточки тренажёра."""

from typing import Literal

from pydantic import BaseModel

from app.plans.types import PositionIdeas

# Меняется при изменении алгоритма сборки или формата дерева — старые курсы остаются
# как были, новые собираются заново.
BUILDER_VERSION = 1

Mover = Literal["learner", "opponent"]


class MoveStats(BaseModel):
    """Статистика хода в базе мастеров (или Lichess, если `source` = lichess)."""

    source: Literal["masters", "lichess"]
    games: int
    white: int
    draws: int
    black: int
    average_rating: int | None = None


class NodeEval(BaseModel):
    """Оценка позиции узла движком, с точки зрения белых. Ровно одно из cp / mate."""

    cp: int | None = None
    mate: int | None = None
    depth: int
    best_uci: str | None = None


class CourseNode(BaseModel):
    id: int
    parent: int | None
    children: list[int] = []
    ply: int  # полуходов от начальной позиции
    uci: str | None
    san: str | None
    mover: Mover | None
    fen: str
    # Позиция есть в базе дебютов (`review/openings.py`); `name` — если у неё есть название.
    book: bool
    name: str | None = None
    # Ход ученика из основной линии курса (у ответов соперника — False).
    main: bool = False
    # Для ходов соперника — доля среди ответов мастеров (для выбора ветки в тренажёре).
    weight: float = 1.0
    stats: MoveStats | None = None
    eval: NodeEval | None = None
    # Идеи позиции — в ключевых узлах: выход из теории, смена структуры, конец линии.
    ideas: PositionIdeas | None = None
    # Почему узел ключевой: "book_exit" | "structure" | "line_end" | None.
    key_moment: str | None = None


class ModelGame(BaseModel):
    """Образцовая партия мастеров, прошедшая через позицию `node_id`."""

    id: str
    node_id: int
    white: str
    black: str
    white_rating: int | None = None
    black_rating: int | None = None
    year: int | None = None
    result: str
    pgn: str


class CourseTree(BaseModel):
    version: int = BUILDER_VERSION
    color: Literal["white", "black"]
    # Индекс узла, где кончается исходная линия курса (с него начинается «дальше теории»).
    line_end: int
    nodes: list[CourseNode]
    model_games: list[ModelGame] = []
