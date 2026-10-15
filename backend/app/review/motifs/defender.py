"""removing_defender и overload: защитник перестаёт защищать, и фигура достаётся.

Линия: ход → ответ соперника → взятие ходящей стороной на другом поле с
выигрышем материала. Выигранная фигура стояла на этом поле ещё до хода, взять
её с выгодой тогда было нельзя, а защищал её в том числе:
- removing_defender — защитник, которого ход забрал;
  squares/pieces: (бьющая фигура, снятый защитник, выигранная фигура);
- overload — защитник, ушедший ответом (взял на другом поле) и больше не
  защищающий её; squares/pieces: (бьющая фигура, перегруженный защитник на новом
  поле, выигранная фигура).
"""

from collections.abc import Sequence

import chess

from app.review.material import capture_gain
from app.review.motifs.base import Motif, MotifType, legal_prefix, piece_at, realized_gain


def detect(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    line = legal_prefix(board, [move, *pv])
    if len(line) < 3:
        return []
    reply, win = line[1], line[2]
    mover = board.turn
    position = board.copy(stack=False)
    position.push(move)
    position.push(reply)
    target = win.to_square
    if target == move.to_square or not position.is_capture(win) or position.is_en_passant(win):
        return []
    won = piece_at(position, target)
    # Выигранная фигура стояла там до хода (а не пришла туда ответом) и не висела.
    gain = realized_gain(board, line)
    if (
        won.piece_type == chess.PAWN
        or board.piece_at(target) != won
        or capture_gain(board, mover, target) > 0
        or gain <= 0
    ):
        return []

    defenders = board.attackers(not mover, target)
    capturer = piece_at(position, win.from_square)
    if board.is_capture(move) and move.to_square in defenders:
        kind, defender_square, defender = (
            MotifType.REMOVING_DEFENDER,
            move.to_square,
            piece_at(board, move.to_square),
        )
    elif reply.from_square in defenders and target not in position.attacks(reply.to_square):
        kind, defender_square, defender = (
            MotifType.OVERLOAD,
            reply.to_square,
            piece_at(position, reply.to_square),
        )
    else:
        return []
    return [
        Motif(
            type=kind,
            squares=(win.from_square, defender_square, target),
            pieces=(capturer, defender, won),
            gain_cp=gain,
            line=tuple(line[:3]),
        )
    ]
