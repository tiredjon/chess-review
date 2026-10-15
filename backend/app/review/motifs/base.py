"""Типы мотивов и общие помощники детекторов (SPEC §5).

Детектор — чистая функция `detect(board, move, pv) -> list[Motif]`: `board` — позиция
до хода (желательно с историей: по ней узнаются взятия в ответ), `move` — ход,
`pv` — продолжение после него (первым ходит соперник). Мотив описывает, что
**делает сторона, которая ходит**: вилка — её вилка, висящая фигура — фигура,
которую она забирает. «Игрок зевнул фигуру» — это `hanging_piece` в ответе соперника.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import chess

from app.review.material import PIECE_VALUES, material_balance
from app.review.thresholds import MOTIF_GAIN_PLIES


class MotifType(StrEnum):
    HANGING_PIECE = "hanging_piece"
    FORK = "fork"
    PIN = "pin"
    SKEWER = "skewer"
    DISCOVERED_ATTACK = "discovered_attack"
    DISCOVERED_CHECK = "discovered_check"
    DOUBLE_CHECK = "double_check"
    MATE_IN_N = "mate_in_n"
    MATE_THREAT = "mate_threat"
    BACK_RANK = "back_rank"
    TRAPPED_PIECE = "trapped_piece"
    REMOVING_DEFENDER = "removing_defender"
    OVERLOAD = "overload"
    PROMOTION = "promotion"
    PROMOTION_THREAT = "promotion_threat"


@dataclass(frozen=True, slots=True)
class Motif:
    """`squares[i]` ↔ `pieces[i]`; первым — фигура ходящей стороны, затем цели
    (порядок для каждого типа — в его детекторе). `gain_cp` — выигрыш материала
    ходящей стороной в линии, None — мотив не про материал (маты).
    `line` — ход и продолжение, на котором мотив виден; `Move.null()` в линии —
    «любой ход соперника» (для угроз)."""

    type: MotifType
    squares: tuple[chess.Square, ...]
    pieces: tuple[chess.Piece, ...]
    gain_cp: int | None
    line: tuple[chess.Move, ...]


def value(piece: chess.Piece) -> int:
    return PIECE_VALUES[piece.piece_type]


def piece_at(board: chess.Board, square: chess.Square) -> chess.Piece:
    piece = board.piece_at(square)
    assert piece is not None, chess.square_name(square)
    return piece


def after(board: chess.Board, move: chess.Move) -> chess.Board:
    """Позиция после хода, с историей."""
    result = board.copy()
    result.push(move)
    return result


def is_defended(board: chess.Board, square: chess.Square) -> bool:
    """Фигуру на поле защищает своя сторона (без учёта рентгена)."""
    return bool(board.attackers(piece_at(board, square).color, square))


def is_valuable_target(board: chess.Board, square: chess.Square, attacker: chess.Piece) -> bool:
    """Цель, удар по которой что-то выигрывает: король (шах), фигура дороже
    нападающей или незащищённая фигура. Пешки целями не считаются."""
    target = piece_at(board, square)
    if target.piece_type == chess.KING:
        return True
    if target.piece_type == chess.PAWN:
        return False
    return value(target) > value(attacker) or not is_defended(board, square)


def legal_prefix(board: chess.Board, line: Sequence[chess.Move]) -> list[chess.Move]:
    """Начало линии до первого нелегального хода."""
    work = board.copy(stack=False)
    played = []
    for move in line:
        if not work.is_legal(move):
            break
        work.push(move)
        played.append(move)
    return played


def realized_gain(
    board: chess.Board, line: Sequence[chess.Move], plies: int = MOTIF_GAIN_PLIES
) -> int:
    """Выигрыш материала стороной на ходу за первые `plies` полуходов линии, в cp.

    Размен на поле последнего хода доигрывается до конца, если линия его продолжает.
    """
    mover = board.turn
    baseline = material_balance(board, mover)
    played = legal_prefix(board, line)
    count = min(plies, len(played))
    while count and count < len(played) and played[count].to_square == played[count - 1].to_square:
        count += 1
    work = board.copy(stack=False)
    for move in played[:count]:
        work.push(move)
    return (material_balance(work, mover) - baseline) * 100


def motif_line(
    board: chess.Board, line: Sequence[chess.Move], plies: int = MOTIF_GAIN_PLIES
) -> tuple[chess.Move, ...]:
    """Легальное начало линии длиной до `plies` — то, что показывать как мотив."""
    return tuple(legal_prefix(board, line)[:plies])
