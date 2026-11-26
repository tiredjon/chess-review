"""Слабые места: агрегаты по партиям пользователя (SQL), примеры и число тренировок.

Партии и фильтры — те же, что у `/stats/me` (`app/stats/queries.user_games`): только
партии с известным цветом и только ходы пользователя; ходы в Python не грузятся, кроме
примеров. Выводы из агрегатов делает `rules.py`.

Определения:
— ошибка — mistake / blunder (как в блоке «Время на ход» `/stats`); для мотивов ещё и
  `miss` — упущенный шанс и есть «упустил мотив»;
— мотив лучшего хода — `motifs.played`, если сыгран лучший ход, иначе `motifs.missed`
  (детекторы на PV1, SPEC §5); возможность — ход, у лучшего хода которого есть мотив;
— дебют — семейство (имя до «:»), по всем партиям с результатом (точность не нужна);
— выигранная позиция — win% после хода пользователя ≥ `conversion_win`; ожидание —
  win% первого такого хода (формула Lichess подобрана по исходам партий).
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ColumnElement,
    and_,
    case,
    column,
    distinct,
    func,
    literal_column,
    or_,
    select,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import CTE

from app.db.models import Analysis, Game, GameSource, Move, Puzzle
from app.insights.rules import (
    THRESHOLDS,
    Aggregates,
    ConversionAgg,
    Finding,
    MotifAgg,
    OpeningAgg,
    PhaseAgg,
    Thresholds,
    TimeAgg,
    Train,
    find_weaknesses,
)
from app.review.game_rating import TimeClass
from app.review.types import MoveClass, Phase
from app.stats.queries import analyzed_moves, clock_sql, user_games

MAX_EXAMPLES = 5
ERRORS = (MoveClass.MISTAKE, MoveClass.BLUNDER)
# Позиции эндшпиля из своих партий (SPEC 16.3 `GET /endgames/mine`): ход-источник — ошибка
# или miss в эндшпиле при win% до хода не ниже порога «ничья».
ENDGAME_MIN_WIN_BEFORE = 35.0

_EMPTY = literal_column("'[]'::jsonb", JSONB)


@dataclass(frozen=True, slots=True)
class ExampleRow:
    game_id: uuid.UUID
    ply: int
    fen_before: str
    san: str
    best_san: str | None
    move_class: str
    opponent: str
    played_at: datetime | None


@dataclass(frozen=True, slots=True)
class Insight:
    finding: Finding
    examples: list[ExampleRow]
    available: int | None


@dataclass(frozen=True, slots=True)
class InsightsResult:
    analyzed_games: int
    min_games: int
    insights: list[Insight]


def _is_error() -> ColumnElement[bool]:
    return Move.move_class.in_(ERRORS)


def _best_motifs() -> ColumnElement[Any]:
    """Мотивы лучшего хода позиции (см. модуль)."""
    return case(
        (Move.uci == Move.best_uci, func.coalesce(Move.motifs["played"], _EMPTY)),
        else_=func.coalesce(Move.motifs["missed"], _EMPTY),
    )


def _family(name: ColumnElement[Any]) -> ColumnElement[str]:
    return func.trim(func.split_part(name, ":", 1))


async def _analyzed_count(session: AsyncSession, ug: CTE) -> int:
    stmt = select(func.count()).where(ug.c.user_color.is_not(None), ug.c.done)
    return int((await session.execute(stmt)).scalar_one())


async def _motifs(session: AsyncSession, ug: CTE) -> list[MotifAgg]:
    element = (
        func.jsonb_array_elements(_best_motifs()).table_valued(column("value", JSONB)).lateral("el")
    )
    missed = and_(Move.uci != Move.best_uci, or_(_is_error(), Move.is_miss))
    per_move = (
        analyzed_moves(
            select(
                Move.id.label("move_id"),
                element.c.value["type"].astext.label("type"),
                missed.label("missed"),
            ),
            ug,
        )
        .join(element, true())
        .where(Move.best_uci.is_not(None))
        .distinct()
        .subquery()
    )
    rows = await session.execute(
        select(
            per_move.c.type,
            func.count().label("opportunities"),
            func.count().filter(per_move.c.missed).label("missed"),
        ).group_by(per_move.c.type)
    )
    return [MotifAgg(row.type, row.opportunities, row.missed) for row in rows]


def _contested(t: Thresholds) -> ColumnElement[bool]:
    return Move.win_before.between(t.contested_min, t.contested_max)


async def _phases(session: AsyncSession, ug: CTE, t: Thresholds) -> list[PhaseAgg]:
    rows = await session.execute(
        analyzed_moves(
            select(
                Move.phase,
                func.count().label("moves"),
                func.count().filter(_is_error()).label("errors"),
            ),
            ug,
        )
        .where(_contested(t))
        .group_by(Move.phase)
    )
    return [PhaseAgg(row.phase, row.moves, row.errors) for row in rows]


async def _time(session: AsyncSession, ug: CTE, t: Thresholds) -> TimeAgg | None:
    clock = clock_sql(ug)
    calm = ~clock.trouble
    row = (
        await session.execute(
            analyzed_moves(
                select(
                    func.count().filter(clock.trouble).label("trouble_moves"),
                    func.count().filter(clock.trouble, _is_error()).label("trouble_errors"),
                    func.count().filter(calm).label("calm_moves"),
                    func.count().filter(calm, _is_error()).label("calm_errors"),
                    func.count().filter(calm, clock.fast).label("fast_moves"),
                    func.count().filter(calm, clock.fast, _is_error()).label("fast_errors"),
                ),
                ug,
            ).where(*clock.known, _contested(t))
        )
    ).one()
    if not row.trouble_moves and not row.calm_moves:
        return None
    return TimeAgg(**row._asdict())


async def _openings(session: AsyncSession, ug: CTE) -> list[OpeningAgg]:
    family = _family(ug.c.opening_name)
    points = case((ug.c.outcome == "win", 1.0), (ug.c.outcome == "draw", 0.5), else_=0.0)
    rows = await session.execute(
        select(
            ug.c.user_color,
            family.label("family"),
            func.mode().within_group(ug.c.opening_eco).label("eco"),
            func.count().label("games"),
            func.sum(points).label("points"),
        )
        .where(
            ug.c.user_color.is_not(None), ug.c.opening_name.is_not(None), ug.c.outcome.is_not(None)
        )
        .group_by(ug.c.user_color, family)
    )
    return [
        OpeningAgg(row.user_color, row.family, row.eco, row.games, float(row.points))
        for row in rows
    ]


def _first_winning(ug: CTE, threshold: float) -> Any:
    """Первый ход пользователя с выигранной позицией в каждой разобранной партии."""
    return (
        analyzed_moves(
            select(
                ug.c.id.label("game_id"),
                ug.c.outcome,
                Move.ply,
                Move.win_after,
            ),
            ug,
        )
        .where(Move.win_after >= threshold, ug.c.outcome.is_not(None))
        .ext(distinct_on(ug.c.id))
        .order_by(ug.c.id, Move.ply)
        .subquery()
    )


async def _conversion(session: AsyncSession, ug: CTE, t: Thresholds) -> ConversionAgg | None:
    first = _first_winning(ug, t.conversion_win)
    points = case((first.c.outcome == "win", 1.0), (first.c.outcome == "draw", 0.5), else_=0.0)
    row = (
        await session.execute(
            select(
                func.count().label("games"),
                func.coalesce(func.sum(points), 0).label("points"),
                func.count().filter(first.c.outcome != "win").label("not_won"),
                func.coalesce(func.sum(first.c.win_after / 100), 0).label("expected"),
            )
        )
    ).one()
    if not row.games:
        return None
    return ConversionAgg(int(row.games), float(row.points), float(row.expected), int(row.not_won))


# --- Примеры ---------------------------------------------------------------------------------


async def _examples(
    session: AsyncSession,
    ug: CTE,
    condition: ColumnElement[bool],
    *,
    prefer: Sequence[Any] = (),
    extra: Any = None,
) -> list[ExampleRow]:
    """До `MAX_EXAMPLES` ходов пользователя по условию: из разных партий, свежие первыми;
    в партии — по `prefer` (по умолчанию самый большой провал win%)."""
    order = (*prefer, (Move.win_before - Move.win_after).desc(), Move.ply)
    stmt = analyzed_moves(
        select(
            ug.c.id.label("game_id"),
            ug.c.ts,
            ug.c.played_at,
            ug.c.opponent,
            Move.ply,
            Move.fen_before,
            Move.san,
            Move.best_san,
            Move.move_class,
            Move.is_miss,
            func.row_number().over(partition_by=ug.c.id, order_by=order).label("rank"),
        ).select_from(Move),
        ug,
    ).where(condition)
    if extra is not None:
        stmt = extra(stmt)
    ranked = stmt.subquery()
    rows = await session.execute(
        select(ranked)
        .where(ranked.c.rank == 1)
        .order_by(ranked.c.ts.desc(), ranked.c.game_id)
        .limit(MAX_EXAMPLES)
    )
    return [
        ExampleRow(
            game_id=row.game_id,
            ply=row.ply,
            fen_before=row.fen_before,
            san=row.san,
            best_san=row.best_san,
            move_class="miss"
            if row.is_miss and row.move_class not in ERRORS
            else row.move_class.value,
            opponent=row.opponent,
            played_at=row.played_at,
        )
        for row in rows
    ]


async def _finding_examples(
    session: AsyncSession, ug: CTE, finding: Finding, t: Thresholds
) -> list[ExampleRow]:
    match finding.kind:
        case "motif":
            missed = Move.motifs["missed"].contains([{"type": finding.key}])
            return await _examples(
                session,
                ug,
                and_(Move.uci != Move.best_uci, or_(_is_error(), Move.is_miss), missed),
            )
        case "phase":
            return await _examples(
                session, ug, and_(Move.phase == finding.key, _is_error(), _contested(t))
            )
        case "time":
            clock = clock_sql(ug)
            flag = clock.trouble if finding.key == "trouble" else and_(~clock.trouble, clock.fast)
            return await _examples(
                session, ug, and_(*clock.known, flag, _is_error(), _contested(t))
            )
        case "opening":
            color, family = finding.key.split(":", 1)
            # Первая ошибка партии в этом дебюте: с неё партия и пошла не так.
            return await _examples(
                session,
                ug,
                and_(
                    ug.c.user_color == color,
                    _family(ug.c.opening_name) == family,
                    _is_error(),
                ),
                prefer=(Move.ply,),
            )
        case "conversion":
            first = _first_winning(ug, t.conversion_win)
            # Самый большой провал после того, как позиция стала выигранной, в партиях без победы.
            return await _examples(
                session,
                ug,
                and_(
                    first.c.outcome != "win",
                    Move.ply > first.c.ply,
                    Move.win_before > Move.win_after,
                ),
                extra=lambda stmt: stmt.join(first, first.c.game_id == ug.c.id),
            )
    return []


# --- Сколько тренировок есть -----------------------------------------------------------------


async def _available(session: AsyncSession, user_id: uuid.UUID, train: Train) -> int:
    """Сколько тренировок найдёт ссылка «Тренировать» (фильтры источника и контроля на страницах
    тренировки не действуют — и здесь не применяются)."""
    if train.kind == "puzzles":
        stmt = select(func.count(distinct(Puzzle.id))).where(Puzzle.user_id == user_id)
        if train.theme is not None:
            stmt = stmt.where(Puzzle.themes.contains([train.theme]))
        if train.phase is not None or train.eco is not None:
            stmt = stmt.join(Move, Move.id == Puzzle.move_id)
            if train.phase is not None:
                stmt = stmt.where(Move.phase == train.phase)
            if train.eco is not None:
                stmt = (
                    stmt.join(Analysis, Analysis.id == Move.analysis_id)
                    .join(Game, Game.id == Analysis.game_id)
                    .where(Game.opening_eco == train.eco)
                )
        return int((await session.execute(stmt)).scalar_one())
    if train.kind == "endgames":
        return await _endgame_positions(session, user_id)
    if train.kind == "course":
        # Курс строится по линии из своих партий: есть партии в этом дебюте — есть линия.
        return 1
    return 0


async def _endgame_positions(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Партии с позицией для тренажёра эндшпиля (по одной на партию, SPEC 16.3)."""
    ug = user_games(user_id, None, None)
    stmt = analyzed_moves(select(func.count(distinct(ug.c.id))).select_from(Move), ug).where(
        Move.phase == Phase.ENDGAME,
        or_(_is_error(), Move.is_miss),
        Move.win_before >= ENDGAME_MIN_WIN_BEFORE,
    )
    return int((await session.execute(stmt)).scalar_one())


async def user_insights(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    source: GameSource | None = None,
    time_class: TimeClass | None = None,
    t: Thresholds = THRESHOLDS,
) -> InsightsResult:
    ug = user_games(user_id, source, time_class)
    analyzed = await _analyzed_count(session, ug)
    if analyzed < t.min_games:
        return InsightsResult(analyzed, t.min_games, [])
    agg = Aggregates(
        analyzed_games=analyzed,
        motifs=await _motifs(session, ug),
        phases=await _phases(session, ug, t),
        time=await _time(session, ug, t),
        openings=await _openings(session, ug),
        conversion=await _conversion(session, ug, t),
    )
    insights = []
    for finding in find_weaknesses(agg, t):
        examples = await _finding_examples(session, ug, finding, t)
        available = (
            None if finding.train is None else await _available(session, user_id, finding.train)
        )
        insights.append(Insight(finding, examples, available))
    return InsightsResult(analyzed, t.min_games, insights)
