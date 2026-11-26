"""Время на ход по `%clk`: разбор контроля, потраченное время, флаги, ответ API."""

import io

import chess.pgn
import pytest

from app.api.schemas import game_clock_out
from app.review.clock import (
    TimeControl,
    clock_before,
    game_clock,
    move_times,
    parse_time_control,
    time_flags,
)

BLITZ = TimeControl(base_cs=18000, increment_cs=200)

# 3+2: белые тратят 5 с, 1.5 с (+2 добавки), чёрные — 10 с, затем ход без часов.
PGN = """[TimeControl "180+2"]

1. e4 { [%clk 0:02:57] } 1... e5 { [%clk 0:02:52] } 2. Nf3 { [%clk 0:02:57.5] } 2... Nc6 3. Bc4 \
{ [%clk 0:00:10] } *
"""


def _game(text: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(text))
    assert game is not None
    return game


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("180+2", TimeControl(18000, 200)),
        ("600", TimeControl(60000, 0)),
        (" 60+0 ", TimeControl(6000, 0)),
        ("1/86400", None),
        ("-", None),
        ("0+1", None),
        (None, None),
    ],
)
def test_parse_time_control(value: str | None, expected: TimeControl | None) -> None:
    assert parse_time_control(value) == expected


def test_game_clock_from_pgn() -> None:
    clock = game_clock(_game(PGN), "180+2")

    assert clock is not None
    assert clock.clocks == [17700, 17200, 17750, None, 1000]
    # 180 + 2 − 177 = 5 с; 180 + 2 − 172 = 10 с; 177 + 2 − 177.5 = 1.5 с; у 2... Nc6 нет
    # часов; 3. Bc4 считается от 2. Nf3: 177.5 + 2 − 10 = 169.5 с.
    assert clock.spent == [500, 1000, 150, None, 16950]


def test_game_clock_needs_clocks_and_base() -> None:
    assert game_clock(_game(PGN), "1/86400") is None
    assert game_clock(_game('[TimeControl "180"]\n\n1. e4 e5 *\n'), "180") is None


def test_move_times_never_negative() -> None:
    # Часы подкрутили соперники (Lichess «+15 секунд»): остаток вырос больше добавки.
    assert move_times([18000, 17000, 19000], BLITZ) == [200, 1200, 0]


def test_clock_before_and_flags() -> None:
    clocks: list[int | None] = [17700, 17200, 1500, 1700, 1000]
    assert clock_before(clocks, BLITZ, 1) == 18000
    assert clock_before(clocks, BLITZ, 2) == 18000
    assert clock_before(clocks, BLITZ, 5) == 1500

    # Цейтнот — меньше 10 % базы (18 с) перед ходом.
    assert time_flags(1799, 100, BLITZ).trouble
    assert not time_flags(1800, 100, BLITZ).trouble
    # Быстро — не больше 2 % базы (3.6 с), но порог не ниже 1 с.
    assert time_flags(10000, 360, BLITZ).fast
    assert not time_flags(10000, 361, BLITZ).fast
    assert time_flags(1000, 100, TimeControl(3000, 0)).fast
    # Долго — от 10 % базы.
    assert time_flags(10000, 1800, BLITZ).long
    assert not time_flags(10000, 1799, BLITZ).long
    assert not time_flags(None, None, BLITZ).trouble


def test_game_clock_out_summary() -> None:
    clocks: list[int | None] = [17700, 17200, 1500, None, 1400]
    spent = move_times(clocks, BLITZ)
    out = game_clock_out(BLITZ, clocks, spent)

    assert [ply.spent_cs for ply in out.plies] == [500, 1000, 16400, None, 300]
    assert [ply.trouble for ply in out.plies] == [False, False, False, False, True]
    assert out.plies[2].long
    assert out.plies[4].fast
    assert out.white.model_dump() == {
        "moves": 3,
        "avg_spent_cs": 5733,
        "longest_ply": 3,
        "longest_spent_cs": 16400,
        "trouble_moves": 1,
        "first_trouble_ply": 5,
    }
    assert out.black.avg_spent_cs == 1000
    assert out.black.first_trouble_ply is None


def test_game_clock_out_black_first() -> None:
    """Партия из позиции с ходом чёрных: первый полуход — их."""
    out = game_clock_out(BLITZ, [17700, 17000], [500, 1200], white_first=False)

    assert out.black.avg_spent_cs == 500
    assert out.white.avg_spent_cs == 1200
