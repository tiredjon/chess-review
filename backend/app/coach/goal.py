"""Цель тренера (17.2): рейтинги по площадкам и контролям, активная цель, `achieved_at`.

Рейтинг — `white_elo`/`black_elo` пользователя в его последней партии (по `played_at`, без него
— по времени импорта) в паре площадка × контроль. Учитываются только Chess.com и Lichess:
у PGN-партий (в том числе с ботом) рейтинг не площадки.
"""

import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas_coach import GoalIn, GoalOut, RatingOptionOut
from app.db.models import CoachGoal, Color, Game, GameSource
from app.stats.queries import time_class_sql

GOAL_SOURCES = (GameSource.CHESSCOM, GameSource.LICHESS)


async def ratings(session: AsyncSession, user_id: uuid.UUID) -> list[RatingOptionOut]:
    rating = case((Game.user_color == Color.WHITE, Game.white_elo), else_=Game.black_elo)
    tc = time_class_sql(Game.__table__.c.time_control)
    ts = func.coalesce(Game.played_at, Game.created_at)
    ranked = (
        select(
            Game.source.label("source"),
            tc.label("time_class"),
            rating.label("rating"),
            Game.played_at.label("played_at"),
            func.count().over(partition_by=(Game.source, tc)).label("games"),
            func.row_number()
            .over(partition_by=(Game.source, tc), order_by=(ts.desc(), Game.id))
            .label("rank"),
        )
        .where(
            Game.user_id == user_id,
            Game.source.in_(GOAL_SOURCES),
            Game.user_color.is_not(None),
            rating.is_not(None),
        )
        .subquery()
    )
    rows = await session.execute(
        select(ranked)
        .where(ranked.c.rank == 1)
        .order_by(ranked.c.games.desc(), ranked.c.source, ranked.c.time_class)
    )
    return [
        RatingOptionOut(
            source=row.source.value,
            time_class=row.time_class,
            rating=row.rating,
            games=row.games,
            last_played_at=row.played_at,
        )
        for row in rows
    ]


async def current_rating(
    session: AsyncSession, user_id: uuid.UUID, source: str, time_class: str
) -> int | None:
    for option in await ratings(session, user_id):
        if option.source == source and option.time_class == time_class:
            return option.rating
    return None


async def active_goal(session: AsyncSession, user_id: uuid.UUID) -> CoachGoal | None:
    return await session.scalar(
        select(CoachGoal).where(CoachGoal.user_id == user_id, CoachGoal.archived_at.is_(None))
    )


def valid_tz(tz: str) -> bool:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def goal_out(goal: CoachGoal, current: int) -> GoalOut:
    return GoalOut(
        id=goal.id,
        source=goal.source.value,
        time_class=goal.time_class,
        start_rating=goal.start_rating,
        current_rating=current,
        target_rating=goal.target_rating,
        minutes_per_day=goal.minutes_per_day,
        days_per_week=goal.days_per_week,
        tz=goal.tz,
        created_at=goal.created_at,
        achieved_at=goal.achieved_at,
    )


async def refresh_goal(session: AsyncSession, goal: CoachGoal) -> GoalOut:
    """Текущий рейтинг цели; достигнута впервые — ставит `achieved_at` (коммит — здесь)."""
    current = await current_rating(session, goal.user_id, goal.source.value, goal.time_class)
    value = goal.start_rating if current is None else current
    if goal.achieved_at is None and value >= goal.target_rating:
        goal.achieved_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(goal)
    return goal_out(goal, value)


async def set_goal(
    session: AsyncSession, user_id: uuid.UUID, body: GoalIn, current: int
) -> CoachGoal:
    """Архивирует прежнюю активную цель и создаёт новую (коммит — здесь)."""
    now = datetime.now(UTC)
    await session.execute(
        update(CoachGoal)
        .where(CoachGoal.user_id == user_id, CoachGoal.archived_at.is_(None))
        .values(archived_at=now)
    )
    goal = CoachGoal(
        user_id=user_id,
        source=GameSource(body.source),
        time_class=body.time_class,
        start_rating=current,
        target_rating=body.target_rating,
        minutes_per_day=body.minutes_per_day,
        days_per_week=body.days_per_week,
        tz=body.tz,
    )
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return goal


async def archive_goal(session: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await session.execute(
        update(CoachGoal)
        .where(CoachGoal.user_id == user_id, CoachGoal.archived_at.is_(None))
        .values(archived_at=datetime.now(UTC))
    )
    await session.commit()
    return bool(getattr(result, "rowcount", 0))
