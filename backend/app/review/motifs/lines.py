"""pin и skewer: сходившая дальнобойная фигура бьёт по линии через две фигуры соперника.

- pin: передняя дешевле задней (или задняя — король, абсолютная связка);
  squares/pieces: (связывающая, связанная, фигура за ней).
- skewer: передняя дороже задней (или передняя — король); задняя после ухода
  передней достаётся с выгодой; squares/pieces: (атакующая, передняя, задняя).

Считаются только новые линии: та же пара под ударом с исходного поля фигуры
(сдвиг слона вдоль связки) — не новый мотив. Если соперник выгодно забирает
атакующую фигуру, мотива нет.
"""

from collections.abc import Sequence

import chess

from app.review.material import best_capture_gain
from app.review.motifs.base import (
    Motif,
    MotifType,
    after,
    motif_line,
    piece_at,
    realized_gain,
    value,
)

_DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))
_ORTHOGONAL = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIRECTIONS = {
    chess.BISHOP: _DIAGONAL,
    chess.ROOK: _ORTHOGONAL,
    chess.QUEEN: _DIAGONAL + _ORTHOGONAL,
}


def _first_two(board: chess.Board, square: chess.Square, step: tuple[int, int]) -> list[int]:
    found: list[int] = []
    file, rank = chess.square_file(square), chess.square_rank(square)
    while len(found) < 2:
        file, rank = file + step[0], rank + step[1]
        if not (0 <= file < 8 and 0 <= rank < 8):
            break
        target = chess.square(file, rank)
        if board.piece_at(target) is not None:
            found.append(target)
    return found


def line_pairs(board: chess.Board, square: chess.Square) -> list[tuple[int, int]]:
    """Пары (передняя, задняя) фигур соперника на лучах дальнобойной фигуры."""
    piece = piece_at(board, square)
    pairs = []
    for step in _DIRECTIONS.get(piece.piece_type, ()):
        found = _first_two(board, square, step)
        if len(found) == 2 and all(piece_at(board, s).color != piece.color for s in found):
            pairs.append((found[0], found[1]))
    return pairs


def _is_pin(board: chess.Board, front: chess.Square, back: chess.Square) -> bool:
    first, second = piece_at(board, front), piece_at(board, back)
    if first.piece_type in (chess.KING, chess.PAWN):
        return False
    return second.piece_type == chess.KING or value(second) > value(first)


def _is_skewer(
    board: chess.Board, front: chess.Square, back: chess.Square, attacker: chess.Piece
) -> bool:
    first, second = piece_at(board, front), piece_at(board, back)
    if second.piece_type in (chess.KING, chess.PAWN):
        return False
    if first.piece_type != chess.KING and value(first) <= value(second):
        return False
    # Передняя фигура уйдёт с линии — её защиту задней не считаем.
    defenders = board.attackers(second.color, back) & ~chess.BB_SQUARES[front]
    return value(second) >= value(attacker) or not defenders


def _detect(
    board: chess.Board, move: chess.Move, pv: Sequence[chess.Move], kind: MotifType
) -> list[Motif]:
    position = after(board, move)
    square = move.to_square
    attacker = piece_at(position, square)
    if attacker.piece_type not in _DIRECTIONS or best_capture_gain(position, square) > 0:
        return []
    old = set(line_pairs(board, move.from_square))
    line = [move, *pv]
    motifs = []
    for front, back in line_pairs(position, square):
        if (front, back) in old:
            continue
        if kind is MotifType.PIN and not _is_pin(position, front, back):
            continue
        if kind is MotifType.SKEWER and not _is_skewer(position, front, back, attacker):
            continue
        motifs.append(
            Motif(
                type=kind,
                squares=(square, front, back),
                pieces=(attacker, piece_at(position, front), piece_at(position, back)),
                gain_cp=realized_gain(board, line),
                line=motif_line(board, line),
            )
        )
    return motifs


def detect_pin(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    return _detect(board, move, pv, MotifType.PIN)


def detect_skewer(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    return _detect(board, move, pv, MotifType.SKEWER)
