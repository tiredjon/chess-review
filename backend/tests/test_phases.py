import chess
import pytest

from app.review.phases import game_phases, is_endgame, non_pawn_material, position_phase
from app.review.types import Phase

# Фазы считаются по позиции; номер хода задаётся полем FEN.
MIDDLEGAME_MOVE_15 = "r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/2N1PN2/PP3PPP/R2QKB1R w KQ - 0 15"
QUEENS_TRADED_MOVE_8 = "rnb1kb1r/ppp2ppp/5n2/4p3/4P3/5N2/PPP2PPP/RNB1KB1R w KQkq - 0 8"
ROOK_BISHOP_EACH = "3rk3/pp3ppp/2b5/8/8/2B5/PP3PPP/3R2K1 w - - 0 30"
TWO_ROOKS_VS_ROOK_KNIGHT = "3r2k1/pp3ppp/2n5/8/8/8/PP3PPP/3RR1K1 w - - 0 30"
QUEEN_VS_QUEEN = "3q2k1/pp3ppp/8/8/8/8/PP3PPP/3Q2K1 w - - 0 40"
QUEEN_ROOK_VS_ROOK = "3r2k1/pp3ppp/8/8/8/8/PP3PPP/3QR1K1 w - - 0 30"
NO_QUEENS_MANY_PIECES = "r1b1kb1r/pp3ppp/2n2n2/4p3/4P3/2N2N2/PP3PPP/R1B1KB1R w KQkq - 0 20"


def board(fen: str) -> chess.Board:
    return chess.Board(fen)


def test_non_pawn_material_counts_both_sides() -> None:
    assert non_pawn_material(chess.Board()) == 2 * (9 + 2 * 5 + 2 * 3 + 2 * 3)
    assert non_pawn_material(board(ROOK_BISHOP_EACH)) == 16


@pytest.mark.parametrize(
    "fen",
    [
        ROOK_BISHOP_EACH,  # ферзей нет, фигур 4
        TWO_ROOKS_VS_ROOK_KNIGHT,  # ферзей нет, фигур 4
        QUEEN_VS_QUEEN,  # материал 18 > 13, но ферзи — не эндшпиль
        "8/5pk1/8/8/8/8/5PK1/8 w - - 0 50",  # пешечный
        "6k1/8/8/8/8/8/5PK1/4Q3 w - - 0 50",  # ферзь против короля: 9 ≤ 13
    ],
)
def test_endgame_positions(fen: str) -> None:
    expected = fen != QUEEN_VS_QUEEN
    assert is_endgame(board(fen)) is expected


@pytest.mark.parametrize("fen", [chess.STARTING_FEN, NO_QUEENS_MANY_PIECES, QUEEN_ROOK_VS_ROOK])
def test_not_endgame_positions(fen: str) -> None:
    assert not is_endgame(board(fen))


def test_opening_ends_after_move_12() -> None:
    early = board(MIDDLEGAME_MOVE_15.replace(" 0 15", " 0 12"))

    assert position_phase(early) is Phase.OPENING
    assert position_phase(board(MIDDLEGAME_MOVE_15)) is Phase.MIDDLEGAME


def test_opening_ends_when_queens_are_traded() -> None:
    assert position_phase(board(QUEENS_TRADED_MOVE_8)) is Phase.MIDDLEGAME


def test_opening_ends_when_out_of_book() -> None:
    assert position_phase(chess.Board(), in_book=False) is Phase.MIDDLEGAME


def _positions(sans: str) -> list[chess.Board]:
    b = chess.Board()
    result = [b.copy()]
    for san in sans.split():
        b.push_san(san)
        result.append(b.copy())
    return result


def test_game_phases_respect_book_exit() -> None:
    positions = _positions("e4 e5 Nf3 Nc6 Bb5 a6")

    # Книжные первые 2 полухода: позиции 0..2 — дебют (ход, выводящий из книги, тоже).
    assert game_phases(positions, book_plies=2) == [Phase.OPENING] * 3 + [Phase.MIDDLEGAME] * 4
    assert game_phases(positions) == [Phase.OPENING] * 7


def test_game_phases_never_go_back() -> None:
    # Эндшпиль, затем превращение пешки возвращает материал — фаза остаётся эндшпилем.
    endgame = board("8/P5k1/8/8/8/8/6K1/r7 w - - 0 50")
    promoted = endgame.copy()
    promoted.push_san("a8=Q")

    assert position_phase(promoted) is Phase.MIDDLEGAME
    assert game_phases([chess.Board(), endgame, promoted]) == [
        Phase.OPENING,
        Phase.ENDGAME,
        Phase.ENDGAME,
    ]


def test_game_phases_full_game() -> None:
    sans = (
        "e4 e5 Nf3 d6 d4 Bg4 dxe5 Bxf3 Qxf3 dxe5 Bc4 Nf6 Qb3 Qe7 Nc3 c6 Bg5 b5 Nxb5 cxb5 "
        "Bxb5+ Nbd7 O-O-O Rd8 Rxd7 Rxd7 Rd1 Qe6 Bxd7+ Nxd7 Qb8+ Nxb8 Rd8#"
    )
    phases = game_phases(_positions(sans))

    # Ходы 1–12 обеих сторон (24 полухода) — дебют, дальше миттельшпиль.
    assert phases[:24] == [Phase.OPENING] * 24
    assert set(phases[24:]) == {Phase.MIDDLEGAME}
