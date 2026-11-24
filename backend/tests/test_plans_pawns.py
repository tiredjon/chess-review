"""Признаки пешечной структуры (`app/plans/pawns.py`) на точечных позициях.

Часть позиций проверяется зеркально (`board.mirror()`): тот же признак за другой цвет
на отражённых полях.
"""

import chess
import pytest

from app.plans.pawns import (
    PawnView,
    ahead,
    backward,
    blocked_center,
    chains,
    doubled,
    half_open,
    hanging,
    holes,
    is_fixed,
    islands,
    isolated,
    majorities,
    open_files,
    outposts,
    passed,
    pawn_can_attack,
    pawn_facts,
    rel_rank,
    square_at,
)
from tests.plans_lines import board_of


def names(squares: object) -> list[str]:
    assert isinstance(squares, list | tuple)
    return sorted(chess.square_name(s) for s in squares)


def mirrored(squares: list[str]) -> list[str]:
    return sorted(chess.square_name(chess.square_mirror(chess.parse_square(s))) for s in squares)


def test_relative_ranks() -> None:
    assert rel_rank(chess.WHITE, chess.E2) == 2
    assert rel_rank(chess.BLACK, chess.E7) == 2
    assert square_at(chess.BLACK, 3, 4) == chess.D5
    assert ahead(chess.WHITE, chess.E4) == chess.E5
    assert ahead(chess.BLACK, chess.E5, 2) == chess.E3
    assert ahead(chess.WHITE, chess.E8) is None
    view = PawnView(chess.Board(), chess.BLACK)
    assert view.ranks("e") == [2]
    assert view.has("e", 2)
    assert not view.has("e", 3)
    assert view.square("c", 3) == chess.C6
    assert view.count((0, 1, 2)) == 3


@pytest.mark.parametrize(
    ("line", "color", "expected"),
    [
        ("panov", chess.WHITE, ["d4"]),
        ("qga_iqp", chess.WHITE, ["d4"]),
        ("tarrasch_iqp", chess.BLACK, ["d5"]),
        ("tartakower_hanging", chess.BLACK, ["a6"]),
        ("najdorf_be2_e5", chess.BLACK, []),
        ("start", chess.WHITE, []),
    ],
)
def test_isolated(line: str, color: chess.Color, expected: list[str]) -> None:
    board = board_of(line)
    assert names(isolated(board, color)) == expected
    assert names(isolated(board.mirror(), not color)) == mirrored(expected)


@pytest.mark.parametrize(
    ("line", "color", "expected"),
    [
        ("rossolimo_dxc6", chess.BLACK, ["c5", "c6"]),
        ("rossolimo_bxc6", chess.BLACK, ["c5", "c6"]),
        ("nimzo_saemisch", chess.WHITE, ["c3", "c4"]),
        ("caro_bronstein", chess.BLACK, ["f6", "f7"]),
        ("rossolimo_g6", chess.BLACK, []),
    ],
)
def test_doubled(line: str, color: chess.Color, expected: list[str]) -> None:
    board = board_of(line)
    assert names(doubled(board, color)) == expected
    assert names(doubled(board.mirror(), not color)) == mirrored(expected)


@pytest.mark.parametrize(
    ("line", "color", "expected"),
    [
        # d6 после …e5: соседей сзади нет, d5 бьёт пешка e4, линия d полуоткрыта.
        ("najdorf_be2_e5", chess.BLACK, ["d6"]),
        ("sveshnikov", chess.BLACK, ["d6"]),
        ("kalashnikov", chess.BLACK, ["d6"]),
        # Шевенинген: e6 рядом на той же горизонтали — d6 не отстала.
        ("scheveningen", chess.BLACK, []),
        # Староиндийская: d6 заблокирована d5, линия не полуоткрыта.
        ("kid_mar_del_plata", chess.BLACK, []),
        # Тайманов: d7 ещё не отстала — поле d6 пешка белых не бьёт.
        ("taimanov_be2", chess.BLACK, []),
    ],
)
def test_backward(line: str, color: chess.Color, expected: list[str]) -> None:
    board = board_of(line)
    assert names(backward(board, color)) == expected
    assert names(backward(board.mirror(), not color)) == mirrored(expected)


@pytest.mark.parametrize(
    ("fen", "color", "expected"),
    [
        ("8/5k2/8/3P4/8/8/5K2/8 w - - 0 1", chess.WHITE, ["d5"]),
        # Пешка e6 на соседней линии впереди — не проходная.
        ("8/5k2/4p3/3P4/8/8/5K2/8 w - - 0 1", chess.WHITE, []),
        # Пешка e6 позади соседней линии — d5 уже прошла её.
        ("8/5k2/8/3P4/4p3/8/5K2/8 w - - 0 1", chess.WHITE, ["d5"]),
        ("8/5k2/8/8/2p5/8/5K2/8 b - - 0 1", chess.BLACK, ["c4"]),
    ],
)
def test_passed(fen: str, color: chess.Color, expected: list[str]) -> None:
    board = chess.Board(fen)
    assert names(passed(board, color)) == expected
    assert names(passed(board.mirror(), not color)) == mirrored(expected)


def test_danish_passed_c_pawn() -> None:
    assert names(passed(board_of("danish"), chess.BLACK)) == ["c7"]
    assert names(passed(board_of("start"), chess.WHITE)) == []


@pytest.mark.parametrize(
    ("line", "color", "expected"),
    [
        ("tartakower_hanging", chess.BLACK, ["c5", "d5"]),
        ("semi_tarrasch_hanging", chess.WHITE, ["c4", "d4"]),
        ("panov_hanging", chess.WHITE, ["c4", "d4"]),
        # Изолятор — не висячие; c3 + d4 — не на одной горизонтали.
        ("panov", chess.WHITE, []),
        ("qgd_orthodox", chess.WHITE, []),
    ],
)
def test_hanging(line: str, color: chess.Color, expected: list[str]) -> None:
    board = board_of(line)
    assert names(hanging(board, color)) == expected
    assert names(hanging(board.mirror(), not color)) == mirrored(expected)


def test_islands_and_files() -> None:
    start = chess.Board()
    assert islands(start, chess.WHITE) == [tuple(range(8))]
    assert open_files(start) == []
    rossolimo = board_of("rossolimo_dxc6")
    assert islands(rossolimo, chess.BLACK) == [(0, 1, 2), (4, 5, 6, 7)]
    assert half_open(rossolimo, chess.BLACK) == [3]
    french = board_of("french_exchange")
    assert open_files(french) == [4]
    najdorf = board_of("najdorf_be2_e5")
    assert half_open(najdorf, chess.WHITE) == [3]
    assert half_open(najdorf, chess.BLACK) == [2]
    assert half_open(najdorf.mirror(), chess.WHITE) == [2]


@pytest.mark.parametrize(
    ("line", "color", "expected"),
    [
        ("najdorf_be2_e5", chess.BLACK, ["d5"]),
        ("stonewall_attack", chess.WHITE, ["d3", "e4"]),
        ("dutch_stonewall", chess.BLACK, ["d6", "e5"]),
        ("taimanov_be2", chess.BLACK, ["d6"]),
        ("start", chess.WHITE, []),
        ("scheveningen", chess.BLACK, []),
    ],
)
def test_holes(line: str, color: chess.Color, expected: list[str]) -> None:
    board = board_of(line)
    assert names(holes(board, color)) == expected
    assert names(holes(board.mirror(), not color)) == mirrored(expected)


@pytest.mark.parametrize(
    ("line", "color", "expected"),
    [
        ("najdorf_be2_e5", chess.WHITE, ["d5"]),
        ("dutch_stonewall", chess.WHITE, ["e5"]),
        ("stonewall_attack", chess.BLACK, ["e4"]),
        ("french_advance", chess.WHITE, ["d6"]),
        ("maroczy_nd4", chess.BLACK, ["d4"]),
        # Пешка соперника может прогнать: e6 / c6 ещё бьют d5.
        ("scheveningen", chess.WHITE, []),
        ("start", chess.BLACK, []),
    ],
)
def test_outposts(line: str, color: chess.Color, expected: list[str]) -> None:
    board = board_of(line)
    assert names(outposts(board, color)) == expected
    assert names(outposts(board.mirror(), not color)) == mirrored(expected)


def test_pawn_can_attack_blocked_path() -> None:
    # Пешка c2 дойдёт до c4 и ударит по d5 — если путь не перекрыт пешкой.
    free = chess.Board("4k3/8/8/8/8/8/2P5/4K3 w - - 0 1")
    blocked = chess.Board("4k3/8/8/8/8/2p5/2P5/4K3 w - - 0 1")
    assert pawn_can_attack(free, chess.WHITE, chess.D5)
    assert not pawn_can_attack(blocked, chess.WHITE, chess.D5)
    # Поле позади пешки она уже не атакует.
    assert not pawn_can_attack(free, chess.WHITE, chess.D2)


def test_majorities() -> None:
    open_sicilian = {
        (m.color, m.wing, m.own, m.other) for m in majorities(board_of("najdorf_be2_e5"))
    }
    assert open_sicilian == {(chess.WHITE, "queenside", 3, 2), (chess.BLACK, "center", 2, 1)}
    carlsbad = {(m.color, m.wing) for m in majorities(board_of("qgd_exchange"))}
    assert carlsbad == {(chess.BLACK, "queenside"), (chess.WHITE, "center")}
    assert majorities(chess.Board()) == []


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("french_advance", True),
        ("kid_mar_del_plata", True),
        ("caro_advance", True),
        ("benoni_classical", False),
        ("french_exchange", False),
        ("start", False),
    ],
)
def test_blocked_center(line: str, expected: bool) -> None:
    board = board_of(line)
    assert blocked_center(board) is expected
    assert blocked_center(board.mirror()) is expected


def test_locked_chains() -> None:
    french = board_of("french_advance")
    (white,) = chains(french, chess.WHITE)
    (black,) = chains(french, chess.BLACK)
    assert names(white.squares) == ["d4", "e5"]
    assert (chess.square_name(white.base), white.wing) == ("d4", "kingside")
    assert (chess.square_name(black.base), black.wing) == ("e6", "queenside")
    kid = board_of("kid_mar_del_plata")
    (white,) = chains(kid, chess.WHITE)
    (black,) = chains(kid, chess.BLACK)
    assert (chess.square_name(white.head), white.wing) == ("d5", "queenside")
    assert (chess.square_name(black.base), black.wing) == ("d6", "kingside")
    # Зеркально: цепь белых становится цепью чёрных.
    (mirror,) = chains(french.mirror(), chess.BLACK)
    assert chess.square_name(mirror.base) == "d5"
    assert chains(chess.Board(), chess.WHITE) == []


def test_is_fixed() -> None:
    french = board_of("french_advance")
    assert is_fixed(french, chess.E5)
    assert not is_fixed(french, chess.C3)
    assert not is_fixed(french, chess.E1)  # не пешка
    assert not is_fixed(chess.Board("4k3/4P3/8/8/8/8/8/4K3 w - - 0 1"), chess.E7)


def test_pawn_facts_by_side() -> None:
    facts = pawn_facts(board_of("panov"))
    assert facts.side(chess.WHITE).isolated == (chess.D4,)
    assert facts.side(chess.BLACK).half_open == (3,)
    assert facts.open_files == (2,)
    assert not facts.blocked_center
