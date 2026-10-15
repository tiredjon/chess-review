"""hanging_piece: ход забирает фигуру, которую соперник не может выгодно отбить.

squares/pieces: (бьющая фигура, взятая фигура) — обе на поле взятия.
"""

from collections.abc import Sequence

import chess

from app.review.material import see
from app.review.motifs.base import Motif, MotifType, piece_at, realized_gain, value


def _recaptured_value(board: chess.Board, move: chess.Move) -> int | None:
    """Сколько стоила фигура, взятая соперником прошлым ходом на этом же поле;
    None — прошлый ход не был взятием на этом поле (или истории нет)."""
    if not board.move_stack or board.peek().to_square != move.to_square:
        return None
    previous = board.copy()
    last = previous.pop()
    if not previous.is_capture(last):
        return None
    taken = previous.piece_at(last.to_square)
    return None if taken is None else value(taken)


def detect(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    if not board.is_capture(move) or board.is_en_passant(move):
        return []
    captured = piece_at(board, move.to_square)
    if captured.piece_type in (chess.PAWN, chess.KING):
        return []
    # Не висящая, если соперник выгодно отбивает (размен или «выигрыш качества»).
    if see(board, move) < value(captured):
        return []
    # Взятие в ответ на взятие — обычный размен, если забираем не больше отданного.
    recaptured = _recaptured_value(board, move)
    if recaptured is not None and value(captured) <= recaptured:
        return []
    return [
        Motif(
            type=MotifType.HANGING_PIECE,
            squares=(move.to_square, move.to_square),
            pieces=(piece_at(board, move.from_square), captured),
            gain_cp=realized_gain(board, [move, *pv], plies=1),
            line=(move,),
        )
    ]
