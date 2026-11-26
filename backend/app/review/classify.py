"""Классификация ходов (SPEC §4.5). Проверки идут по порядку, первое совпадение — класс.

Δ — потеря win% ходящим: `max(0, win_before − win_after)`, где win_before —
оценка позиции при лучшей игре, win_after — после сыгранного хода.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.review.evaluate import MoveEval
from app.review.material import see
from app.review.openings import OpeningBook
from app.review.sacrifice import Sacrifice, find_sacrifice
from app.review.thresholds import (
    BEST_MAX_DELTA,
    BOOK_MAX_FULLMOVE,
    BRILLIANT_MAX_DELTA,
    BRILLIANT_MAX_WIN_BEFORE,
    BRILLIANT_MIN_EVAL_CP,
    EXCELLENT_MAX_DELTA,
    GOOD_MAX_DELTA,
    GREAT_CRITICAL_MIN_GAP,
    GREAT_MIN_GAP,
    INACCURACY_MAX_DELTA,
    LOSING_MAX_WIN,
    MISS_MIN_DELTA,
    MISS_MIN_WIN_AFTER,
    MISS_MIN_WIN_BEFORE,
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


def is_recapture(
    board: chess.Board,
    move: chess.Move,
    prior: chess.Board | None,
    previous_move: chess.Move | None,
) -> bool:
    """Взятие на поле, где соперник только что взял (`prior` — позиция до его хода)."""
    return (
        prior is not None
        and previous_move is not None
        and prior.is_capture(previous_move)
        and board.is_capture(move)
        and move.to_square == previous_move.to_square
    )


def is_obvious(
    board: chess.Board,
    move: chess.Move,
    prior: chess.Board | None = None,
    previous_move: chess.Move | None = None,
) -> bool:
    """Ход, который находит каждый, — не `great`, даже если он единственный: взятие в ответ
    или взятие с выигрышем материала (подставленная фигура, SEE > 0). Мат — не очевиден."""
    if not board.is_capture(move) or _mates(board, move):
        return False
    return is_recapture(board, move, prior, previous_move) or see(board, move) > 0


def _mates(board: chess.Board, move: chess.Move) -> bool:
    after = board.copy(stack=False)
    after.push(move)
    return after.is_checkmate()


def is_great(move: MoveEval, *, obvious: bool = False, punishing: bool = False) -> bool:
    """Лучший ход — единственный: второй вариант хуже на ≥ GREAT_MIN_GAP win%, или на
    ≥ GREAT_CRITICAL_MIN_GAP в критический момент — ход меняет результат или (`punishing`)
    наказывает ошибку соперника. Очевидный ход (`is_obvious`) — никогда."""
    if obvious or len(move.lines) < 2:
        return False
    best, second = win_percent(move.lines[0].score), win_percent(move.lines[1].score)
    gap = best - second
    critical = punishing or outcome(best) > outcome(second)
    return gap >= GREAT_MIN_GAP or (gap >= GREAT_CRITICAL_MIN_GAP and critical)


def is_miss(move: MoveEval, delta: float, previous: MoveClass | None) -> bool:
    """Соперник ошибся, у игрока был шанс, а он его упустил, не проиграв позицию."""
    return (
        previous in _ERRORS
        and delta >= MISS_MIN_DELTA
        and move.win_before >= MISS_MIN_WIN_BEFORE
        and move.win_after >= MISS_MIN_WIN_AFTER
    )


def classify_move(
    move: MoveEval,
    *,
    in_book: bool = False,
    previous: MoveClass | None = None,
    prior: chess.Board | None = None,
    previous_move: chess.Move | None = None,
) -> MoveClassification:
    """`in_book` — позиция после хода есть в книге; `previous` — класс хода соперника
    перед ним; `prior` — позиция до этого хода соперника, `previous_move` — сам этот ход."""
    delta = win_loss(move)
    missed = is_miss(move, delta, previous)
    board = chess.Board(move.fen_before)
    is_best = move.best_move == move.move

    sacrifice = None
    if is_best or delta <= BRILLIANT_MAX_DELTA:
        sacrifice = find_sacrifice(board, move.move, reply_line(move), prior)

    def result(move_class: MoveClass) -> MoveClassification:
        return MoveClassification(move_class, is_miss=missed, sacrifice=sacrifice)

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
        great = is_great(
            move,
            obvious=is_obvious(board, move.move, prior, previous_move),
            punishing=previous in _ERRORS,
        )
        return result(MoveClass.GREAT if great else MoveClass.BEST)
    for move_class, limit in (
        # Не первый ход движка, но равноценный ему.
        (MoveClass.BEST, BEST_MAX_DELTA),
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
            previous_move=moves[index - 1].move if index > 0 else None,
        )
        result.append(classification)
    return result
