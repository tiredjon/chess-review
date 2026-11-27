"""Уроки тренера (17.2): прочитанные, позиции из своих партий и тренировка к уроку.

Тексты — на фронте (`web/src/lib/coach-lessons/`). Позиции — до 5 своих ходов (из разных
партий, свежие первыми, как примеры слабых мест 16.1) по партиям цели (нет цели — по всем):
- мотив — ходы, где лучший ход с этим мотивом упущен (ошибка или miss);
- фаза — ошибки в этой фазе из неясных позиций (win% 10–90);
- навыки: `blunder_check` — зевки; `tactical_vision` — упущенные шансы (miss);
  `converting_advantage` — ошибки при win% до хода ≥ 80; `defense` — ошибки при win% ≤ 30;
  `time_management` — ошибки в цейтноте; `opening_repertoire` — первая ошибка в дебюте.
Тренировка — как у выводов 16.1: мотив → пазлы по теме; дебют / миттельшпиль → пазлы фазы;
эндшпиль и реализация → эндшпиль своих партий; репертуар → курс по самому частому дебюту;
остальное — пазлы.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import CTE

from app.api.schemas_coach import LessonItemOut, LessonKind
from app.api.schemas_insights import ExampleOut, TrainOut, TrainQueryOut
from app.coach.lessons import LESSONS
from app.db.models import CoachGoal, CoachLessonRead, GameSource, Move
from app.insights.queries import ExampleRow, _available, _contested, _examples, _is_error
from app.insights.rules import THRESHOLDS, Train
from app.review.types import MoveClass, Phase
from app.stats.queries import clock_sql, user_games

PHASES: dict[str, Phase] = {
    "opening_principles": Phase.OPENING,
    "middlegame_plans": Phase.MIDDLEGAME,
    "endgame_technique": Phase.ENDGAME,
}
WINNING = 80.0
LOSING = 30.0


async def read_keys(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
    return set(
        await session.scalars(select(CoachLessonRead.key).where(CoachLessonRead.user_id == user_id))
    )


async def lesson_list(session: AsyncSession, user_id: uuid.UUID) -> list[LessonItemOut]:
    read = await read_keys(session, user_id)
    return [LessonItemOut(key=k, kind=kind, read=k in read) for k, kind in LESSONS.items()]


def _skill_condition(key: str, ug: CTE) -> ColumnElement[bool]:
    t = THRESHOLDS
    conditions: dict[str, ColumnElement[bool]] = {
        "blunder_check": and_(Move.move_class == MoveClass.BLUNDER, _contested(t)),
        "tactical_vision": and_(Move.is_miss, Move.uci != Move.best_uci),
        "converting_advantage": and_(Move.win_before >= WINNING, _is_error()),
        "defense": and_(Move.win_before <= LOSING, _is_error()),
        "opening_repertoire": and_(Move.phase == Phase.OPENING, _is_error()),
    }
    if key == "time_management":
        clock = clock_sql(ug)
        return and_(*clock.known, clock.trouble, _is_error())
    return conditions.get(key, and_(_is_error(), _contested(t)))


def _condition(key: str, kind: LessonKind, ug: CTE) -> tuple[ColumnElement[bool], tuple[Any, ...]]:
    """Условие на ходы-примеры урока и порядок внутри партии (см. модуль)."""
    if kind == "motif":
        missed = Move.motifs["missed"].contains([{"type": key}])
        return and_(Move.uci != Move.best_uci, or_(_is_error(), Move.is_miss), missed), ()
    if kind == "phase":
        return and_(Move.phase == PHASES[key], _is_error(), _contested(THRESHOLDS)), ()
    # Репертуар — первая ошибка дебюта: с неё партия и пошла не так.
    prefer = (Move.ply,) if key == "opening_repertoire" else ()
    return _skill_condition(key, ug), prefer


async def _common_eco(session: AsyncSession, ug: CTE) -> str | None:
    return await session.scalar(
        select(func.mode().within_group(ug.c.opening_eco)).where(ug.c.opening_eco.is_not(None))
    )


async def _train(
    session: AsyncSession, user_id: uuid.UUID, key: str, kind: LessonKind, ug: CTE
) -> TrainOut | None:
    train: Train
    if kind == "motif":
        train = Train(kind="puzzles", theme=key)
    elif key in {"endgame_technique", "converting_advantage"}:
        train = Train(kind="endgames")
    elif kind == "phase":
        train = Train(kind="puzzles", phase=PHASES[key])
    elif key == "opening_repertoire":
        eco = await _common_eco(session, ug)
        if eco is None:
            return None
        train = Train(kind="course", eco=eco)
    else:
        train = Train(kind="puzzles")
    available = await _available(session, user_id, train)
    return TrainOut(
        kind=train.kind,
        query=TrainQueryOut(theme=train.theme, phase=train.phase, eco=train.eco),
        available=available,
    )


def _example(row: ExampleRow) -> ExampleOut:
    return ExampleOut(
        game_id=row.game_id,
        ply=row.ply,
        fen_before=row.fen_before,
        san=row.san,
        best_san=row.best_san,
        move_class=row.move_class,
        opponent=row.opponent,
        played_at=row.played_at,
    )


async def lesson_detail(
    session: AsyncSession, user_id: uuid.UUID, key: str, goal: CoachGoal | None
) -> tuple[LessonKind, bool, list[ExampleOut], TrainOut | None]:
    kind = LESSONS[key]
    source: GameSource | None = goal.source if goal else None
    ug = user_games(user_id, source, goal.time_class if goal else None)  # type: ignore[arg-type]
    condition, prefer = _condition(key, kind, ug)
    rows = await _examples(session, ug, condition, prefer=prefer)
    train = await _train(session, user_id, key, kind, ug)
    read = key in await read_keys(session, user_id)
    return kind, read, [_example(r) for r in rows], train


async def mark_read(session: AsyncSession, user_id: uuid.UUID, key: str, now: datetime) -> None:
    """Отметить урок прочитанным (повторное чтение обновляет время; без коммита)."""
    stmt = insert(CoachLessonRead).values(user_id=user_id, key=key, read_at=now)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[CoachLessonRead.user_id, CoachLessonRead.key],
            set_={"read_at": stmt.excluded.read_at},
        )
    )
