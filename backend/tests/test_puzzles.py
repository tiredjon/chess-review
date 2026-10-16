"""Пазлы: решение из PV, однозначность, проверка попытки, расписание повторений."""

from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import chess
import pytest
from chess.engine import Cp, Mate

from app.puzzles.solution import (
    AttemptError,
    baseline_material,
    build_puzzle,
    check_attempt,
    cut_solution,
    is_clear_best,
    parse_lines,
)
from app.puzzles.srs import RELEARN_DELAY, schedule
from app.review.types import EngineLine, MoveClass, PositionEval

# Конь даёт шах с вилкой: Nc7+ Kd7 Nxa8 Kc8 — выигрыш ладьи.
FORK = "r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1"
FORK_LINE = ["d5c7", "e8d7", "c7a8", "d7c8"]
# Мат по последней горизонтали: Ra8#; со второй ладьёй — ещё и Rb8#.
BACK_RANK = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"
TWO_MATES = "6k1/5ppp/8/8/8/8/8/RR4K1 w - - 0 1"


def moves(ucis: list[str]) -> list[chess.Move]:
    return [chess.Move.from_uci(uci) for uci in ucis]


def line_json(fen: str, ucis: list[str]) -> list[dict[str, str]]:
    board = chess.Board(fen)
    result = []
    for move in moves(ucis):
        result.append({"uci": move.uci(), "san": board.san(move)})
        board.push(move)
    return result


def engine_line(fen: str, ucis: list[str], cp: int | None = None, mate: int | None = None) -> Any:
    return {"cp": cp, "mate": mate, "pv": line_json(fen, ucis)}


@dataclass
class FakeMove:
    fen_before: str
    uci: str
    best_uci: str | None
    pv: list[Any] | None
    multipv: list[Any] | None = None
    move_class: MoveClass = MoveClass.BLUNDER
    is_miss: bool = False
    motifs: dict[str, Any] | None = None


@dataclass
class FakeAnalyser:
    """Линии по FEN позиции; запоминает, какие позиции спрашивали."""

    lines: dict[str, tuple[EngineLine, ...]]
    calls: list[tuple[str, int, tuple[str, ...]]] = field(default_factory=list)

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        played: Collection[chess.Move] = (),
    ) -> PositionEval:
        self.calls.append((board.fen(), multipv, tuple(m.uci() for m in played)))
        lines = self.lines[board.fen()]
        return PositionEval(score=lines[0].score, lines=lines, depth=depth)


def lines(*items: tuple[list[str], int]) -> tuple[EngineLine, ...]:
    return tuple(EngineLine(score=Cp(cp), pv=tuple(moves(ucis))) for ucis, cp in items)


# --- Решение ---


def test_cut_solution_stops_after_material_is_won() -> None:
    board = chess.Board(FORK)
    solution = cut_solution(board, moves([*FORK_LINE, "a8b6"]), baseline_material(board, None))

    assert solution == moves(["d5c7", "e8d7", "c7a8"])


def test_cut_solution_stops_at_mate() -> None:
    board = chess.Board(BACK_RANK)

    assert cut_solution(board, moves(["a1a8"]), 0) == moves(["a1a8"])


def test_cut_solution_without_gain_is_none() -> None:
    board = chess.Board(FORK)
    # Тихие ходы: материал не меняется.
    line = moves(["e1e2", "e8e7", "e2e3", "e7e6", "e3e2", "e6e7", "e2e1", "e7e8"])

    assert cut_solution(board, line, baseline_material(board, None)) is None


def test_cut_solution_needs_the_reply() -> None:
    board = chess.Board(FORK)

    # Линия оборвалась на ходе игрока без мата — выигрыш не подтверждён ответом.
    assert cut_solution(board, moves(["d5c7"]), baseline_material(board, None)) is None


def test_baseline_counts_material_before_opponents_capture() -> None:
    # Чёрные только что взяли коня: «отыграть» его — не пазл.
    prev = FakeMove("4k3/8/3p4/4N3/8/8/8/4K2R b - - 0 1", "d6e5", None, None)
    board = chess.Board("4k3/8/8/4p3/8/8/8/4K2R w - - 0 2")

    assert baseline_material(board, prev) == 7
    assert baseline_material(board, None) == 4


def test_is_clear_best_compares_first_two_lines() -> None:
    board = chess.Board(FORK)

    assert is_clear_best(board, lines((["d5c7"], 500), (["e1e2"], 0)))
    assert not is_clear_best(board, lines((["d5c7"], 500), (["d5b6"], 420)))
    assert not is_clear_best(board, lines((["d5c7"], 500)))
    # Единственный легальный ход — однозначен и без второй линии.
    assert is_clear_best(chess.Board("k7/8/1Q6/8/8/8/8/7K b - - 0 1"), ())


# --- Пазл из хода ---


def fork_move(**overrides: Any) -> FakeMove:
    values: dict[str, Any] = {
        "fen_before": FORK,
        "uci": "e1e2",
        "best_uci": "d5c7",
        "pv": line_json(FORK, FORK_LINE),
        "multipv": [engine_line(FORK, FORK_LINE, cp=520)],
        "motifs": {"missed": [{"type": "fork"}, {"type": "fork"}, {"type": "hanging_piece"}]},
    }
    return FakeMove(**(values | overrides))


def after(fen: str, ucis: list[str]) -> str:
    board = chess.Board(fen)
    for move in moves(ucis):
        board.push(move)
    return board.fen()


async def test_build_puzzle_from_blunder() -> None:
    analyser = FakeAnalyser(
        {
            FORK: lines((["d5c7"], 520), (["e1e2"], 0)),
            after(FORK, ["d5c7", "e8d7"]): lines((["c7a8"], 520), (["c7e6"], 0)),
        }
    )

    draft = await build_puzzle(fork_move(), None, analyser, depth=10)

    assert draft is not None
    assert draft.fen == FORK
    assert draft.solution == ("d5c7", "e8d7", "c7a8")
    assert draft.themes == ("fork", "hanging_piece")
    # В разборе одна линия — второй вариант добирается движком из обеих позиций игрока.
    assert [(multipv, played) for _, multipv, played in analyser.calls] == [
        (2, ("d5c7",)),
        (2, ("c7a8",)),
    ]


async def test_build_puzzle_uses_stored_multipv() -> None:
    analyser = FakeAnalyser({after(FORK, ["d5c7", "e8d7"]): lines((["c7a8"], 520), (["c7e6"], 0))})
    move = fork_move(
        multipv=[engine_line(FORK, FORK_LINE, cp=520), engine_line(FORK, ["e1e2"], cp=0)]
    )

    assert await build_puzzle(move, None, analyser, depth=10) is not None
    assert [fen for fen, _, _ in analyser.calls] == [after(FORK, ["d5c7", "e8d7"])]


async def test_ambiguous_first_move_is_rejected() -> None:
    analyser = FakeAnalyser({FORK: lines((["d5c7"], 520), (["d5b6"], 450))})

    assert await build_puzzle(fork_move(), None, analyser, depth=10) is None


async def test_ambiguous_later_move_is_rejected() -> None:
    analyser = FakeAnalyser(
        {
            FORK: lines((["d5c7"], 520), (["e1e2"], 0)),
            after(FORK, ["d5c7", "e8d7"]): lines((["c7a8"], 520), (["c7b5"], 480)),
        }
    )

    assert await build_puzzle(fork_move(), None, analyser, depth=10) is None


async def test_engine_disagreeing_with_pv_is_rejected() -> None:
    analyser = FakeAnalyser(
        {
            FORK: lines((["d5c7"], 520), (["e1e2"], 0)),
            after(FORK, ["d5c7", "e8d7"]): lines((["c7e6"], 520), (["c7a8"], 0)),
        }
    )

    assert await build_puzzle(fork_move(), None, analyser, depth=10) is None


async def test_final_mate_needs_no_uniqueness_check() -> None:
    move = FakeMove(
        TWO_MATES, "g1f1", "a1a8", line_json(TWO_MATES, ["a1a8"]), move_class=MoveClass.MISTAKE
    )
    analyser = FakeAnalyser({})

    draft = await build_puzzle(move, None, analyser, depth=10)

    assert draft is not None
    assert draft.solution == ("a1a8",)
    assert draft.themes == ("mate_in_n",)
    assert analyser.calls == []


async def test_only_move_puzzle_without_material_gain() -> None:
    # Тихая лучшая линия: материал не выигрывается — пазл из одного единственного хода.
    quiet = ["e1e2", "e8e7", "e2e3", "e7e6"]
    move = fork_move(
        uci="d5c7",
        best_uci="e1e2",
        pv=line_json(FORK, quiet),
        multipv=[engine_line(FORK, quiet, cp=100), engine_line(FORK, ["e1d2"], cp=-200)],
        motifs={"missed": [{"type": "pin"}]},
    )

    draft = await build_puzzle(move, None, FakeAnalyser({}), depth=10)

    assert draft is not None
    assert draft.solution == ("e1e2",)
    assert draft.themes == ("only_move", "pin")


async def test_only_move_puzzle_needs_clear_best() -> None:
    quiet = ["e1e2", "e8e7"]
    move = fork_move(
        uci="d5c7",
        best_uci="e1e2",
        pv=line_json(FORK, quiet),
        multipv=[engine_line(FORK, quiet, cp=100), engine_line(FORK, ["e1d2"], cp=60)],
    )

    assert await build_puzzle(move, None, FakeAnalyser({}), depth=10) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"move_class": MoveClass.INACCURACY},
        {"best_uci": "e1e2"},
        {"pv": None},
        {"pv": [{"uci": "0000", "san": "--"}]},
    ],
)
async def test_not_a_puzzle_source(overrides: dict[str, Any]) -> None:
    assert await build_puzzle(fork_move(**overrides), None, FakeAnalyser({}), depth=10) is None


async def test_miss_of_any_class_is_a_source() -> None:
    analyser = FakeAnalyser(
        {
            FORK: lines((["d5c7"], 520), (["e1e2"], 0)),
            after(FORK, ["d5c7", "e8d7"]): lines((["c7a8"], 520), (["c7e6"], 0)),
        }
    )
    move = fork_move(move_class=MoveClass.INACCURACY, is_miss=True)

    assert await build_puzzle(move, None, analyser, depth=10) is not None


# --- Попытка ---

SOLUTION = ["d5c7", "e8d7", "c7a8"]


def test_attempt_continues_with_reply() -> None:
    check = check_attempt(FORK, SOLUTION, ["d5c7"])

    assert (check.result, check.reply) == ("continue", "e8d7")


def test_attempt_solved() -> None:
    assert check_attempt(FORK, SOLUTION, SOLUTION).result == "solved"


def test_attempt_wrong_move_fails_with_expected() -> None:
    check = check_attempt(FORK, SOLUTION, ["d5c7", "e8d7", "c7e6"])

    assert (check.result, check.expected) == ("failed", "c7a8")


def test_any_mate_counts_on_last_move() -> None:
    assert check_attempt(TWO_MATES, ["a1a8"], ["b1b8"]).result == "solved"


def test_promotion_matches_by_squares() -> None:
    fen = "8/1P5k/8/8/8/8/8/K7 w - - 0 1"

    assert check_attempt(fen, ["b7b8n"], ["b7b8q"]).result == "solved"


def test_give_up_returns_next_player_move() -> None:
    assert check_attempt(FORK, SOLUTION, [], gave_up=True).expected == "d5c7"
    assert check_attempt(FORK, SOLUTION, ["d5c7"], gave_up=True).expected == "c7a8"
    assert check_attempt(FORK, SOLUTION, ["d5c7", "e8d7"], gave_up=True).expected == "c7a8"


@pytest.mark.parametrize(
    ("attempt", "message"),
    [
        (["d5c7", "e8f8"], "Ответ соперника"),
        (["d5d4"], "Нелегальный"),
        (["d5c7", "e8d7"], "ходом игрока"),
        ([], "ходом игрока"),
        ([*SOLUTION, "d7c8"], "больше"),
    ],
)
def test_invalid_attempts(attempt: list[str], message: str) -> None:
    with pytest.raises(AttemptError, match=message):
        check_attempt(FORK, SOLUTION, attempt)


# --- Расписание ---

NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)


def test_leitner_promotes_on_clean_solve() -> None:
    first = schedule(0, solved=True, hint_used=False, now=NOW)
    assert (first.box, first.next_review_at) == (1, NOW + timedelta(days=1))
    assert schedule(1, solved=True, hint_used=False, now=NOW).next_review_at == NOW + timedelta(
        days=3
    )
    top = schedule(5, solved=True, hint_used=False, now=NOW)
    assert (top.box, top.next_review_at) == (5, NOW + timedelta(days=35))


def test_leitner_hint_keeps_box() -> None:
    assert schedule(3, solved=True, hint_used=True, now=NOW).box == 3
    assert schedule(0, solved=True, hint_used=True, now=NOW).box == 1


def test_leitner_failure_resets_and_repeats_soon() -> None:
    review = schedule(4, solved=False, hint_used=False, now=NOW)

    assert (review.box, review.next_review_at) == (0, NOW + RELEARN_DELAY)


def test_mate_score_lines_parse() -> None:
    parsed = parse_lines([engine_line(BACK_RANK, ["a1a8"], mate=1)])

    assert parsed[0].score == Mate(1)
    assert parsed[0].pv == (chess.Move.from_uci("a1a8"),)
