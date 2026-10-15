"""Мотивы хода партии в трёх контекстах (SPEC §5):

- played — сам ход игрока с лучшим продолжением после него;
- missed — лучший ход PV1, если сыгран другой (что упущено);
- refutation — лучший ответ соперника после хода (чем наказывается ошибка).
"""

from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.review.classify import reply_line
from app.review.evaluate import MoveEval
from app.review.motifs import detect_all
from app.review.motifs.base import Motif


@dataclass(frozen=True, slots=True)
class MoveMotifs:
    played: tuple[Motif, ...] = ()
    missed: tuple[Motif, ...] = ()
    refutation: tuple[Motif, ...] = ()


def move_motifs(move: MoveEval, board: chess.Board | None = None) -> MoveMotifs:
    """`board` — позиция до хода с историей (по ней видно взятие в ответ);
    по умолчанию — из `move.fen_before` без истории."""
    if board is None:
        board = chess.Board(move.fen_before)
    played = detect_all(board, move.move, reply_line(move))

    missed: tuple[Motif, ...] = ()
    best = move.best_move
    if best is not None and best != move.move:
        missed = detect_all(board, best, move.lines[0].pv[1:])

    refutation: tuple[Motif, ...] = ()
    if move.lines_after and move.lines_after[0].pv:
        position = board.copy()
        position.push(move.move)
        reply, *rest = move.lines_after[0].pv
        refutation = detect_all(position, reply, rest)
    return MoveMotifs(played=played, missed=missed, refutation=refutation)


def game_motifs(moves: Sequence[MoveEval]) -> list[MoveMotifs]:
    """Мотивы всех ходов партии; позиция каждого хода — с ходом соперника в истории."""
    result = []
    for index, move in enumerate(moves):
        board = chess.Board(move.fen_before)
        if index > 0:
            board = chess.Board(moves[index - 1].fen_before)
            board.push(moves[index - 1].move)
        result.append(move_motifs(move, board))
    return result
