"""Классификация ходов (SPEC §4.5). Проверки идут по порядку, первое совпадение — класс.

Δ — потеря win% ходящим: `max(0, win_before − win_after)`, где win_before —
оценка позиции при лучшей игре, win_after — после сыгранного хода.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.review.evaluate import MoveEval
from app.review.openings import OpeningBook
from app.review.sacrifice import Sacrifice, find_sacrifice
from app.review.thresholds import (
    BOOK_MAX_FULLMOVE,
    BRILLIANT_MAX_DELTA,
    BRILLIANT_MAX_WIN_BEFORE,
    BRILLIANT_MIN_EVAL_CP,
    EXCELLENT_MAX_DELTA,
    GOOD_MAX_DELTA,
    GREAT_MIN_GAP,
    INACCURACY_MAX_DELTA,
    LOSING_MAX_WIN,
    MISS_MIN_DELTA,
    MISTAKE_MAX_DELTA,
    WINNING_MIN_WIN,
)
from app.review.types import MoveClass
from app.review.winprob import score_to_cp, win_percent

_ERRORS = frozenset({MoveClass.MISTAKE, MoveClass.BLUNDER})


@dataclass(frozen=True, slots=True)
class MoveClassification:
    move_class: MoveClass
    # Соперник только что ошибся, а игрок не наказал (флаг поверх класса).
    is_miss: bool = False
    # Жертва, если ход лучший или почти лучший (Δ ≤ 2) и жертвует материал.
    sacrifice: Sacrifice | None = None


def win_loss(move: MoveEval) -> float:
    """Δ: сколько win% потерял ходящий."""
    return max(0.0, move.win_before - move.win_after)


def outcome(win: float) -> int:
    """−1 проигрыш, 0 ничья, 1 выигрыш."""
    if win < LOSING_MAX_WIN:
        return -1
    if win > WINNING_MIN_WIN:
        return 1
    return 0


def reply_line(move: MoveEval) -> tuple[chess.Move, ...]:
    """Линия после хода: продолжение PV1, если сыгран лучший ход (§4.5 — «в PV1»),
    иначе PV1 позиции после хода."""
    if move.lines and move.lines[0].pv[:1] == (move.move,):
        return move.lines[0].pv[1:]
    if move.lines_after:
        return move.lines_after[0].pv
    return ()


def is_great(move: MoveEval) -> bool:
    """Лучший ход — единственный (второй вариант хуже на ≥ GREAT_MIN_GAP) или меняет результат."""
    if len(move.lines) < 2:
        return False
    best, second = win_percent(move.lines[0].score), win_percent(move.lines[1].score)
    return best - second >= GREAT_MIN_GAP or outcome(best) > outcome(second)


def classify_move(
    move: MoveEval,
    *,
    in_book: bool = False,
    previous: MoveClass | None = None,
    prior: chess.Board | None = None,
) -> MoveClassification:
    """`in_book` — позиция после хода есть в книге; `previous` — класс хода соперника
    перед ним; `prior` — позиция до этого хода соперника."""
    delta = win_loss(move)
    is_miss = previous in _ERRORS and delta >= MISS_MIN_DELTA
    board = chess.Board(move.fen_before)
    is_best = move.best_move == move.move

    sacrifice = None
    if is_best or delta <= BRILLIANT_MAX_DELTA:
        sacrifice = find_sacrifice(board, move.move, reply_line(move), prior)

    def result(move_class: MoveClass) -> MoveClassification:
        return MoveClassification(move_class, is_miss=is_miss, sacrifice=sacrifice)

    if in_book and move.fullmove <= BOOK_MAX_FULLMOVE:
        return result(MoveClass.BOOK)
    if board.legal_moves.count() == 1:
        return result(MoveClass.FORCED)
    if (
        sacrifice is not None
        and score_to_cp(move.eval_after) >= BRILLIANT_MIN_EVAL_CP
        and move.win_before < BRILLIANT_MAX_WIN_BEFORE
    ):
        return result(MoveClass.BRILLIANT)
    if is_best:
        return result(MoveClass.GREAT if is_great(move) else MoveClass.BEST)
    for move_class, limit in (
        (MoveClass.EXCELLENT, EXCELLENT_MAX_DELTA),
        (MoveClass.GOOD, GOOD_MAX_DELTA),
        (MoveClass.INACCURACY, INACCURACY_MAX_DELTA),
        (MoveClass.MISTAKE, MISTAKE_MAX_DELTA),
    ):
        if delta <= limit:
            return result(move_class)
    return result(MoveClass.BLUNDER)


def classify_game(
    moves: Sequence[MoveEval], book: OpeningBook | None = None
) -> list[MoveClassification]:
    """Классы всех ходов партии; без книги класс `book` не ставится."""
    result: list[MoveClassification] = []
    for index, move in enumerate(moves):
        in_book = book is not None and book.is_book(chess.Board(move.fen_before), move.move)
        prior = chess.Board(moves[index - 1].fen_before) if index > 0 else None
        classification = classify_move(
            move,
            in_book=in_book,
            previous=result[-1].move_class if result else None,
            prior=prior,
        )
        result.append(classification)
    return result
