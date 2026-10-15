"""fork: сходившая фигура нападает на две и более ценные цели (король — тоже цель).

Вилкой не считается, если соперник выгодно забирает саму вилочную фигуру.
squares/pieces: (вилочная фигура, цели…).
"""

from collections.abc import Sequence

import chess

from app.review.material import best_capture_gain
from app.review.motifs.base import (
    Motif,
    MotifType,
    after,
    is_valuable_target,
    motif_line,
    piece_at,
    realized_gain,
)


def detect(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    position = after(board, move)
    square = move.to_square
    forker = piece_at(position, square)
    # В `position` ходит соперник: может ли он выгодно взять вилочную фигуру.
    if best_capture_gain(position, square) > 0:
        return []
    targets = [
        target
        for target in chess.SquareSet(
            position.attacks(square) & position.occupied_co[not forker.color]
        )
        if is_valuable_target(position, target, forker)
    ]
    if len(targets) < 2:
        return []
    line = [move, *pv]
    return [
        Motif(
            type=MotifType.FORK,
            squares=(square, *targets),
            pieces=(forker, *(piece_at(position, t) for t in targets)),
            gain_cp=realized_gain(board, line),
            line=motif_line(board, line),
        )
    ]
