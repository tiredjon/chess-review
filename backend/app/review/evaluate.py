"""Оценки позиций партии → оценка, win% и точность каждого хода, точность партии."""

from collections.abc import Sequence
from dataclasses import dataclass

import chess
from chess.engine import Cp, Mate, Score

from app.review.accuracy import aggregate_accuracy, move_accuracy, volatility_weights
from app.review.phases import game_phases
from app.review.types import EngineLine, Phase, PositionEval
from app.review.winprob import win_percent


@dataclass(frozen=True, slots=True)
class MoveEval:
    ply: int  # с 1
    fullmove: int  # номер полного хода, как в записи партии
    move: chess.Move
    san: str
    color: chess.Color
    fen_before: str
    # Оценки и win% — с точки зрения ходящего (SPEC §4.1).
    eval_before: Score
    eval_after: Score
    win_before: float
    win_after: float
    accuracy: float
    # Вес хода в точности партии (волатильность, §4.4).
    weight: float
    phase: Phase
    # MultiPV позиции перед ходом, лучшая линия первой.
    lines: tuple[EngineLine, ...]
    # MultiPV позиции после хода — с точки зрения соперника (его лучший ответ первым).
    lines_after: tuple[EngineLine, ...]

    @property
    def best_move(self) -> chess.Move | None:
        if not self.lines or not self.lines[0].pv:
            return None
        return self.lines[0].pv[0]


@dataclass(frozen=True, slots=True)
class GameEval:
    moves: list[MoveEval]
    accuracy: dict[chess.Color, float | None]
    phase_accuracy: dict[chess.Color, dict[Phase, float | None]]


def replay(start: chess.Board, moves: Sequence[chess.Move]) -> list[chess.Board]:
    """Все позиции партии: стартовая и после каждого хода (с историей ходов)."""
    board = start.copy()
    positions = [board.copy()]
    for move in moves:
        board.push(move)
        positions.append(board.copy())
    return positions


def terminal_eval(board: chess.Board) -> PositionEval | None:
    """Оценка финальной позиции без движка; None, если партия продолжается."""
    outcome = board.outcome()
    if outcome is None:
        return None
    # В обычных шахматах победитель бывает только при мате — его получила сторона на ходу.
    return PositionEval(score=Mate(0) if outcome.winner is not None else Cp(0))


def evaluate_game(
    start: chess.Board,
    moves: Sequence[chess.Move],
    evals: Sequence[PositionEval],
    *,
    book_plies: int | None = None,
) -> GameEval:
    """`evals[i]` — оценка позиции после i полуходов, с точки зрения стороны на ходу."""
    if len(evals) != len(moves) + 1:
        raise ValueError(f"нужно {len(moves) + 1} оценок позиций, получено {len(evals)}")

    positions = replay(start, moves)
    phases = game_phases(positions, book_plies)
    white_wins = [
        win_percent(pe.score if board.turn == chess.WHITE else -pe.score)
        for board, pe in zip(positions, evals, strict=True)
    ]
    weights = volatility_weights(white_wins)

    result: list[MoveEval] = []
    for index, move in enumerate(moves):
        board = positions[index]
        before = evals[index].score
        after = -evals[index + 1].score
        win_before, win_after = win_percent(before), win_percent(after)
        result.append(
            MoveEval(
                ply=index + 1,
                fullmove=board.fullmove_number,
                move=move,
                san=board.san(move),
                color=board.turn,
                fen_before=board.fen(),
                eval_before=before,
                eval_after=after,
                win_before=win_before,
                win_after=win_after,
                accuracy=move_accuracy(win_before, win_after),
                weight=weights[index],
                phase=phases[index],
                lines=evals[index].lines,
                lines_after=evals[index + 1].lines,
            )
        )

    return GameEval(
        moves=result,
        accuracy={
            color: aggregate_accuracy((m.accuracy, m.weight) for m in result if m.color == color)
            for color in chess.COLORS
        },
        phase_accuracy={
            color: {
                phase: aggregate_accuracy(
                    (m.accuracy, m.weight) for m in result if m.color == color and m.phase == phase
                )
                for phase in Phase
            }
            for color in chess.COLORS
        },
    )
