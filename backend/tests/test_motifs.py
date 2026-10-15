"""Детекторы мотивов (SPEC §5): ≥ 3 положительных и ≥ 2 отрицательных позиции на каждый.

Ожидание — список (тип, поля) — `squares` мотива в порядке, описанном в детекторе.
Часть позиций проверяется и в зеркальном виде (те же мотивы за другой цвет).
"""

from dataclasses import dataclass, field

import chess
import pytest

from app.review.motifs import DETECTORS, detect_all
from app.review.motifs.base import Motif, MotifType, realized_gain

T = MotifType

OPERA_16 = "4kb1r/p2n1ppp/4q3/4p1B1/4P3/1Q6/PPP2PPP/2KR4 w k - 0 16"
RETI_10 = "rnbk1b1r/pp3ppp/2p5/4q3/4n3/8/PPPB1PPP/2KR1BNR w - - 0 10"
SCHOLAR = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


@dataclass(frozen=True)
class Case:
    detector: str
    fen: str
    san: str
    pv: str = ""
    expected: list[tuple[MotifType, str]] = field(default_factory=list)
    # Ходы, сыгранные до позиции `fen` (история нужна для взятий в ответ).
    history: str = ""
    mirror: bool = False

    @property
    def id(self) -> str:
        sign = "+" if self.expected else "-"
        return f"{self.detector}{sign}{'~' if self.mirror else ''}:{self.san}"


def pos(
    detector: str,
    fen: str,
    san: str,
    pv: str = "",
    *expected: tuple[MotifType, str],
    history: str = "",
    mirror: bool = False,
) -> Case:
    return Case(detector, fen, san, pv, list(expected), history, mirror)


CASES = [
    # --- hanging_piece: (бьющая, взятая) ---
    pos(
        "hanging_piece", "4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1", "Rxd5", "", (T.HANGING_PIECE, "d5 d5")
    ),
    pos(
        "hanging_piece", "2q1k3/8/8/8/2B5/8/8/4K3 b - - 0 1", "Qxc4", "", (T.HANGING_PIECE, "c4 c4")
    ),
    pos(
        "hanging_piece", "4k3/8/8/8/8/2r5/8/1N2K3 w - - 0 1", "Nxc3", "", (T.HANGING_PIECE, "c3 c3")
    ),
    # Ферзь взял защищённого коня — отбиваем ферзя: это зевок, а не размен.
    pos(
        "hanging_piece",
        "3qk3/8/8/8/3N4/4P3/8/4K3 b - - 0 1",
        "exd4",
        "",
        (T.HANGING_PIECE, "d4 d4"),
        history="Qxd4",
    ),
    pos("hanging_piece", "4k3/8/4p3/3n4/8/8/8/3RK3 w - - 0 1", "Rxd5"),  # защищён
    pos("hanging_piece", "4k3/8/8/3p4/8/8/8/3RK3 w - - 0 1", "Rxd5"),  # пешка
    pos("hanging_piece", "4k3/1p6/2n5/1B6/8/8/8/4K3 w - - 0 1", "bxc6", history="Bxc6"),  # размен
    # --- fork: (вилочная фигура, цели…) ---
    pos("fork", "r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "Nc7+", "Ke7 Nxa8", (T.FORK, "c7 a8 e8")),
    pos("fork", "4k3/8/8/2n1b3/8/2PP4/8/4K3 w - - 0 1", "d4", "", (T.FORK, "d4 c5 e5")),
    pos("fork", "4k3/1r6/8/8/8/8/8/4K2Q w - - 0 1", "Qe4+", "Kf7 Qxb7+", (T.FORK, "e4 b7 e8")),
    pos("fork", "r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "Nc7+", "", (T.FORK, "c7 a8 e8"), mirror=True),
    pos("fork", "r2bk3/8/8/1N6/8/8/8/4K3 w - - 0 1", "Nc7+"),  # конь под боем слона
    pos("fork", "4k3/8/8/1N6/8/8/8/4K3 w - - 0 1", "Nc7+"),  # одна цель
    pos("fork", "4k3/1p3p2/2n1n3/8/8/8/6B1/4K3 w - - 0 1", "Bd5"),  # кони защищены
    # --- pin: (связывающая, связанная, за ней) ---
    pos("pin", "4k3/3n4/8/8/8/8/8/4KB2 w - - 0 1", "Bb5", "", (T.PIN, "b5 d7 e8")),
    pos("pin", "3q2k1/8/8/3n4/8/8/8/R3K3 w - - 0 1", "Rd1", "", (T.PIN, "d1 d5 d8")),
    pos("pin", "6k1/5r2/8/8/8/8/8/Q3K3 w - - 0 1", "Qa2", "", (T.PIN, "a2 f7 g8")),
    pos("pin", "4k3/3n4/8/8/8/8/8/4KB2 w - - 0 1", "Bb5", "", (T.PIN, "b5 d7 e8"), mirror=True),
    pos("pin", "4k3/3n4/8/1B6/8/8/8/4K3 w - - 0 1", "Ba4"),  # связка уже была
    pos("pin", "r3k3/1q6/8/8/8/8/8/5B1K w - - 0 1", "Bg2"),  # спереди дороже — это не связка
    pos("pin", "4k3/3n4/p7/8/8/8/8/4KB2 w - - 0 1", "Bb5"),  # слон под боем пешки
    # --- skewer: (атакующая, передняя, задняя) ---
    pos("skewer", "8/8/6r1/8/B3k3/8/8/4K3 w - - 0 1", "Bc2+", "Kd4 Bxg6", (T.SKEWER, "c2 e4 g6")),
    pos("skewer", "r3k3/1q6/8/8/8/8/8/5B1K w - - 0 1", "Bg2", "", (T.SKEWER, "g2 b7 a8")),
    pos("skewer", "7k/8/8/3q3b/1P6/8/8/R3K3 w - - 0 1", "Ra5", "", (T.SKEWER, "a5 d5 h5")),
    pos("skewer", "8/8/6p1/8/B3k3/8/8/4K3 w - - 0 1", "Bc2+"),  # сзади пешка
    pos("skewer", "8/7p/6n1/8/Q3k3/8/8/4K3 w - - 0 1", "Qc2+"),  # сзади защищённый конь
    # --- discovered: (открытая дальнобойная, цель, сходившая) ---
    pos(
        "discovered",
        "4k3/8/8/8/4N3/8/8/4R1K1 w - - 0 1",
        "Nc5+",
        "",
        (T.DISCOVERED_CHECK, "e1 e8 c5"),
    ),
    pos(
        "discovered",
        "3qk3/8/8/8/3B4/8/8/3RK3 w - - 0 1",
        "Bc3",
        "",
        (T.DISCOVERED_ATTACK, "d1 d8 c3"),
    ),
    pos(
        "discovered",
        "6k1/6r1/8/8/3N4/8/1B6/4K3 w - - 0 1",
        "Nb5",
        "",
        (T.DISCOVERED_ATTACK, "b2 g7 b5"),
    ),
    pos("discovered", "3qk3/8/8/8/3B4/8/8/3RK3 w - - 0 1", "Ke2"),  # линия не открылась
    pos("discovered", "3nk3/8/8/8/3B4/8/8/3RK3 w - - 0 1", "Bc3"),  # цель дешевле и защищена
    # --- double_check: (шахующие…, король) ---
    pos(
        "double_check",
        "4k3/8/8/8/4N3/8/8/4R1K1 w - - 0 1",
        "Nf6+",
        "",
        (T.DOUBLE_CHECK, "e1 f6 e8"),
    ),
    pos("double_check", RETI_10, "Bg5+", "Kc7 Bd8#", (T.DOUBLE_CHECK, "d1 g5 d8")),
    pos(
        "double_check",
        "4k3/8/8/8/8/8/4B3/K3R3 w - - 0 1",
        "Bb5+",
        "",
        (T.DOUBLE_CHECK, "e1 b5 e8"),
    ),
    pos("double_check", "4k3/8/8/8/4N3/8/8/4R1K1 w - - 0 1", "Nc5+"),  # шах один
    pos("double_check", "4k3/8/8/8/8/8/4B3/K7 w - - 0 1", "Bb5+"),
    # --- mate: мат в линии (матующая, король) и угроза мата ---
    pos("mate", "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "Ra8#", "", (T.MATE_IN_N, "a8 g8")),
    pos("mate", OPERA_16, "Qb8+", "Nxb8 Rd8#", (T.MATE_IN_N, "d8 e8")),
    pos("mate", SCHOLAR, "Qxf7#", "", (T.MATE_IN_N, "f7 e8")),
    pos("mate", "6k1/5ppp/8/8/8/8/1P6/1R4K1 w - - 0 1", "Ra1", "", (T.MATE_THREAT, "a8 g8")),
    pos("mate", "5rk1/5ppp/8/8/8/3B4/8/3Q2K1 w - - 0 1", "Qh5", "", (T.MATE_THREAT, "h7 g8")),
    pos("mate", chess.STARTING_FEN, "e4", "e5 Nf3"),
    pos("mate", "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "Kf2"),  # мат в 1 был и до хода
    pos(
        "mate", "rnbqkbnr/pppp1ppp/8/4p3/8/5P2/PPPPP1PP/RNBQKBNR w KQkq - 0 2", "g4", "Qh4#"
    ),  # мат ставят нам
    # --- back_rank ---
    pos("back_rank", "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", "Ra8#", "", (T.BACK_RANK, "a8 g8")),
    pos("back_rank", OPERA_16, "Qb8+", "Nxb8 Rd8#", (T.BACK_RANK, "d8 e8")),
    pos("back_rank", "6k1/5ppp/8/8/8/8/1P6/1R4K1 w - - 0 1", "Ra1", "", (T.BACK_RANK, "a8 g8")),
    pos(
        "back_rank",
        "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
        "Ra8#",
        "",
        (T.BACK_RANK, "a8 g8"),
        mirror=True,
    ),
    pos("back_rank", SCHOLAR, "Qxf7#"),
    pos("back_rank", "6k1/5pp1/7p/8/8/8/8/R5K1 w - - 0 1", "Ra8+"),  # есть форточка
    # --- trapped_piece: (сходившая, пойманная) ---
    pos(
        "trapped_piece",
        "4k3/8/8/8/8/8/P7/n3K2R w K - 0 1",
        "Kd2",
        "",
        (T.TRAPPED_PIECE, "d2 a1"),
    ),
    pos(
        "trapped_piece",
        "r3k3/Bpp5/8/8/8/8/8/4K3 b - - 0 1",
        "b6",
        "",
        (T.TRAPPED_PIECE, "b6 a7"),
    ),
    pos(
        "trapped_piece",
        "N2k4/p7/8/8/8/8/7K/1r6 b - - 0 1",
        "Rb8",
        "",
        (T.TRAPPED_PIECE, "b8 a8"),
    ),
    pos("trapped_piece", "r3k3/Bp6/8/8/8/8/8/4K3 b - - 0 1", "b6"),  # Bxb6 спасает
    pos("trapped_piece", "r3k3/B1p5/1p6/8/8/8/8/4K3 b - - 0 1", "Ke7"),  # пойман и до хода
    pos("trapped_piece", "r3k3/Bpp5/8/8/8/8/8/4K2R w K - 0 1", "Rh8+"),  # шах
    # --- defender: removing_defender / overload (бьющая, защитник, выигранная) ---
    pos(
        "defender",
        "6k1/6pp/5n2/3b2B1/8/8/8/3R2K1 w - - 0 1",
        "Bxf6",
        "gxf6 Rxd5",
        (T.REMOVING_DEFENDER, "d1 f6 d5"),
    ),
    pos(
        "defender",
        "6k1/6pp/5n2/3b2B1/8/8/8/3R2K1 w - - 0 1",
        "Bxf6",
        "gxf6 Rxd5",
        (T.REMOVING_DEFENDER, "d1 f6 d5"),
        mirror=True,
    ),
    pos(
        "defender",
        "6k1/3q4/2npb3/1B6/8/8/8/4R1K1 w - - 0 1",
        "Bxc6",
        "Qxc6 Rxe6",
        (T.OVERLOAD, "e1 c6 e6"),
    ),
    pos(
        "defender",
        "1n2r2k/8/4b3/8/2B5/8/8/1R4K1 w - - 0 1",
        "Rxb8",
        "Rxb8 Bxe6",
        (T.OVERLOAD, "c4 b8 e6"),
    ),
    pos(
        "defender", "6k1/6pp/4pn2/3b2B1/8/8/8/3R2K1 w - - 0 1", "Bxf6", "gxf6 Rxd5 exd5"
    ),  # e6 защищает
    pos("defender", "6k1/6pp/5n2/1b4B1/8/8/8/1R4K1 w - - 0 1", "Bxf6", "gxf6 Rxb5"),  # и так висел
    pos("defender", "6k1/6pp/5n2/3b2B1/8/8/8/3R2K1 w - - 0 1", "Bxf6", "gxf6"),  # линия коротка
    # --- promotion ---
    pos("promotion", "8/4P3/8/8/8/8/k7/4K3 w - - 0 1", "e8=Q", "", (T.PROMOTION, "e8")),
    pos("promotion", "3r4/4P3/8/8/8/8/k7/4K3 w - - 0 1", "exd8=Q", "", (T.PROMOTION, "d8")),
    pos("promotion", "4K3/8/8/8/8/8/3p4/k7 b - - 0 1", "d1=Q", "", (T.PROMOTION, "d1")),
    pos("promotion", "8/8/4P3/8/8/8/k7/4K3 w - - 0 1", "e7", "", (T.PROMOTION_THREAT, "e7")),
    pos("promotion", "8/k7/8/8/8/3p4/8/6K1 b - - 0 1", "d2", "", (T.PROMOTION_THREAT, "d2")),
    pos("promotion", "k2rr3/8/4P3/8/8/8/8/K7 w - - 0 1", "e7", "", (T.PROMOTION_THREAT, "e7")),
    pos("promotion", "8/8/8/4P3/8/8/k7/4K3 w - - 0 1", "e6"),
    pos("promotion", "4r3/8/4P3/8/8/8/k7/4K3 w - - 0 1", "e7"),  # не пройти и не взять
]


def setup(item: Case) -> tuple[chess.Board, chess.Move, list[chess.Move]]:
    """Позиция, ход и продолжение; для `mirror` — зеркальная позиция и ходы."""
    board = chess.Board(item.fen)
    for san in item.history.split():
        board.push_san(san)
    work = board.copy()
    line = [work.push_san(san) for san in f"{item.san} {item.pv}".split()]
    if item.mirror:
        board = board.mirror()
        line = [
            chess.Move(
                chess.square_mirror(m.from_square), chess.square_mirror(m.to_square), m.promotion
            )
            for m in line
        ]
    return board, line[0], line[1:]


def summary(motifs: list[Motif], item: Case) -> list[tuple[MotifType, str]]:
    def name(square: chess.Square) -> str:
        return chess.square_name(chess.square_mirror(square) if item.mirror else square)

    return [(m.type, " ".join(name(s) for s in m.squares)) for m in motifs]


@pytest.mark.parametrize("item", CASES, ids=lambda item: item.id)
def test_detector(item: Case) -> None:
    board, move, pv = setup(item)
    motifs = DETECTORS[item.detector](board, move, pv)
    assert summary(motifs, item) == item.expected
    for motif in motifs:
        assert len(motif.squares) == len(motif.pieces)
        assert motif.line[0] == move


def test_every_detector_has_enough_cases() -> None:
    for name in DETECTORS:
        cases = [c for c in CASES if c.detector == name]
        assert sum(1 for c in cases if c.expected) >= 3, name
        assert sum(1 for c in cases if not c.expected) >= 2, name


def test_fork_gain_and_line() -> None:
    board = chess.Board("r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1")
    line = [chess.Move.from_uci(u) for u in ("b5c7", "e8e7", "c7a8")]
    (fork,) = DETECTORS["fork"](board, line[0], line[1:])
    assert fork.gain_cp == 500
    assert board.variation_san(fork.line) == "1. Nc7+ Ke7 2. Nxa8"
    assert [p.symbol() for p in fork.pieces] == ["N", "r", "k"]


def test_mate_lines() -> None:
    board = chess.Board(OPERA_16)
    pv = [chess.Move.from_uci(u) for u in ("d7b8", "d1d8")]
    (mate,) = DETECTORS["mate"](board, board.parse_san("Qb8+"), pv)
    assert mate.gain_cp is None
    assert len(mate.line) == 3  # мат в 2

    threat_board = chess.Board("5rk1/5ppp/8/8/8/3B4/8/3Q2K1 w - - 0 1")
    (threat,) = DETECTORS["mate"](threat_board, threat_board.parse_san("Qh5"), [])
    assert threat.line[1] == chess.Move.null()
    assert threat.line[2] == chess.Move.from_uci("h5h7")


def test_realized_gain_finishes_exchange() -> None:
    # Rxd5 exd5: ладья за коня — минус 2, хотя после первого хода +3.
    board = chess.Board("4k3/8/4p3/3n4/8/8/8/3RK3 w - - 0 1")
    line = [chess.Move.from_uci(u) for u in ("d1d5", "e6d5")]
    assert realized_gain(board, line, plies=1) == -200
    assert realized_gain(board, [], plies=3) == 0


def test_detect_all() -> None:
    board = chess.Board("4k3/8/8/8/4N3/8/8/4R1K1 w - - 0 1")
    types = {m.type for m in detect_all(board, board.parse_san("Nf6+"), [])}
    assert {T.DOUBLE_CHECK, T.DISCOVERED_CHECK} <= types
    assert detect_all(board, chess.Move.from_uci("a1a2"), []) == ()
