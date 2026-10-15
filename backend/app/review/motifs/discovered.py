"""Вскрытое нападение и двойной шах.

- discovered_check / discovered_attack: ход уводит фигуру с линии своей
  дальнобойной фигуры, и та теперь бьёт короля / ценную цель;
  squares/pieces: (открытая дальнобойная, цель, сходившая фигура).
- double_check: шах сразу двумя фигурами; squares/pieces: (шахующие…, король).
"""

from collections.abc import Sequence

import chess

from app.review.motifs.base import (
    Motif,
    MotifType,
    after,
    is_valuable_target,
    motif_line,
    piece_at,
    realized_gain,
)

_SLIDERS = (chess.BISHOP, chess.ROOK, chess.QUEEN)


def detect_discovered(
    board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]
) -> list[Motif]:
    position = after(board, move)
    mover = board.turn
    moved = piece_at(position, move.to_square)
    line = [move, *pv]
    motifs = []
    for slider_type in _SLIDERS:
        for square in position.pieces(slider_type, mover):
            if square == move.to_square:
                continue
            slider = piece_at(position, square)
            opened = position.attacks(square) & ~board.attacks(square)
            for target in chess.SquareSet(opened & position.occupied_co[not mover]):
                if move.from_square not in chess.SquareSet(chess.between(square, target)):
                    continue
                if not is_valuable_target(position, target, slider):
                    continue
                is_check = piece_at(position, target).piece_type == chess.KING
                motifs.append(
                    Motif(
                        type=MotifType.DISCOVERED_CHECK
                        if is_check
                        else MotifType.DISCOVERED_ATTACK,
                        squares=(square, target, move.to_square),
                        pieces=(slider, piece_at(position, target), moved),
                        gain_cp=realized_gain(board, line),
                        line=motif_line(board, line),
                    )
                )
    return motifs


def detect_double_check(
    board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]
) -> list[Motif]:
    position = after(board, move)
    checkers = list(position.checkers())
    if len(checkers) < 2:
        return []
    king = position.king(position.turn)
    assert king is not None
    line = [move, *pv]
    return [
        Motif(
            type=MotifType.DOUBLE_CHECK,
            squares=(*checkers, king),
            pieces=(*(piece_at(position, s) for s in checkers), piece_at(position, king)),
            gain_cp=realized_gain(board, line),
            line=motif_line(board, line),
        )
    ]
