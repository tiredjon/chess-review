"""SQL тренажёра эндшпиля: позиции из своих партий, прогресс по попыткам, запись попытки."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import chess
from sqlalchemy import Integer, and_, case, cast, func, or_, select, true
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Analysis, AnalysisStatus, Color, EndgameAttempt, Game, Move
from app.endgames.catalog import Goal
from app.endgames.rules import DRAW_GOAL_MIN, SOURCE_CLASSES, goal_for
from app.review.types import Phase

Source = Literal["catalog", "game"]


@dataclass(frozen=True, slots=True)
class Progress:
    attempts: int = 0
    successes: int = 0


@dataclass(frozen=True, slots=True)
class GamePosition:
    key: str
    fen: str
    goal: Goal
    game_id: uuid.UUID
    ply: int
    played_at: datetime | None
    opponent: str
    san: str
    best_san: str | None
    win_before: float
    pieces: int
    progress: Progress


async def progress(
    session: AsyncSession, user_id: uuid.UUID, source: Source, keys: list[str] | None = None
) -> dict[str, Progress]:
    """Попытки и успехи по ключам источника (`keys=None` — все)."""
    stmt = (
        select(
            EndgameAttempt.key,
            func.count(),
            func.coalesce(func.sum(cast(EndgameAttempt.success, Integer)), 0),
        )
        .where(EndgameAttempt.user_id == user_id, EndgameAttempt.source == source)
        .group_by(EndgameAttempt.key)
    )
    if keys is not None:
        stmt = stmt.where(EndgameAttempt.key.in_(keys))
    rows = await session.execute(stmt)
    return {key: Progress(int(n), int(ok)) for key, n, ok in rows}


async def game_positions(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int
) -> list[GamePosition]:
    """Свой ход в эндшпиле класса mistake / blunder (или miss) с win% до хода ≥ 35 — из
    последнего готового анализа партии; одна позиция на партию — ход с наибольшей потерей
    win% (при равенстве — более ранний); свежие партии первыми."""
    latest = (
        select(Analysis.id)
        .where(Analysis.game_id == Game.id, Analysis.status == AnalysisStatus.DONE)
        .order_by(Analysis.created_at.desc(), Analysis.id)
        .limit(1)
        .lateral("la")
    )
    side = func.split_part(Move.fen_before, " ", 2)
    own = side == case((Game.user_color == Color.WHITE, "w"), else_="b")
    picked = (
        select(
            Move.id.label("move_id"),
            Move.fen_before,
            Move.ply,
            Move.san,
            Move.best_san,
            Move.win_before,
            Game.id.label("game_id"),
            Game.played_at,
            Game.created_at,
            case((Game.user_color == Color.WHITE, Game.black), else_=Game.white).label("opponent"),
        )
        .select_from(Game)
        .join(latest, true())
        .join(Move, Move.analysis_id == latest.c.id)
        .where(
            Game.user_id == user_id,
            Game.user_color.is_not(None),
            Move.phase == Phase.ENDGAME,
            or_(Move.move_class.in_(SOURCE_CLASSES), Move.is_miss),
            Move.win_before >= DRAW_GOAL_MIN,
            own,
        )
        .ext(distinct_on(Game.id))
        .order_by(Game.id, (Move.win_before - Move.win_after).desc(), Move.ply)
        .subquery("picked")
    )
    stmt = (
        select(picked)
        .order_by(
            picked.c.played_at.desc().nulls_last(),
            picked.c.created_at.desc(),
            picked.c.game_id,
        )
        .limit(limit)
    )
    rows = (await session.execute(stmt)).mappings().all()
    stats = await progress(session, user_id, "game", [str(row["move_id"]) for row in rows])
    result = []
    for row in rows:
        goal = goal_for(row["win_before"])
        if goal is None:  # pragma: no cover — отсечено в SQL
            continue
        key = str(row["move_id"])
        result.append(
            GamePosition(
                key=key,
                fen=row["fen_before"],
                goal=goal,
                game_id=row["game_id"],
                ply=row["ply"],
                played_at=row["played_at"],
                opponent=row["opponent"],
                san=row["san"],
                best_san=row["best_san"],
                win_before=round(float(row["win_before"]), 1),
                pieces=chess.popcount(chess.Board(row["fen_before"]).occupied),
                progress=stats.get(key, Progress()),
            )
        )
    return result


async def own_move_exists(session: AsyncSession, user_id: uuid.UUID, move_id: int) -> bool:
    """Ход есть, партия — пользователя, и ход сделал он сам."""
    side = func.split_part(Move.fen_before, " ", 2)
    stmt = (
        select(Move.id)
        .join(Analysis, Analysis.id == Move.analysis_id)
        .join(Game, Game.id == Analysis.game_id)
        .where(
            Move.id == move_id,
            Game.user_id == user_id,
            and_(
                Game.user_color.is_not(None),
                side == case((Game.user_color == Color.WHITE, "w"), else_="b"),
            ),
        )
    )
    return (await session.execute(stmt)).first() is not None


async def add_attempt(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    source: Source,
    key: str,
    goal: Goal,
    success: bool,
    plies: int,
) -> Progress:
    session.add(
        EndgameAttempt(
            user_id=user_id, source=source, key=key, goal=goal, success=success, plies=plies
        )
    )
    await session.flush()
    stats = await progress(session, user_id, source, [key])
    await session.commit()
    return stats.get(key, Progress())
