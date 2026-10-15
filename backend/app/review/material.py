"""Материал и размен на поле (SEE, static exchange evaluation). Значения в пешках."""

import chess

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def material(board: chess.Board, color: chess.Color) -> int:
    return sum(value * len(board.pieces(piece, color)) for piece, value in PIECE_VALUES.items())


def material_balance(board: chess.Board, color: chess.Color) -> int:
    """Материал `color` минус материал соперника."""
    return material(board, color) - material(board, not color)


def _captured_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    piece = board.piece_type_at(move.to_square)
    return 0 if piece is None else PIECE_VALUES[piece]


def _gain(board: chess.Board, move: chess.Move) -> int:
    """Немедленный выигрыш материала ходом: взятая фигура + бонус превращения."""
    promotion = 0
    if move.promotion is not None:
        promotion = PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN]
    return _captured_value(board, move) + promotion


def _capture_order(board: chess.Board, move: chess.Move) -> tuple[bool, int, int]:
    """Сначала дешёвые фигуры, король — последним; при превращении — в ферзя."""
    piece = board.piece_type_at(move.from_square)
    assert piece is not None
    return (piece == chess.KING, PIECE_VALUES[piece], -(move.promotion or 0))


def _least_valuable_capture(board: chess.Board, square: chess.Square) -> chess.Move | None:
    captures = board.generate_legal_captures(to_mask=chess.BB_SQUARES[square])
    return min(captures, key=lambda move: _capture_order(board, move), default=None)


def see(board: chess.Board, move: chess.Move) -> int:
    """Итог размена на поле хода `move` для стороны, которая его делает.

    Стороны по очереди бьют на этом поле самой дешёвой фигурой и вправе
    остановиться. Взятия — легальные ходы, поэтому связки, рентген и взятия
    королём учитываются сами. Для не-взятия — итог потери фигуры на новом поле.
    """
    gains = [_gain(board, move)]
    work = board.copy(stack=False)
    work.push(move)
    while (reply := _least_valuable_capture(work, move.to_square)) is not None:
        gains.append(_gain(work, reply) - gains[-1])
        work.push(reply)
    # Каждая сторона выбирает: бить дальше или остановиться.
    for index in range(len(gains) - 1, 0, -1):
        gains[index - 1] = -max(-gains[index - 1], gains[index])
    return gains[0]


def best_capture_gain(board: chess.Board, square: chess.Square) -> int:
    """Сколько выигрывает сторона на ходу лучшим взятием на `square` (0 — взятия нет
    или все невыгодны)."""
    captures = board.generate_legal_captures(to_mask=chess.BB_SQUARES[square])
    return max([0, *(see(board, move) for move in captures)])
