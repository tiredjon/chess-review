"""Фазы партии (SPEC §4.6): дебют → миттельшпиль → эндшпиль, только вперёд."""

from collections.abc import Sequence

import chess

from app.review.thresholds import (
    ENDGAME_MAX_MATERIAL,
    ENDGAME_MAX_PIECES_WITHOUT_QUEENS,
    OPENING_MAX_FULLMOVE,
)
from app.review.types import Phase

PIECE_VALUES = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3}

_ORDER = (Phase.OPENING, Phase.MIDDLEGAME, Phase.ENDGAME)


def non_pawn_material(board: chess.Board) -> int:
    """Материал без пешек и королей за обе стороны."""
    return sum(
        value * len(board.pieces(piece, color))
        for piece, value in PIECE_VALUES.items()
        for color in chess.COLORS
    )


def is_endgame(board: chess.Board) -> bool:
    if non_pawn_material(board) <= ENDGAME_MAX_MATERIAL:
        return True
    if board.queens:
        return False
    pieces = board.occupied & ~board.pawns & ~board.kings
    return chess.popcount(pieces) <= ENDGAME_MAX_PIECES_WITHOUT_QUEENS


def position_phase(board: chess.Board, *, in_book: bool = True) -> Phase:
    """Фаза отдельной позиции без учёта истории партии."""
    if is_endgame(board):
        return Phase.ENDGAME
    # «Пока не разменяны ферзи»: дебют заканчивается, когда ферзей на доске нет.
    if in_book and board.fullmove_number <= OPENING_MAX_FULLMOVE and board.queens:
        return Phase.OPENING
    return Phase.MIDDLEGAME


def game_phases(positions: Sequence[chess.Board], book_plies: int | None = None) -> list[Phase]:
    """Фаза каждой позиции партии; фаза хода — фаза позиции перед ним.

    `book_plies` — сколько первых полуходов книжные (None — книга неизвестна,
    дебют ограничен только номером хода). Ход, выводящий из книги, ещё дебют.
    """
    phases: list[Phase] = []
    current = 0
    for index, board in enumerate(positions):
        in_book = book_plies is None or index <= book_plies
        current = max(current, _ORDER.index(position_phase(board, in_book=in_book)))
        phases.append(_ORDER[current])
    return phases
