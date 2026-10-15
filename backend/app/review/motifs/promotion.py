"""promotion и promotion_threat.

- promotion: ход — превращение пешки; squares/pieces: (новая фигура,).
- promotion_threat: пешка вышла на предпоследнюю горизонталь и следующим ходом
  может превратиться (вперёд или со взятием); `line` = (ход, Move.null(), превращение);
  squares/pieces: (пешка,).
"""

from collections.abc import Sequence

import chess

from app.review.motifs.base import Motif, MotifType, after, piece_at, realized_gain


def detect(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    position = after(board, move)
    pawn = piece_at(position, move.to_square)
    if move.promotion is not None:
        return [
            Motif(
                type=MotifType.PROMOTION,
                squares=(move.to_square,),
                pieces=(pawn,),
                gain_cp=realized_gain(board, [move, *pv], plies=1),
                line=(move,),
            )
        ]
    seventh = 6 if pawn.color == chess.WHITE else 1
    if pawn.piece_type != chess.PAWN or chess.square_rank(move.to_square) != seventh:
        return []
    position.push(chess.Move.null())
    promotions = [
        m
        for m in position.legal_moves
        if m.from_square == move.to_square and m.promotion == chess.QUEEN
    ]
    if not promotions:
        return []
    # Предпочитаем ход вперёд, затем взятие.
    promote = min(promotions, key=position.is_capture)
    return [
        Motif(
            type=MotifType.PROMOTION_THREAT,
            squares=(move.to_square,),
            pieces=(pawn,),
            gain_cp=None,
            line=(move, chess.Move.null(), promote),
        )
    ]
