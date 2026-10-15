"""Подбор параметров точности «как у Chess.com» (`app/review/cc_accuracy.py`) по партиям, у
которых есть и наш разбор, и официальная точность Chess.com (`games.source_*_accuracy`).

Модель — та же схема, что у Lichess, с подбираемыми параметрами:
  win%(cp) = 50 + 50·(2/(1 + e^(−k·cp)) − 1), cp ∈ [−CP_CAP, CP_CAP], мат — ±CP_CAP;
  Δ = max(0, win%до − win%после) за ходящего;
  точность хода = (100 + c)·e^(−b·Δ) − c, в [0, 100];
  точность партии = степенное среднее с показателем p (p = 1 — обычное, p = −1 — гармоническое).
Качество — MAE на 5-кратной перекрёстной проверке.

    PYTHONPATH=. uv run python scripts/fit_accuracy.py
"""

import asyncio
import random
from dataclasses import dataclass

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import Analysis, AnalysisStatus, Game, Move
from app.db.session import Database
from app.review.cc_accuracy import CP_CAP, CcParams, game_accuracy
from scripts.fitting import nelder_mead

FOLDS = 5


@dataclass
class Sample:
    # (cp_before, cp_after) за ходящего, мат — ±CP_CAP.
    moves: list[tuple[float, float]]
    target: float
    # Наша точность по формуле Lichess — для сравнения.
    lichess: float


def to_cp(cp: int | None, mate: int | None) -> float:
    if mate is not None:
        return CP_CAP if mate >= 0 else -CP_CAP
    return float(max(-CP_CAP, min(CP_CAP, cp or 0)))


async def load() -> list[Sample]:
    settings = Settings()
    db = Database(settings.database_url)
    samples: list[Sample] = []
    async with db.sessionmaker() as session:
        rows = await session.execute(
            select(
                Analysis.id,
                Game.source_white_accuracy,
                Game.source_black_accuracy,
                Analysis.white_accuracy,
                Analysis.black_accuracy,
            )
            .join(Game)
            .where(
                Analysis.status == AnalysisStatus.DONE,
                Game.source_white_accuracy.is_not(None),
                Game.source_black_accuracy.is_not(None),
            )
        )
        for analysis_id, white, black, lichess_white, lichess_black in rows.all():
            moves = list(
                await session.scalars(
                    select(Move).where(Move.analysis_id == analysis_id).order_by(Move.ply)
                )
            )
            for color, target, lichess in (
                ("w", white, lichess_white),
                ("b", black, lichess_black),
            ):
                own = [
                    (
                        to_cp(m.eval_before_cp, m.mate_before),
                        # Мат на доске (mate_after == 0) — выигрыш ходящего.
                        to_cp(m.eval_after_cp, m.mate_after),
                    )
                    for m in moves
                    if m.fen_before.split()[1] == color
                ]
                if own and target is not None and lichess is not None:
                    samples.append(Sample(own, target, lichess))
    await db.dispose()
    return samples


def loss(params: CcParams, samples: list[Sample]) -> float:
    return sum(abs(game_accuracy(s.moves, params) - s.target) for s in samples) / len(samples)


def fit(samples: list[Sample]) -> CcParams:
    def objective(x: list[float]) -> float:
        k, b, c, p = x
        if not (0.0005 < k < 0.02 and 0.001 < b < 0.5 and -10 < c < 60 and -3 < p < 3):
            return 1e9
        return loss(CcParams(k=k, b=b, c=c, p=p), samples)

    best = nelder_mead(objective, [0.00368208, 0.04354, 3.1669, 1.0], [0.001, 0.01, 2.0, 0.5])
    return CcParams(*best)


async def main() -> None:
    samples = await load()
    print(f"игроко-партий: {len(samples)}")
    lichess_mae = sum(abs(s.lichess - s.target) for s in samples) / len(samples)
    print(f"формула Lichess (наша прежняя точность): MAE {lichess_mae:.2f}")

    random.Random(1).shuffle(samples)
    errors = []
    for fold in range(FOLDS):
        test = samples[fold::FOLDS]
        train = [s for i, s in enumerate(samples) if i % FOLDS != fold]
        errors.append(loss(fit(train), test))
    by_fold = ", ".join(f"{e:.2f}" for e in errors)
    print(f"перекрёстная проверка: MAE {sum(errors) / len(errors):.2f} ({by_fold})")

    final = fit(samples)
    print(f"на всех данных: MAE {loss(final, samples):.2f}")
    print(f"CcParams(k={final.k:.6g}, b={final.b:.6g}, c={final.c:.6g}, p={final.p:.6g})")
    worst = sorted(samples, key=lambda s: -abs(game_accuracy(s.moves, final) - s.target))[:5]
    for s in worst:
        print(f"  худшие: Chess.com {s.target:.1f}, модель {game_accuracy(s.moves, final):.1f}")


if __name__ == "__main__":
    asyncio.run(main())
