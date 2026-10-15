"""Детекторы тактических мотивов (SPEC §5) и их применение к ходу.

Детекторы — чистые функции `detect(board, move, pv) -> list[Motif]` (см. `base`).
"""

from collections.abc import Callable, Sequence

import chess

from app.review.motifs import defender, discovered, fork, hanging, lines, mate, promotion, trapped
from app.review.motifs.base import Motif, MotifType

Detector = Callable[[chess.Board, chess.Move, Sequence[chess.Move]], list[Motif]]

DETECTORS: dict[str, Detector] = {
    "hanging_piece": hanging.detect,
    "fork": fork.detect,
    "pin": lines.detect_pin,
    "skewer": lines.detect_skewer,
    "discovered": discovered.detect_discovered,
    "double_check": discovered.detect_double_check,
    "mate": mate.detect_mate,
    "back_rank": mate.detect_back_rank,
    "trapped_piece": trapped.detect,
    "defender": defender.detect,
    "promotion": promotion.detect,
}


_MATE_TYPES = frozenset({MotifType.MATE_IN_N, MotifType.BACK_RANK})


def detect_all(board: chess.Board, move: chess.Move, pv: Sequence[chess.Move]) -> tuple[Motif, ...]:
    """Все мотивы хода `move` из позиции `board` с продолжением `pv`.

    Если ход сам ставит мат, остальные мотивы (вилка, шах…) неважны — только маты.
    """
    if not board.is_legal(move):
        return ()
    motifs = [motif for detect in DETECTORS.values() for motif in detect(board, move, pv)]
    if _gives_mate(board, move):
        motifs = [m for m in motifs if m.type in _MATE_TYPES]
    return tuple(motifs)


def _gives_mate(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        return board.is_checkmate()
    finally:
        board.pop()


__all__ = ["DETECTORS", "Detector", "Motif", "MotifType", "detect_all"]
