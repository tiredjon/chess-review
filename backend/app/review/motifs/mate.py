"""Маты (SPEC §5, п. 7–8).

- mate_in_n: линия «ход + PV» заканчивается матом от ходящей стороны; N — число
  её ходов в `line`. squares/pieces: (матующая фигура, король).
- mate_threat: ход (не шах) создаёт угрозу мата в 1, которой до хода не было;
  `line` = (ход, Move.null(), матующий ход). squares/pieces: (матующая фигура
  на поле мата, король).
- back_rank: такой мат или угроза — по последней горизонтали: король на своей
  первой линии, перед ним свои фигуры, матует ладья или ферзь с той же линии.
  squares/pieces и line — как у мата/угрозы, на которых он основан.

PV движка с оценкой «мат в N» доходит до мата, поэтому оценка отдельно не нужна.
"""

from collections.abc import Sequence

import chess

from app.review.motifs.base import Motif, MotifType, after, legal_prefix, piece_at


def _mate_line(board: chess.Board, line: Sequence[chess.Move]) -> list[chess.Move] | None:
    """Начало линии до мата ходящей стороной (None — мата нет)."""
    mover = board.turn
    work = board.copy(stack=False)
    for index, move in enumerate(legal_prefix(board, line)):
        work.push(move)
        if work.is_checkmate():
            return list(line[: index + 1]) if work.turn != mover else None
    return None


def _mate_in_one(board: chess.Board) -> chess.Move | None:
    for move in board.legal_moves:
        board.push(move)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            return move
    return None


def _threat(board: chess.Board, move: chess.Move) -> chess.Move | None:
    """Матующий ход, которым ход `move` угрожает (None — угрозы нет или она была)."""
    position = after(board, move)
    if position.is_check() or position.is_game_over():
        return None
    position.push(chess.Move.null())
    threat = _mate_in_one(position)
    if threat is None or _mate_in_one(board.copy(stack=False)) is not None:
        return None
    return threat


def _final(board: chess.Board, line: Sequence[chess.Move]) -> chess.Board:
    work = board.copy(stack=False)
    for move in line:
        work.push(move)
    return work


def _mate_motif(kind: MotifType, final: chess.Board, line: Sequence[chess.Move]) -> Motif:
    king = final.king(final.turn)
    assert king is not None
    mating = line[-1].to_square
    return Motif(
        type=kind,
        squares=(mating, king),
        pieces=(piece_at(final, mating), piece_at(final, king)),
        gain_cp=None,
        line=tuple(line),
    )


def is_back_rank_mate(board: chess.Board) -> bool:
    """`board` — мат стороне на ходу."""
    color = board.turn
    king = board.king(color)
    assert king is not None
    back = 0 if color == chess.WHITE else 7
    if chess.square_rank(king) != back:
        return False
    checkers = list(board.checkers())
    if len(checkers) != 1 or chess.square_rank(checkers[0]) != back:
        return False
    if piece_at(board, checkers[0]).piece_type not in (chess.ROOK, chess.QUEEN):
        return False
    front = back + (1 if color == chess.WHITE else -1)
    file = chess.square_file(king)
    return any(
        board.color_at(chess.square(f, front)) == color
        for f in (file - 1, file, file + 1)
        if 0 <= f < 8
    )


def _mates(
    board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]
) -> list[tuple[MotifType, chess.Board, list[chess.Move]]]:
    """Мат в линии и/или угроза мата: (тип, позиция мата, линия)."""
    found = []
    line = _mate_line(board, [move, *pv])
    if line is not None:
        found.append((MotifType.MATE_IN_N, _final(board, line), line))
    threat = _threat(board, move)
    if threat is not None:
        threat_line = [move, chess.Move.null(), threat]
        found.append((MotifType.MATE_THREAT, _final(board, threat_line), threat_line))
    return found


def detect_mate(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    return [_mate_motif(kind, final, line) for kind, final, line in _mates(board, move, pv)]


def detect_back_rank(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> list[Motif]:
    return [
        _mate_motif(MotifType.BACK_RANK, final, line)
        for _, final, line in _mates(board, move, pv)
        if is_back_rank_mate(final)
    ]
