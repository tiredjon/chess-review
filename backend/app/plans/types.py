"""Контракт идей позиции (сессия 13). `position_ideas(board)` (`ideas.py`) возвращает
`PositionIdeas` — только факты, выводимые из позиции (структура, прорывы, форпосты,
слабости) и ключи типовых планов; текст — `render(ideas, lang)` по шаблонам RU/EN.

Модели pydantic: идеи хранятся в дереве курса (`courses.tree`, JSON) и отдаются API как
есть. Порядок в кортежах — по значимости, самое важное первым."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

Side = Literal["white", "black"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class PawnBreak(_Frozen):
    """Пешечный прорыв стороны `side`: ход пешкой, бьющий или атакующий пешку соперника /
    вскрывающий линию. `legal_now` — можно сыграть прямо сейчас; иначе — цель, к которой
    готовятся (поле прорыва свободно, нужна подготовка)."""

    side: Side
    uci: str
    san: str | None  # только при legal_now
    target: str  # клетка пешки, по которой бьёт прорыв
    legal_now: bool


class Outpost(_Frozen):
    """Форпост `side`: поле на половине соперника, которое не атаковать пешкой соперника
    и которое защищено своей пешкой."""

    side: Side
    square: str


class Weakness(_Frozen):
    side: Side  # чья слабость
    square: str
    kind: Literal["isolated", "backward", "doubled", "hanging", "hole", "passed"]


class Idea(_Frozen):
    """Пункт плана: `key` — шаблон текста в `templates.py`, `params` — клетки, ходы, линии
    для подстановки. Например key="minority_attack", side="white", params={"pawns": "b4-b5"}."""

    key: str
    side: Side
    params: dict[str, str] = {}


class PositionIdeas(_Frozen):
    # Распознанные типовые структуры (`structures.py`, StructureId), самая точная первой.
    structures: tuple[str, ...] = ()
    ideas: tuple[Idea, ...] = ()
    breaks: tuple[PawnBreak, ...] = ()
    outposts: tuple[Outpost, ...] = ()
    weaknesses: tuple[Weakness, ...] = ()
    open_files: tuple[str, ...] = ()
    half_open_files: dict[Side, tuple[str, ...]] = {}


class RenderedIdea(_Frozen):
    """Готовый текст пункта плана на языке пользователя (для API и интерфейса)."""

    key: str
    side: Side
    text: str


class RenderedIdeas(_Frozen):
    structures: tuple[str, ...]
    # Заголовок структуры на языке пользователя («Изолированная пешка d4»), если распознана.
    structure_title: str | None
    # Короткое описание структуры: кто чего добивается (2–3 предложения).
    structure_summary: str | None
    ideas: tuple[RenderedIdea, ...]
