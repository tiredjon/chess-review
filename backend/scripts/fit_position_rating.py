"""Рейтинг партии с учётом позиций: модель «насколько вероятна такая потеря у игрока рейтинга r
в этой позиции» по партиям из `scripts/analyze_rating_games.py`. Эксперимент 2026-11-26
(SPEC «Принятые решения»): итог — в прод не пошло.

Модель хода: потеря win% (шкала `cc_accuracy`) попадает в одну из корзин по порогам
THRESHOLDS; P(потеря > t | r, позиция) = σ(β_t·φ), φ — рейтинг, контроль, признаки позиции
(`app.review.difficulty`) и их произведения с рейтингом. Правдоподобие партии при рейтинге r —
сумма логарифмов вероятностей корзин её ходов; оценка — медиана апостериорного распределения.

Скрипт печатает на отложенных партиях ошибку оценки настоящего рейтинга игрока по одной партии
(с широким априори): без признаков позиции, с ними и по точности (`game_rating.py`). С
`--reference` — сравнение с Game Rating Chess.com на партиях, где он известен.

    uv run --with numpy python scripts/fit_position_rating.py moves.jsonl \\
        --reference ref.jsonl --game-ratings ratings.jsonl
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any

import chess
import numpy as np

from app.review.cc_accuracy import MIN_MOVE_ACCURACY, PARAMS, move_accuracy, win_percent
from app.review.difficulty import FEATURES, move_features
from app.review.game_rating import TimeClass, game_rating

TIME_CLASSES: tuple[TimeClass, ...] = ("bullet", "blitz", "rapid")
THRESHOLDS = (0.3, 1.0, 2.5, 5.0, 10.0, 20.0)
RATING_CENTER, RATING_SCALE = 1500.0, 500.0
GRID = np.arange(100, 3201, 25, dtype=float)
PRIOR = (1500.0, 800.0)


def design(rating: np.ndarray, tc: np.ndarray, x: np.ndarray | None) -> np.ndarray:
    """1, r, r², блиц, пуля, (блиц, пуля)·r, признаки позиции и их ·r."""
    r = (rating - RATING_CENTER) / RATING_SCALE
    columns = [np.ones_like(r), r, r**2]
    for name in ("blitz", "bullet"):
        dummy = (tc == TIME_CLASSES.index(name)).astype(float)
        columns += [dummy, dummy * r]
    if x is not None:
        for k in range(x.shape[1]):
            columns += [x[:, k], x[:, k] * r]
    return np.column_stack(columns)


def fit(matrix: np.ndarray, target: np.ndarray, ridge: float = 1e-3) -> np.ndarray:
    """Логистическая регрессия (IRLS) с небольшой L2-регуляризацией."""
    beta = np.zeros(matrix.shape[1])
    for _ in range(30):
        mu = 1 / (1 + np.exp(-(matrix @ beta)))
        w = np.clip(mu * (1 - mu), 1e-6, None)
        gradient = matrix.T @ (target - mu) - ridge * beta
        hessian = (matrix * w[:, None]).T @ matrix + ridge * np.eye(len(beta))
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return beta


def load(path: Path) -> list[dict[str, Any]]:
    """Стороны партий: рейтинги, контроль, потери win% ходов, признаки позиций, точность."""
    sides = []
    for line in path.open():
        game = json.loads(line)
        if game["time_class"] not in TIME_CLASSES:
            continue
        plies = game["plies"]
        board = chess.Board()
        losses: list[float] = []
        features: list[tuple[float, ...]] = []
        values: list[float] = []
        for index in range(len(plies) - 1):
            ply = plies[index]
            if "move" not in ply:
                break
            after = -plies[index + 1]["cp"]
            loss = max(0.0, win_percent(ply["cp"], PARAMS.k) - win_percent(after, PARAMS.k))
            best = chess.Move.from_uci(ply["lines"][0][0]) if ply["lines"] else None
            features.append(
                move_features(
                    [cp for _, cp in ply["lines"]],
                    ply["legal"],
                    ply["cp"],
                    previous_loss=losses[-1] if losses else 0.0,
                    best_is_capture=best is not None and board.is_capture(best),
                    ply=index,
                )
            )
            losses.append(loss)
            values.append(max(MIN_MOVE_ACCURACY, move_accuracy(ply["cp"], after, PARAMS)))
            board.push_uci(ply["move"])
        for side, color in enumerate(("white", "black")):
            own = slice(side, None, 2)
            if len(losses[own]) < 5:
                continue
            accuracy = float(np.mean(np.array(values[own]) ** PARAMS.p) ** (1 / PARAMS.p))
            sides.append(
                {
                    "url": game["url"],
                    "color": color,
                    "rating": game[f"{color}_rating"],
                    "opponent": game[f"{'black' if color == 'white' else 'white'}_rating"],
                    "tc": TIME_CLASSES.index(game["time_class"]),
                    "loss": np.array(losses[own]),
                    "x": np.array(features[own]),
                    "accuracy": accuracy,
                }
            )
    return sides


def fit_model(sides: list[dict[str, Any]], positional: bool) -> list[np.ndarray]:
    rating = np.concatenate([[s["rating"]] * len(s["loss"]) for s in sides]).astype(float)
    tc = np.concatenate([[s["tc"]] * len(s["loss"]) for s in sides])
    x = np.concatenate([s["x"] for s in sides]) if positional else None
    loss = np.concatenate([s["loss"] for s in sides])
    matrix = design(rating, tc, x)
    return [fit(matrix, (loss > t).astype(float)) for t in THRESHOLDS]


def loglik(side: dict[str, Any], betas: list[np.ndarray], positional: bool) -> np.ndarray:
    """Логарифм правдоподобия ходов стороны при каждом рейтинге сетки GRID."""
    n = len(side["loss"])
    rating = np.repeat(GRID, n)
    x = np.tile(side["x"], (len(GRID), 1)) if positional else None
    matrix = design(rating, np.full(len(rating), side["tc"]), x)
    exceed = [np.ones(len(rating))] + [1 / (1 + np.exp(-(matrix @ b))) for b in betas]
    exceed.append(np.zeros(len(rating)))
    bucket = np.searchsorted(THRESHOLDS, np.tile(side["loss"], len(GRID)), side="left")
    probs = np.stack(
        [np.clip(exceed[k] - exceed[k + 1], 1e-4, 1) for k in range(len(THRESHOLDS) + 1)], axis=1
    )
    chosen = probs[np.arange(len(rating)), bucket]
    result: np.ndarray = np.log(chosen).reshape(len(GRID), n).sum(axis=1)
    return result


def median(log: np.ndarray) -> float:
    weights = np.exp(log - log.max())
    return float(GRID[np.searchsorted(np.cumsum(weights) / weights.sum(), 0.5)])


def prior(mean: float, spread: float) -> np.ndarray:
    result: np.ndarray = -(((GRID - mean) / spread) ** 2) / 2
    return result


def report(label: str, sides: list[dict[str, Any]], estimates: list[float]) -> None:
    errors = np.array(estimates) - np.array([s["rating"] for s in sides])
    tcs = np.array([s["tc"] for s in sides])
    per_tc = ", ".join(
        f"{name} {np.mean(np.abs(errors[tcs == k])):.0f}"
        for k, name in enumerate(TIME_CLASSES)
        if (tcs == k).any()
    )
    print(f"{label:22} MAE {np.mean(np.abs(errors)):4.0f}  ({per_tc})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("moves", type=Path)
    parser.add_argument("--test", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--reference", type=Path, help="разбор партий с известным Game Rating")
    parser.add_argument("--game-ratings", type=Path, help="jsonl: url, color, game_rating")
    args = parser.parse_args()

    known: dict[tuple[str, str], int] = {}
    if args.game_ratings:
        for line in args.game_ratings.open():
            row = json.loads(line)
            known[(row["url"], row["color"])] = row["game_rating"]
    sides = [s for s in load(args.moves) if (s["url"], s["color"]) not in known]
    urls = sorted({s["url"] for s in sides})
    random.Random(args.seed).shuffle(urls)
    test_urls = set(urls[: int(len(urls) * args.test)])
    train = [s for s in sides if s["url"] not in test_urls]
    test = [s for s in sides if s["url"] in test_urls]
    print(f"сторон: обучение {len(train)}, проверка {len(test)}; признаки {FEATURES}")
    print("Ошибка оценки настоящего рейтинга по одной партии (априори N(1500, 800²)):")

    wide = prior(*PRIOR)
    accuracy_estimates = [
        float(game_rating(s["accuracy"], TIME_CLASSES[s["tc"]], rating=None, opponent_rating=None))
        for s in test
    ]
    report("по точности", test, accuracy_estimates)
    for positional in (False, True):
        betas = fit_model(train, positional)
        estimates = [median(loglik(s, betas, positional) + wide) for s in test]
        report("по ходам" + (" + позиции" if positional else ""), test, estimates)

    if args.reference and known:
        betas = fit_model(sides, True)
        print("Game Rating Chess.com: точность, рейтинг, Chess.com, по точности, по ходам:")
        errors: dict[str, list[float]] = {"accuracy": [], "moves": []}
        for s in load(args.reference):
            target = known.get((s["url"], s["color"]))
            if target is None:
                continue
            tc = TIME_CLASSES[s["tc"]]
            by_accuracy = game_rating(
                s["accuracy"], tc, rating=s["rating"], opponent_rating=s["opponent"]
            )
            by_moves = median(loglik(s, betas, True) + prior(s["rating"], 700.0))
            errors["accuracy"].append(by_accuracy - target)
            errors["moves"].append(by_moves - target)
            print(
                f"  {tc:6} {s['accuracy']:5.1f} {s['rating']:5}  {target:5} "
                f"{by_accuracy:5} {by_moves:6.0f}"
            )
        for name, values in errors.items():
            print(
                f"  {name:9} MAE {np.mean(np.abs(values)):4.0f}, смещение {np.mean(values):+4.0f}"
            )


if __name__ == "__main__":
    main()
