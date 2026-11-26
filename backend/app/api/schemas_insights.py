"""Схемы `GET /insights/me` (SPEC «Сессия 16», 16.1)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.api.schemas import StatsFilters
from app.insights.queries import ExampleRow, Insight, InsightsResult
from app.review.types import Phase


class FindingStatsOut(BaseModel):
    """Показатель пользователя против его же базы (в процентах) и на чём он держится."""

    value: float
    baseline: float
    count: int
    total: int


class ExampleOut(BaseModel):
    game_id: uuid.UUID
    ply: int
    fen_before: str
    san: str
    best_san: str | None
    # Класс как в интерфейсе: `miss` вместо класса, если ход не mistake / blunder.
    move_class: str
    opponent: str
    played_at: datetime | None


class TrainQueryOut(BaseModel):
    theme: str | None = None
    phase: Phase | None = None
    eco: str | None = None


class TrainOut(BaseModel):
    kind: Literal["puzzles", "endgames", "course", "play"]
    query: TrainQueryOut
    # Сколько тренировок найдёт ссылка (пазлов, позиций эндшпиля; у курса — 1).
    available: int


class FindingOut(BaseModel):
    id: str
    kind: Literal["motif", "phase", "time", "opening", "conversion"]
    key: str
    severity: Literal["high", "medium", "low"]
    score: float
    stats: FindingStatsOut
    examples: list[ExampleOut]
    train: TrainOut | None


class InsightsOut(BaseModel):
    filters: StatsFilters
    analyzed_games: int
    min_games: int
    findings: list[FindingOut]


def _example(row: ExampleRow) -> ExampleOut:
    return ExampleOut(
        game_id=row.game_id,
        ply=row.ply,
        fen_before=row.fen_before,
        san=row.san,
        best_san=row.best_san,
        move_class=row.move_class,
        opponent=row.opponent,
        played_at=row.played_at,
    )


def _finding(insight: Insight) -> FindingOut:
    f = insight.finding
    train = None
    if f.train is not None:
        train = TrainOut(
            kind=f.train.kind,
            query=TrainQueryOut(theme=f.train.theme, phase=f.train.phase, eco=f.train.eco),
            available=insight.available or 0,
        )
    return FindingOut(
        id=f.id,
        kind=f.kind,
        key=f.key,
        severity=f.severity,
        score=f.score,
        stats=FindingStatsOut(
            value=f.stats.value, baseline=f.stats.baseline, count=f.stats.count, total=f.stats.total
        ),
        examples=[_example(row) for row in insight.examples],
        train=train,
    )


def insights_out(result: InsightsResult, filters: StatsFilters) -> InsightsOut:
    return InsightsOut(
        filters=filters,
        analyzed_games=result.analyzed_games,
        min_games=result.min_games,
        findings=[_finding(insight) for insight in result.insights],
    )
