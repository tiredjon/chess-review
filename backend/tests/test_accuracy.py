import json
from pathlib import Path
from typing import Any

import chess
import pytest
from chess.engine import Cp, Mate, Score

from app.review.accuracy import (
    aggregate_accuracy,
    move_accuracy,
    volatility_weights,
    volatility_window,
)
from app.review.evaluate import evaluate_game
from app.review.thresholds import INITIAL_CP
from app.review.types import PositionEval

LICHESS_GAMES = json.loads(
    (Path(__file__).parent / "data" / "lichess_accuracy.json").read_text(encoding="utf-8")
)["games"]


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (60.0, 50.0, 64.57982845372067),
        (70.0, 40.0, 25.772047746869696),
        (50.0, 49.0, 96.60397651008962),
        # Огромная потеря упирается в 0 + бонус неопределённости.
        (90.0, 10.0, 1.000170640274321),
    ],
)
def test_move_accuracy_reference_values(before: float, after: float, expected: float) -> None:
    assert move_accuracy(before, after) == pytest.approx(expected, abs=1e-9)


def test_move_accuracy_is_100_when_position_did_not_get_worse() -> None:
    assert move_accuracy(50.0, 50.0) == 100.0
    assert move_accuracy(40.0, 70.0) == 100.0


def test_move_accuracy_never_leaves_0_100() -> None:
    assert move_accuracy(100.0, 0.0) >= 0.0
    # Δ чуть больше нуля: формула + бонус дают > 100, обрезается.
    assert move_accuracy(50.0, 49.99) == 100.0


@pytest.mark.parametrize(
    ("plies", "window"), [(1, 2), (19, 2), (20, 2), (35, 3), (79, 7), (80, 8), (200, 8)]
)
def test_volatility_window_is_plies_over_ten_clamped(plies: int, window: int) -> None:
    assert volatility_window(plies) == window


def test_volatility_weights_one_per_move_and_clamped() -> None:
    flat = [50.0] * 31
    swingy = [50.0, 90.0] * 15 + [50.0]

    assert volatility_weights(flat) == [0.5] * 30
    assert volatility_weights(swingy) == [12.0] * 30
    assert volatility_weights([50.0]) == []


def test_aggregate_accuracy_mixes_weighted_and_harmonic_means() -> None:
    # weighted = (100·1 + 50·3) / 4 = 62.5; harmonic = 2 / (1/100 + 1/50) = 66.67
    assert aggregate_accuracy([(100.0, 1.0), (50.0, 3.0)]) == pytest.approx((62.5 + 200 / 3) / 2)
    assert aggregate_accuracy([]) is None


def test_aggregate_accuracy_survives_zero_accuracy() -> None:
    assert aggregate_accuracy([(0.0, 1.0), (100.0, 1.0)]) == pytest.approx(
        (50.0 + 2 / (1 + 1 / 100)) / 2
    )


def _lichess_white_score(entry: dict[str, Any]) -> Score:
    if "eval" in entry:
        return Cp(entry["eval"])
    return Mate(entry["mate"])


def _lichess_position_evals(game: dict[str, Any]) -> tuple[list[chess.Move], list[PositionEval]]:
    """Оценки Lichess (с точки зрения белых, после каждого хода) → наш формат.

    Стартовая позиция, как в lila, оценивается в +0.15. Если последняя оценка
    отсутствует (партия кончилась матом), Lichess не учитывает последний ход —
    повторяем это, обрезая партию.
    """
    board = chess.Board()
    moves = [board.push_san(san) for san in game["moves"].split()[: len(game["analysis"])]]
    evals = [PositionEval(score=Cp(INITIAL_CP))]
    for ply, entry in enumerate(game["analysis"], start=1):
        white = _lichess_white_score(entry)
        if entry.get("mate") == 0:
            # «Мат 0» у Lichess — мат на доске; его всегда получила сторона на ходу.
            evals.append(PositionEval(score=Mate(0)))
        else:
            evals.append(PositionEval(score=white if ply % 2 == 0 else -white))
    return moves, evals


@pytest.mark.parametrize("game", LICHESS_GAMES, ids=[g["id"] for g in LICHESS_GAMES])
def test_game_accuracy_matches_lichess(game: dict[str, Any]) -> None:
    moves, evals = _lichess_position_evals(game)

    result = evaluate_game(chess.Board(), moves, evals)

    # Решение в SPEC: допуск ±1. Фактически совпадаем с точностью до округления.
    assert result.accuracy[chess.WHITE] == pytest.approx(game["accuracy"]["white"], abs=0.5)
    assert result.accuracy[chess.BLACK] == pytest.approx(game["accuracy"]["black"], abs=0.5)


def test_lichess_fixture_covers_game_endings() -> None:
    statuses = {g["status"] for g in LICHESS_GAMES}
    truncated = [g for g in LICHESS_GAMES if len(g["analysis"]) < len(g["moves"].split())]

    assert {"mate", "resign", "outoftime", "draw", "stalemate"} <= statuses
    assert truncated
    assert {g["winner"] for g in LICHESS_GAMES if g["status"] == "mate"} == {"white", "black"}
