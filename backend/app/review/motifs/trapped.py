"""trapped_piece: после хода фигура соперника под боем, а любой её ход —
потеря (по SEE). До хода она такой не была.

Пешки и король не считаются; если ход — шах, мотив не ищется (соперник
обязан отвечать на шах, «ловушка» тут не при чём).
squares/pieces: (сходившая фигура, пойманная фигура).
"""

from collections.abc import Sequence

import chess

from app.review.material import capture_gain, see
from app.review.motifs.base import Motif, MotifType, after, motif_line, piece_at, realized_gain


def is_trapped(board: chess.Board, square: chess.Square) -> bool:
    """Фигура стороны на ходу на `square` под боем и не может уйти без потери."""
    if capture_gain(board, not board.turn, square) <= 0:
        return False
    return all(see(board, move) < 0 for move in board.legal_moves if move.from_square == square)


def detect(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    position = after(board, move)
    if position.is_check():
        return []
    opponent = position.turn
    # Та же позиция до хода, но с ходом соперника — была ли фигура поймана раньше.
    before = board.copy(stack=False)
    before.push(chess.Move.null())
    candidates = position.occupied_co[opponent] & ~position.pawns & ~position.kings
    line = [move, *pv]
    return [
        Motif(
            type=MotifType.TRAPPED_PIECE,
            squares=(move.to_square, square),
            pieces=(piece_at(position, move.to_square), piece_at(position, square)),
            gain_cp=realized_gain(board, line),
            line=motif_line(board, line),
        )
        for square in chess.SquareSet(candidates)
        if is_trapped(position, square) and not is_trapped(before, square)
    ]
