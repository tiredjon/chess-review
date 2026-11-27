"""Метрики тренера (`app/coach/metrics.py`): чистые формулы по агрегатам партий."""

import math
import uuid

import pytest

from app.coach.lessons import METRIC_LESSONS
from app.coach.metrics import (
    METRIC_KEYS,
    GameAgg,
    PhaseAgg,
    compute_metrics,
    metric_value,
    motif_spec,
    ratio,
    spec_for,
)


def _game(**kwargs: object) -> GameAgg:
    base: dict[str, object] = {"game_id": uuid.uuid4(), "moves": 40}
    base.update(kwargs)
    return GameAgg(**base)  # type: ignore[arg-type]


def test_metric_keys_match_contract_and_lessons() -> None:
    assert set(METRIC_KEYS) == set(METRIC_LESSONS)
    assert spec_for("accuracy") is not None
    assert spec_for("motif:fork") is not None
    assert spec_for("unknown") is None


def test_ratio_is_pooled_and_se_by_clusters() -> None:
    value, se = ratio([(2, 40), (0, 40), (4, 40)], 100.0)
    assert value == pytest.approx(5.0)
    # r = 0.05; остатки: 0, −2, 2 → Σ = 8; k/(k−1) = 1.5; √12 / 120 · 100
    assert se == pytest.approx(100 * math.sqrt(1.5 * 8) / 120)
    assert ratio([(1, 10)])[1] is None


def test_per_100_metrics_weight_moves_not_games() -> None:
    games = [_game(moves=10, blunders=1), _game(moves=90, blunders=1)]
    m = compute_metrics(games)
    assert m["blunders_per_100"].value == pytest.approx(2.0)
    assert m["blunders_per_100"].n == 100
    assert m["blunders_per_100"].games == 2
    assert m["blunders_per_100"].events == pytest.approx(2.0)


def test_accuracy_is_mean_of_games_and_skips_missing() -> None:
    games = [_game(accuracy=80.0), _game(accuracy=60.0), _game(accuracy=None)]
    acc = compute_metrics(games)["accuracy"]
    assert acc.value == pytest.approx(70.0)
    assert acc.n == 2


def test_phase_accuracy_uses_contested_moves_only() -> None:
    games = [
        _game(phases={"endgame": PhaseAgg(moves=10, accuracy_sum=700.0)}),
        _game(phases={"endgame": PhaseAgg(moves=30, accuracy_sum=1500.0)}),
        _game(phases={"endgame": PhaseAgg()}),
    ]
    m = compute_metrics(games)
    assert m["accuracy_endgame"].value == pytest.approx(2200 / 40)
    assert m["accuracy_endgame"].n == 40
    assert "accuracy_opening" not in m


def test_conversion_and_resilience() -> None:
    games = [
        _game(max_win_after=95.0, min_win_after=40.0, outcome="win"),
        _game(max_win_after=85.0, min_win_after=10.0, outcome="draw"),
        _game(max_win_after=60.0, min_win_after=5.0, outcome="loss"),
        _game(max_win_after=90.0, min_win_after=50.0, outcome=None),
    ]
    m = compute_metrics(games)
    # Выигранная позиция — в 2 партиях с результатом, выиграна 1.
    assert m["conversion"].value == pytest.approx(50.0)
    assert m["conversion"].n == 2
    # Проигранная позиция — в 2 партиях, не проиграна 1 (ничья).
    assert m["resilience"].value == pytest.approx(50.0)


def test_time_metrics_use_clock_known_moves() -> None:
    games = [
        _game(clock_moves=30, trouble_moves=6, hasty_errors=2),
        _game(clock_moves=0, trouble_moves=0, hasty_errors=0),
    ]
    m = compute_metrics(games)
    assert m["time_trouble_share"].value == pytest.approx(20.0)
    assert m["time_trouble_share"].n == 30
    # Поспешные — на 100 ходов вне цейтнота.
    assert m["hasty_per_100"].value == pytest.approx(100 * 2 / 24)


def test_motifs_per_100_own_moves() -> None:
    games = [_game(moves=50, motifs_missed={"fork": 2}), _game(moves=50)]
    m = compute_metrics(games)
    assert m["motif:fork"].value == pytest.approx(2.0)
    assert "motif:pin" not in m
    pin = metric_value(motif_spec("pin"), games)
    assert pin is not None
    assert pin.value == 0.0


def test_empty_games_have_no_metrics() -> None:
    assert compute_metrics([]) == {}
    assert compute_metrics([_game(moves=0)]) == {}
