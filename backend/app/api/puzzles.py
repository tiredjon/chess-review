"""Пазлы из ошибок пользователя: следующий пазл и попытка решения."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

import chess
from fastapi import APIRouter, Query, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.deps import CurrentUser, SessionDep
from app.api.errors import ApiError, ErrorCode
from app.api.schemas import (
    AttemptIn,
    AttemptOut,
    PuzzleCounts,
    PuzzleLastMove,
    PuzzleNextOut,
    PuzzleOut,
    PuzzleSource,
)
from app.db.models import Analysis, Color, Game, Move, Puzzle, PuzzleAttempt
from app.puzzles.solution import AttemptError, check_attempt
from app.puzzles.srs import schedule

router = APIRouter(tags=["puzzles"])

# Не больше стольких id в `exclude` (пропущенные в этой сессии пазлы).
MAX_EXCLUDE = 100


def _now() -> datetime:
    return datetime.now(UTC)


async def _streak(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Решённых подряд: попытки после последней неудачной."""
    last_fail = (
        select(func.max(PuzzleAttempt.created_at))
        .where(PuzzleAttempt.user_id == user_id, ~PuzzleAttempt.correct)
        .scalar_subquery()
    )
    streak = await session.scalar(
        select(func.count()).where(
            PuzzleAttempt.user_id == user_id,
            PuzzleAttempt.correct,
            or_(last_fail.is_(None), PuzzleAttempt.created_at > last_fail),
        )
    )
    return streak or 0


async def _counts(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> PuzzleCounts:
    row = (
        await session.execute(
            select(
                func.count().filter(Puzzle.next_review_at <= now).label("due"),
                func.count().filter(Puzzle.next_review_at.is_(None)).label("new"),
                func.count().label("total"),
                func.min(Puzzle.next_review_at).filter(Puzzle.next_review_at > now).label("next"),
            ).where(Puzzle.user_id == user_id)
        )
    ).one()
    return PuzzleCounts(
        due=row.due,
        new=row.new,
        total=row.total,
        streak=await _streak(session, user_id),
        next_review_at=row.next,
    )


def _san_line(fen: str, line: list[str]) -> list[str]:
    board = chess.Board(fen)
    result = []
    for uci in line:
        move = chess.Move.from_uci(uci)
        result.append(board.san(move))
        board.push(move)
    return result


@router.get("/puzzles/next")
async def next_puzzle(
    session: SessionDep,
    user: CurrentUser,
    exclude: Annotated[list[uuid.UUID], Query(max_length=MAX_EXCLUDE)] = [],  # noqa: B006
) -> PuzzleNextOut:
    """Следующий пазл: сначала пора повторить (раньше назначенные первыми), затем новые —
    из более свежих партий. `exclude` — пропущенные клиентом в этой сессии."""
    now = _now()
    prev = aliased(Move)
    due = Puzzle.next_review_at <= now
    stmt = (
        select(Puzzle, Move, Game, prev)
        .outerjoin(Move, Move.id == Puzzle.move_id)
        .outerjoin(Analysis, Analysis.id == Move.analysis_id)
        .outerjoin(Game, Game.id == Analysis.game_id)
        .outerjoin(prev, and_(prev.analysis_id == Move.analysis_id, prev.ply == Move.ply - 1))
        .where(Puzzle.user_id == user.id, or_(due, Puzzle.next_review_at.is_(None)))
        .order_by(
            case((due, 0), else_=1),
            Puzzle.next_review_at,
            Game.played_at.desc().nulls_last(),
            Move.ply,
            Puzzle.id,
        )
        .limit(1)
    )
    if exclude:
        stmt = stmt.where(Puzzle.id.not_in(exclude))
    found = (await session.execute(stmt)).one_or_none()
    counts = await _counts(session, user.id, now)
    if found is None:
        return PuzzleNextOut(puzzle=None, counts=counts)

    puzzle, move, game, prev_move = found
    board = chess.Board(puzzle.fen)
    source = None
    if move is not None and game is not None:
        source = PuzzleSource(
            game_id=game.id,
            ply=move.ply,
            fullmove=board.fullmove_number,
            san=move.san,
            move_class=move.move_class,
            is_miss=move.is_miss,
            opponent=game.black if game.user_color == Color.WHITE else game.white,
            played_at=game.played_at,
        )
    last_move = None
    if prev_move is not None:
        last_move = PuzzleLastMove(
            uci=prev_move.uci, san=prev_move.san, fen_before=prev_move.fen_before
        )
    return PuzzleNextOut(
        puzzle=PuzzleOut(
            id=puzzle.id,
            fen=puzzle.fen,
            color=Color.WHITE if board.turn == chess.WHITE else Color.BLACK,
            themes=puzzle.themes,
            player_moves=(len(puzzle.solution_uci) + 1) // 2,
            hints=[uci[:2] for uci in puzzle.solution_uci[::2]],
            box=puzzle.box,
            attempts=puzzle.attempts,
            next_review_at=puzzle.next_review_at,
            last_move=last_move,
            source=source,
        ),
        counts=counts,
    )


@router.post("/puzzles/{puzzle_id}/attempt")
async def attempt_puzzle(
    puzzle_id: uuid.UUID, body: AttemptIn, session: SessionDep, user: CurrentUser
) -> AttemptOut:
    """Проверка ходов на сервере. Пока ходы верны и решение не закончено — `continue` с
    ответом соперника (ничего не записывается); `solved` / `failed` записывают попытку и
    назначают следующее повторение."""
    puzzle = await session.scalar(
        select(Puzzle).where(Puzzle.id == puzzle_id, Puzzle.user_id == user.id).with_for_update()
    )
    if puzzle is None:
        raise ApiError(status.HTTP_404_NOT_FOUND, ErrorCode.PUZZLE_NOT_FOUND, "Пазл не найден")
    try:
        check = check_attempt(puzzle.fen, puzzle.solution_uci, body.moves_uci, gave_up=body.gave_up)
    except AttemptError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, ErrorCode.PUZZLE_ATTEMPT_INVALID, str(exc)
        ) from exc
    if check.result == "continue":
        await session.rollback()
        return AttemptOut(result="continue", reply_uci=check.reply)

    now = _now()
    solved = check.result == "solved"
    review = schedule(puzzle.box, solved=solved, hint_used=body.hint_used, now=now)
    puzzle.box = review.box
    puzzle.next_review_at = review.next_review_at
    puzzle.attempts += 1
    puzzle.solved = solved
    puzzle.last_attempt_at = now
    session.add(
        PuzzleAttempt(
            puzzle_id=puzzle.id, user_id=user.id, correct=solved, hint_used=body.hint_used
        )
    )
    await session.commit()
    return AttemptOut(
        result=check.result,
        expected_uci=check.expected,
        solution_uci=puzzle.solution_uci,
        solution_san=_san_line(puzzle.fen, puzzle.solution_uci),
        box=review.box,
        next_review_at=review.next_review_at,
        streak=await _streak(session, user.id),
    )
