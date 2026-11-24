"""Пешечные прорывы (`app/plans/breaks.py`): готов ли ход сейчас или его надо подготовить."""

import chess
import pytest

from app.plans.breaks import MAX_BREAKS_PER_SIDE, as_mover, pawn_breaks, side_name
from app.plans.pawns import pawn_facts
from app.plans.types import PawnBreak
from tests.plans_lines import LINES, board_of


def breaks_of(board: chess.Board) -> list[PawnBreak]:
    return pawn_breaks(board, pawn_facts(board))


def by_uci(board: chess.Board) -> dict[str, PawnBreak]:
    return {b.uci: b for b in breaks_of(board)}


def test_najdorf_breaks() -> None:
    """Найдорф 6.Be2 e5: у белых f2–f4 против e5, у чёрных …d5 и подготовка …f5."""
    assert breaks_of(board_of("najdorf_be2_e5")) == [
        PawnBreak(side="white", uci="f2f4", san="f4", target="e5", legal_now=True),
        PawnBreak(side="black", uci="d6d5", san="d5", target="e4", legal_now=True),
        PawnBreak(side="black", uci="f7f5", san=None, target="e4", legal_now=False),
    ]


def test_pianissimo_d4_needs_preparation() -> None:
    """Пьяниссимо: d3–d4 сразу проигрывает пешку (SEE < 0), значит — «готовить»."""
    found = by_uci(board_of("giuoco_pianissimo"))
    assert found["d3d4"].legal_now is False
    assert found["d3d4"].san is None
    assert found["d3d4"].target == "e5"
    assert found["d6d5"].legal_now is True
    assert found["d6d5"].san == "d5"


def test_kid_c5_defended_by_d6() -> None:
    """Староиндийская: c4–c5 легален, но поле c5 бьёт d6 — прорыв не готов."""
    found = by_uci(board_of("kid_mar_del_plata"))
    assert found["c4c5"].legal_now is False
    assert found["c4c5"].target == "d6"
    assert found["f7f5"].legal_now is False


def test_capture_is_a_break() -> None:
    found = by_uci(board_of("qgd_orthodox"))
    assert found["c4d5"] == PawnBreak(
        side="white", uci="c4d5", san="cxd5", target="d5", legal_now=True
    )
    assert found["d5c4"].san == "dxc4"


def test_chain_base_is_preferred_target() -> None:
    """Французская с продвижением: удар по основанию цепи d4 — первым у чёрных."""
    black = [b for b in breaks_of(board_of("french_advance")) if b.side == "black"]
    assert black[0].uci == "c5d4"
    assert black[0].target == "d4"
    white = {b.uci for b in breaks_of(board_of("french_advance")) if b.side == "white"}
    assert "c3c4" in white


def test_side_not_to_move_gets_san() -> None:
    """В Карлсбаде ходят чёрные, но готовый e3–e4 белых тоже записан в SAN."""
    board = board_of("qgd_exchange")
    assert board.turn == chess.BLACK
    assert by_uci(board)["e3e4"].san == "e4"


def test_no_breaks_without_contact() -> None:
    assert breaks_of(chess.Board()) == []
    # Пешка на предпоследней горизонтали — это превращение, не прорыв.
    assert breaks_of(chess.Board("4k3/8/8/8/8/8/3p4/4K3 b - - 0 1")) == []


def test_as_mover() -> None:
    board = chess.Board()
    assert as_mover(board, chess.WHITE) is board
    black = as_mover(board, chess.BLACK)
    assert black is not None
    assert black.turn == chess.BLACK
    assert board.turn == chess.WHITE  # исходная доска не тронута
    # Белые под шахом: отдать ход чёрным нельзя — позиция станет невозможной.
    check = chess.Board("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
    assert as_mover(check, chess.BLACK) is None


def test_side_in_check_has_no_ready_breaks() -> None:
    """Если очередь соперника передать нельзя, его прорывы — только «готовить»."""
    board = chess.Board("4k3/8/8/3p4/4P3/8/4r3/4K3 w - - 0 1")
    found = by_uci(board)
    assert found["d5e4"].legal_now is False
    assert found["e4d5"].legal_now is False  # белые под шахом: e4xd5 не спасает короля


@pytest.mark.parametrize("line", sorted(LINES))
def test_break_invariants(line: str) -> None:
    board = board_of(line)
    found = breaks_of(board)
    for color in chess.COLORS:
        mine = [b for b in found if b.side == side_name(color)]
        assert len(mine) <= MAX_BREAKS_PER_SIDE
    ready_seen_after_prepare = False
    for brk in found:
        move = chess.Move.from_uci(brk.uci)
        piece = board.piece_at(move.from_square)
        assert piece is not None
        assert piece.piece_type == chess.PAWN
        assert side_name(piece.color) == brk.side
        target = board.piece_at(chess.parse_square(brk.target))
        assert target == chess.Piece(chess.PAWN, not piece.color)
        if brk.legal_now:
            mover = as_mover(board, piece.color)
            assert mover is not None
            assert mover.san(move) == brk.san
            assert not ready_seen_after_prepare
        else:
            assert brk.san is None
            ready_seen_after_prepare = True
