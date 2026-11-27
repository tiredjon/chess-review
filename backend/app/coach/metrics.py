"""Метрики тренера (SPEC «Сессия 17», «Метрики»): агрегаты партий → значения метрик.

Одна и та же чистая функция `compute_metrics` считает метрики пользователя (по партиям цели)
и игроков выборки эталона (по их партиям) — сравнение честное, только если формулы
совпадают. SQL-загрузка агрегатов (`load_game_aggs`) тоже общая: партии выборки лежат в БД
эталонов как партии служебного пользователя.

Каждая метрика — отношение сумм по партиям: Σ числитель / Σ знаменатель (× масштаб). Так
«на 100 ходов» весит ходы, а не партии, а точность партии — партии. Погрешность — по партиям
как кластерам (ход в партии не независим): se² = k/(k−1) · Σ(cᵢ − r·mᵢ)² / (Σmᵢ)². Её
используют проверка устойчивости в диагностике и сжатие разброса в эталоне.

Определения (только свои ходы партии, у анализа — готовый статус):
— `accuracy` — точность партии (§4.4, формула Lichess нашего анализа), среднее по партиям;
— `accuracy_<фаза>` — средняя точность ходов фазы из неясных позиций (win% до хода 10–90);
— `blunders|mistakes|misses_per_100` — ходов класса на 100 своих; miss — как в интерфейсе
  (`is_miss`, но не mistake / blunder);
— `conversion` — % выигранных из партий, где после своего хода был win% ≥ 80;
  `resilience` — % не проигранных из партий, где был win% ≤ 20;
— `time_trouble_share` — % ходов в цейтноте среди ходов с известным временем;
  `hasty_per_100` — быстрых ошибок (mistake / blunder) вне цейтнота на 100 таких ходов;
— `motif:<тип>` — пропусков мотива лучшего хода на 100 своих ходов (как в 16.1: ход не лучший,
  ошибка или miss, мотив в `motifs.missed`).
"""

import math
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import and_, column, func, literal_column, or_, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import CTE

from app.db.models import Analysis, Color, Move
from app.review.types import MoveClass, Phase
from app.stats.queries import analyzed_moves, clock_sql

Direction = Literal["higher_better", "lower_better"]

CONTESTED_MIN, CONTESTED_MAX = 10.0, 90.0
WINNING, LOSING = 80.0, 20.0
ERRORS = (MoveClass.MISTAKE, MoveClass.BLUNDER)
MOTIF_PREFIX = "motif:"


@dataclass(frozen=True, slots=True)
class PhaseAgg:
    """Свои ходы фазы из неясных позиций: сколько и сумма их точности."""

    moves: int = 0
    accuracy_sum: float = 0.0


@dataclass(frozen=True, slots=True)
class GameAgg:
    """Агрегаты одной разобранной партии по своим ходам."""

    game_id: uuid.UUID
    moves: int
    accuracy: float | None = None
    blunders: int = 0
    mistakes: int = 0
    misses: int = 0
    phases: Mapping[str, PhaseAgg] = field(default_factory=dict)
    max_win_after: float | None = None
    min_win_after: float | None = None
    outcome: Literal["win", "draw", "loss"] | None = None
    clock_moves: int = 0
    trouble_moves: int = 0
    hasty_errors: int = 0
    # Тип мотива → пропусков в партии.
    motifs_missed: Mapping[str, int] = field(default_factory=dict)
    rating: int | None = None


# Вклад партии в метрику: (числитель, знаменатель); None — партия в метрике не участвует.
Part = tuple[float, float] | None


@dataclass(frozen=True, slots=True)
class MetricSpec:
    key: str
    direction: Direction
    part: Callable[[GameAgg], Part]
    scale: float = 1.0
    # `n` метрики — партии (иначе — Σ знаменателей, то есть ходы).
    per_game: bool = False


def _per_move(count: Callable[[GameAgg], int]) -> Callable[[GameAgg], Part]:
    return lambda g: (count(g), g.moves) if g.moves else None


def _phase(phase: Phase) -> Callable[[GameAgg], Part]:
    def part(g: GameAgg) -> Part:
        p = g.phases.get(phase.value)
        return (p.accuracy_sum, p.moves) if p is not None and p.moves else None

    return part


def _conversion(g: GameAgg) -> Part:
    if g.max_win_after is None or g.max_win_after < WINNING or g.outcome is None:
        return None
    return (1.0 if g.outcome == "win" else 0.0), 1.0


def _resilience(g: GameAgg) -> Part:
    if g.min_win_after is None or g.min_win_after > LOSING or g.outcome is None:
        return None
    return (0.0 if g.outcome == "loss" else 1.0), 1.0


def _motif(motif: str) -> Callable[[GameAgg], Part]:
    return lambda g: (g.motifs_missed.get(motif, 0), g.moves) if g.moves else None


METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        "accuracy",
        "higher_better",
        lambda g: None if g.accuracy is None else (g.accuracy, 1.0),
        per_game=True,
    ),
    MetricSpec("accuracy_opening", "higher_better", _phase(Phase.OPENING)),
    MetricSpec("accuracy_middlegame", "higher_better", _phase(Phase.MIDDLEGAME)),
    MetricSpec("accuracy_endgame", "higher_better", _phase(Phase.ENDGAME)),
    MetricSpec("blunders_per_100", "lower_better", _per_move(lambda g: g.blunders), 100.0),
    MetricSpec("mistakes_per_100", "lower_better", _per_move(lambda g: g.mistakes), 100.0),
    MetricSpec("misses_per_100", "lower_better", _per_move(lambda g: g.misses), 100.0),
    MetricSpec("conversion", "higher_better", _conversion, 100.0, per_game=True),
    MetricSpec("resilience", "higher_better", _resilience, 100.0, per_game=True),
    MetricSpec(
        "time_trouble_share",
        "lower_better",
        lambda g: (g.trouble_moves, g.clock_moves) if g.clock_moves else None,
        100.0,
    ),
    MetricSpec(
        "hasty_per_100",
        "lower_better",
        lambda g: (
            (g.hasty_errors, g.clock_moves - g.trouble_moves)
            if g.clock_moves > g.trouble_moves
            else None
        ),
        100.0,
    ),
)
METRIC_KEYS: tuple[str, ...] = tuple(m.key for m in METRICS)


def motif_spec(motif: str) -> MetricSpec:
    return MetricSpec(f"{MOTIF_PREFIX}{motif}", "lower_better", _motif(motif), 100.0)


def all_specs(motifs: Iterable[str]) -> list[MetricSpec]:
    return [*METRICS, *(motif_spec(m) for m in sorted(set(motifs)))]


def spec_for(key: str) -> MetricSpec | None:
    if key.startswith(MOTIF_PREFIX):
        return motif_spec(key.removeprefix(MOTIF_PREFIX))
    return next((m for m in METRICS if m.key == key), None)


@dataclass(frozen=True, slots=True)
class MetricValue:
    value: float
    # Партий (метрики по партиям) или Σ знаменателей (ходы).
    n: int
    # Партий, давших вклад.
    games: int
    # Стандартная ошибка по партиям-кластерам; None — одна партия.
    se: float | None
    # Σ числителей без масштаба: сколько случаев (пропусков мотива, зевков…) или очков точности.
    events: float


def ratio(parts: Sequence[tuple[float, float]], scale: float = 1.0) -> tuple[float, float | None]:
    """Σc/Σm × scale и его ошибка по кластерам (см. модуль)."""
    total_m = sum(m for _, m in parts)
    r = sum(c for c, _ in parts) / total_m
    k = len(parts)
    if k < 2:
        return r * scale, None
    resid = sum((c - r * m) ** 2 for c, m in parts)
    return r * scale, scale * math.sqrt(k / (k - 1) * resid) / total_m


def metric_value(spec: MetricSpec, games: Iterable[GameAgg]) -> MetricValue | None:
    parts = [p for g in games if (p := spec.part(g)) is not None and p[1] > 0]
    if not parts:
        return None
    value, se = ratio(parts, spec.scale)
    n = len(parts) if spec.per_game else round(sum(m for _, m in parts))
    return MetricValue(value=value, n=n, games=len(parts), se=se, events=sum(c for c, _ in parts))


def compute_metrics(
    games: Sequence[GameAgg], specs: Sequence[MetricSpec] | None = None
) -> dict[str, MetricValue]:
    """Значения метрик по партиям: ключ → значение (метрики без данных пропускаются).
    По умолчанию — фиксированные метрики и мотивы, встретившиеся в партиях."""
    if specs is None:
        specs = all_specs(m for g in games for m in g.motifs_missed)
    return {s.key: v for s in specs if (v := metric_value(s, games)) is not None}


# --- Загрузка агрегатов из БД ---------------------------------------------------------------

_EMPTY = literal_column("'[]'::jsonb", JSONB)


def _contested() -> Any:
    return Move.win_before.between(CONTESTED_MIN, CONTESTED_MAX)


async def load_game_aggs(session: AsyncSession, ug: CTE) -> list[GameAgg]:
    """Агрегаты разобранных партий из CTE `app.stats.queries.user_games` (с известным цветом,
    готовым анализом). Ходы в Python не грузятся: всё считает PostgreSQL."""
    error = Move.move_class.in_(ERRORS)
    miss = and_(Move.is_miss, ~error)
    clock = clock_sql(ug)
    known = and_(*clock.known)
    phase_cols: list[Any] = []
    for phase in Phase:
        cond = and_(Move.phase == phase, _contested())
        phase_cols += [
            func.count().filter(cond).label(f"{phase.value}_n"),
            func.coalesce(func.sum(Move.accuracy).filter(cond), 0.0).label(f"{phase.value}_s"),
        ]
    stmt = (
        analyzed_moves(
            select(
                ug.c.id,
                ug.c.outcome,
                ug.c.rating,
                ug.c.user_color,
                func.max(Analysis.white_accuracy).label("white_accuracy"),
                func.max(Analysis.black_accuracy).label("black_accuracy"),
                func.count().label("moves"),
                func.count().filter(Move.move_class == MoveClass.BLUNDER).label("blunders"),
                func.count().filter(Move.move_class == MoveClass.MISTAKE).label("mistakes"),
                func.count().filter(miss).label("misses"),
                func.max(Move.win_after).label("max_win"),
                func.min(Move.win_after).label("min_win"),
                func.count().filter(known).label("clock_moves"),
                func.count().filter(known, clock.trouble).label("trouble_moves"),
                func.count().filter(known, ~clock.trouble, clock.fast, error).label("hasty"),
                *phase_cols,
            ).select_from(Move),
            ug,
        )
        .join(Analysis, Analysis.id == ug.c.analysis_id)
        .where(ug.c.user_color.is_not(None))
        .group_by(ug.c.id, ug.c.outcome, ug.c.rating, ug.c.user_color)
    )
    rows = (await session.execute(stmt)).all()
    motifs = await _missed_motifs(session, ug)
    result = []
    for row in rows:
        accuracy = row.white_accuracy if row.user_color == Color.WHITE else row.black_accuracy
        result.append(
            GameAgg(
                game_id=row.id,
                moves=int(row.moves),
                accuracy=None if accuracy is None else float(accuracy),
                blunders=int(row.blunders),
                mistakes=int(row.mistakes),
                misses=int(row.misses),
                phases={
                    p.value: PhaseAgg(
                        int(getattr(row, f"{p.value}_n")), float(getattr(row, f"{p.value}_s"))
                    )
                    for p in Phase
                },
                max_win_after=None if row.max_win is None else float(row.max_win),
                min_win_after=None if row.min_win is None else float(row.min_win),
                outcome=row.outcome,
                clock_moves=int(row.clock_moves),
                trouble_moves=int(row.trouble_moves),
                hasty_errors=int(row.hasty),
                motifs_missed=motifs.get(row.id, {}),
                rating=row.rating,
            )
        )
    return result


async def _missed_motifs(session: AsyncSession, ug: CTE) -> dict[uuid.UUID, dict[str, int]]:
    """Партия → тип мотива → своих ходов, где мотив лучшего хода упущен (как в 16.1)."""
    element = (
        func.jsonb_array_elements(func.coalesce(Move.motifs["missed"], _EMPTY))
        .table_valued(column("value", JSONB))
        .lateral("el")
    )
    error = Move.move_class.in_(ERRORS)
    per_move = (
        analyzed_moves(
            select(
                ug.c.id.label("game_id"),
                Move.id.label("move_id"),
                element.c.value["type"].astext.label("type"),
            ),
            ug,
        )
        .join(element, true())
        .where(
            ug.c.user_color.is_not(None),
            Move.best_uci.is_not(None),
            Move.uci != Move.best_uci,
            or_(error, Move.is_miss),
        )
        .distinct()
        .subquery()
    )
    rows = await session.execute(
        select(per_move.c.game_id, per_move.c.type, func.count().label("n")).group_by(
            per_move.c.game_id, per_move.c.type
        )
    )
    result: dict[uuid.UUID, dict[str, int]] = {}
    for row in rows:
        result.setdefault(row.game_id, {})[row.type] = int(row.n)
    return result
