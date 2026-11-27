"""Диагностика тренера (SPEC «Сессия 17», 17.1): метрики пользователя по партиям цели против
эталонов текущей и целевой рейтинговых групп → сильные и слабые стороны.

Чистая часть (`evaluate_metric`, `percentile`, `norm_at`, `find_gaps`) не ходит в БД;
`diagnose` собирает агрегаты партий, примеры и тренировки. Все пороги — `DiagnosisThresholds`.

- Группа — квартили эталона на рейтинге: между соседними центрами — линейная интерполяция,
  за крайним центром — крайняя группа, если до неё не дальше `max_band_distance`.
- `percentile` — место значения среди целевой группы: между p25 и p75 — кусочно-линейно,
  хвосты — нормальное приближение со своей σ на каждой стороне (σ = (p50 − p25) / 0.6745 и
  (p75 − p50) / 0.6745: в p25 и p75 хвост и середина сходятся). С учётом направления: больше —
  лучше.
- Слабая сторона — перцентиль среди целевой группы ниже `weak_pct`, и устойчиво: значение,
  сдвинутое на `robust_z` стандартных ошибок в лучшую сторону, всё ещё ниже `robust_pct`
  (иначе это может быть шум нескольких партий). Сильная — выше `strong_pct` среди текущей
  группы с той же проверкой в худшую сторону. Объём — не меньше `min_volume` по виду метрики.
- `severity` слабой стороны — по перцентилю (ниже `high_pct` — high, ниже `medium_pct` —
  medium); `score` = 2 · (50 − перцентиль) для слабых и 2 · (перцентиль текущей − 50) для
  сильных, 0…100 — та же шкала, что у выводов 16.1 (дебюты берутся оттуда как есть).
- Буллет сравнивается с эталоном блица, daily — с рапидом; Lichess — без эталона (шкала
  рейтинга другая): метрики считаются, сравнений нет.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import CTE

from app.api.schemas_coach import (
    DiagnosisOut,
    GapOut,
    GoalOut,
    MetricOut,
    MetricStatus,
    NormOut,
    Severity,
)
from app.api.schemas_insights import ExampleOut, TrainOut, TrainQueryOut
from app.coach.lessons import lesson_for
from app.coach.metrics import (
    ERRORS,
    METRICS,
    MOTIF_PREFIX,
    GameAgg,
    MetricSpec,
    MetricValue,
    load_game_aggs,
    metric_value,
    motif_spec,
)
from app.coach.norms import BAND_HALF_WIDTH, NORM_FALLBACK, nearest_center
from app.coach.norms_data import Band, Norms, Quartiles, load_norms
from app.db.models import CoachGoal, GameSource, Move
from app.insights.queries import (
    ExampleRow,
    _available,
    _examples,
    _finding_examples,
    user_insights,
)
from app.insights.rules import THRESHOLDS as INSIGHT_THRESHOLDS
from app.insights.rules import Finding, Stats, Train
from app.review.game_rating import TimeClass
from app.review.types import Phase
from app.stats.queries import user_games

_NORMAL = NormalDist()
_Q75_Z = _NORMAL.inv_cdf(0.75)


@dataclass(frozen=True, slots=True)
class DiagnosisThresholds:
    min_games: int = 20
    # Своих ходов в разобранных партиях цели — не меньше (иначе `insufficient`).
    min_moves: int = 600
    weak_pct: float = 35.0
    strong_pct: float = 65.0
    robust_z: float = 1.0
    robust_pct: float = 50.0
    high_pct: float = 10.0
    medium_pct: float = 20.0
    # Минимальный объём по виду метрики: партий (точность партии, реализация, защита) или
    # ходов (остальное).
    min_volume: Mapping[str, int] = field(
        default_factory=lambda: {
            "accuracy": 20,
            "accuracy_phase": 120,
            "per_move": 400,
            "conversion": 8,
            "resilience": 8,
            "time": 300,
            "motif": 400,
        }
    )
    # Пропусков мотива у пользователя — не меньше, чтобы звать мотив слабостью.
    motif_min_events: int = 3
    # Дальше крайней группы (от центра) эталон не экстраполируется.
    max_band_distance: int = BAND_HALF_WIDTH
    max_weaknesses: int = 6
    max_strengths: int = 4
    max_motif_weaknesses: int = 3
    max_opening_weaknesses: int = 2


THRESHOLDS = DiagnosisThresholds()


def _volume_kind(key: str) -> str:
    if key.startswith(MOTIF_PREFIX):
        return "motif"
    if key in ("accuracy", "conversion", "resilience"):
        return key
    if key.startswith("accuracy_"):
        return "accuracy_phase"
    if key in ("time_trouble_share", "hasty_per_100"):
        return "time"
    return "per_move"


# --- Эталон на рейтинге -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Norm:
    p25: float
    p50: float
    p75: float

    def out(self) -> NormOut:
        return NormOut(p25=round(self.p25, 2), p50=round(self.p50, 2), p75=round(self.p75, 2))


def _q(q: Quartiles) -> Norm:
    return Norm(q.p25, q.p50, q.p75)


def norm_at(
    bands: Sequence[Band], key: str, rating: int, t: DiagnosisThresholds = THRESHOLDS
) -> Norm | None:
    """Квартили метрики на рейтинге (см. модуль); групп с этой метрикой нет — None."""
    with_key = [b for b in bands if key in b.metrics]
    if not with_key:
        return None
    below = [b for b in with_key if b.center <= rating]
    above = [b for b in with_key if b.center >= rating]
    lo = max(below, key=lambda b: b.center, default=None)
    hi = min(above, key=lambda b: b.center, default=None)
    if lo is not None and hi is not None:
        if lo.center == hi.center:
            return _q(lo.metrics[key])
        w = (rating - lo.center) / (hi.center - lo.center)
        a, b = lo.metrics[key], hi.metrics[key]
        return Norm(
            a.p25 + w * (b.p25 - a.p25), a.p50 + w * (b.p50 - a.p50), a.p75 + w * (b.p75 - a.p75)
        )
    edge = lo or hi
    assert edge is not None
    if abs(edge.center - rating) > t.max_band_distance:
        return None
    return _q(edge.metrics[key])


def percentile(value: float, norm: Norm, *, higher_better: bool) -> float:
    """Место значения среди группы, 0–100, больше — лучше (см. модуль)."""
    p25, p50, p75 = norm.p25, norm.p50, norm.p75
    if p25 <= value <= p75:
        if value <= p50:
            raw = 25 + 25 * ((value - p25) / (p50 - p25) if p50 > p25 else 1.0)
        else:
            raw = 50 + 25 * ((value - p50) / (p75 - p50) if p75 > p50 else 0.0)
    elif value < p25:
        sigma = (p50 - p25) / _Q75_Z
        raw = 100 * _NORMAL.cdf((value - p50) / sigma) if sigma > 0 else 0.0
    else:
        sigma = (p75 - p50) / _Q75_Z
        raw = 100 * _NORMAL.cdf((value - p50) / sigma) if sigma > 0 else 100.0
    raw = min(max(raw, 0.0), 100.0)
    return raw if higher_better else 100 - raw


# --- Оценка метрики ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetricEval:
    spec: MetricSpec
    value: MetricValue | None
    current: Norm | None
    target: Norm | None
    percentile: float | None
    current_percentile: float | None
    status: MetricStatus
    severity: Severity | None = None
    score: float = 0.0
    # Объёма данных пользователя хватает (иначе значение не показывается).
    enough: bool = True


def _enough(spec: MetricSpec, value: MetricValue, t: DiagnosisThresholds) -> bool:
    return value.n >= t.min_volume[_volume_kind(spec.key)]


def _shifted(value: MetricValue, z: float, *, better: bool, higher_better: bool) -> float | None:
    if value.se is None:
        return None
    sign = 1 if better == higher_better else -1
    return value.value + sign * z * value.se


def evaluate_metric(
    spec: MetricSpec,
    value: MetricValue | None,
    current: Norm | None,
    target: Norm | None,
    t: DiagnosisThresholds = THRESHOLDS,
) -> MetricEval:
    higher = spec.direction == "higher_better"
    if value is None or not _enough(spec, value, t):
        return MetricEval(spec, value, current, target, None, None, "insufficient", enough=False)
    pct = None if target is None else percentile(value.value, target, higher_better=higher)
    cur = None if current is None else percentile(value.value, current, higher_better=higher)
    if pct is None and cur is None:
        return MetricEval(spec, value, current, target, None, None, "insufficient")
    status: MetricStatus = "neutral"
    severity: Severity | None = None
    score = 0.0
    motif_ok = not spec.key.startswith(MOTIF_PREFIX) or value.events >= t.motif_min_events
    if pct is not None and pct < t.weak_pct and motif_ok and target is not None:
        optimistic = _shifted(value, t.robust_z, better=True, higher_better=higher)
        if (
            optimistic is not None
            and percentile(optimistic, target, higher_better=higher) < t.robust_pct
        ):
            status = "weakness"
            severity = "high" if pct < t.high_pct else "medium" if pct < t.medium_pct else "low"
            score = round(min(100.0, 2 * (50 - pct)), 1)
    if status == "neutral" and cur is not None and cur > t.strong_pct and current is not None:
        pessimistic = _shifted(value, t.robust_z, better=False, higher_better=higher)
        if (
            pessimistic is not None
            and percentile(pessimistic, current, higher_better=higher) > t.robust_pct
        ):
            status = "strength"
            score = round(min(100.0, 2 * (cur - 50)), 1)
    return MetricEval(spec, value, current, target, pct, cur, status, severity, score)


def metric_out(e: MetricEval) -> MetricOut:
    kind = "motif" if e.spec.key.startswith(MOTIF_PREFIX) else "metric"
    key = e.spec.key.removeprefix(MOTIF_PREFIX)
    # `value: null` — мало данных у пользователя; без эталона значение показывается.
    return MetricOut(
        kind=kind,
        key=key,
        value=None if e.value is None or not e.enough else round(e.value.value, 2),
        n=e.value.n if e.value is not None else 0,
        direction=e.spec.direction,
        current=e.current.out() if e.current else None,
        target=e.target.out() if e.target else None,
        percentile=None if e.percentile is None else round(e.percentile, 1),
        status=e.status,
    )


_SEVERITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


def find_gaps(
    evals: Sequence[MetricEval], t: DiagnosisThresholds = THRESHOLDS
) -> tuple[list[MetricEval], list[MetricEval]]:
    """(сильные, слабые) по важности с лимитами."""
    weak = sorted(
        (e for e in evals if e.status == "weakness"),
        key=lambda e: (_SEVERITY_ORDER[e.severity or "low"], -e.score, e.spec.key),
    )
    motifs = [e for e in weak if e.spec.key.startswith(MOTIF_PREFIX)][: t.max_motif_weaknesses]
    weak = [e for e in weak if not e.spec.key.startswith(MOTIF_PREFIX) or e in motifs]
    strong = sorted(
        (e for e in evals if e.status == "strength"), key=lambda e: (-e.score, e.spec.key)
    )
    return strong[: t.max_strengths], weak[: t.max_weaknesses]


def has_enough(games: Sequence[GameAgg], t: DiagnosisThresholds = THRESHOLDS) -> bool:
    """Разобранных партий цели и своих ходов в них хватает для выводов."""
    return len(games) >= t.min_games and sum(g.moves for g in games) >= t.min_moves


def evaluate_all(
    games: Sequence[GameAgg],
    bands: Sequence[Band],
    current_rating: int,
    target_rating: int,
    t: DiagnosisThresholds = THRESHOLDS,
) -> list[MetricEval]:
    """Фиксированные метрики + мотивы, у которых есть эталон целевой группы."""
    motif_keys = sorted({k for b in bands for k in b.metrics if k.startswith(MOTIF_PREFIX)})
    specs = [*METRICS, *(motif_spec(k.removeprefix(MOTIF_PREFIX)) for k in motif_keys)]
    enough = has_enough(games, t)
    result = []
    for spec in specs:
        current = norm_at(bands, spec.key, current_rating, t)
        target = norm_at(bands, spec.key, target_rating, t)
        value = metric_value(spec, games)
        if not enough:
            result.append(
                MetricEval(spec, value, current, target, None, None, "insufficient", enough=False)
            )
        else:
            result.append(evaluate_metric(spec, value, current, target, t))
    return result


# --- Тренировка, урок, примеры ----------------------------------------------------------------

_PHASE_OF = {
    "accuracy_opening": Phase.OPENING,
    "accuracy_middlegame": Phase.MIDDLEGAME,
    "accuracy_endgame": Phase.ENDGAME,
}


def train_for(key: str) -> Train | None:
    """Как у выводов 16.1: мотив → пазлы по теме, фаза → пазлы фазы / эндшпиль, цейтнот →
    пазлы (экран строит ссылку на забег `mode=rush` по ключу `time_trouble_share`, как для
    `time:trouble` в 16.1), реализация → эндшпиль, защита → партия с ботом."""
    if key.startswith(MOTIF_PREFIX):
        return Train(kind="puzzles", theme=key.removeprefix(MOTIF_PREFIX))
    if key == "accuracy_endgame":
        return Train(kind="endgames")
    if key in _PHASE_OF:
        return Train(kind="puzzles", phase=_PHASE_OF[key])
    if key == "conversion":
        return Train(kind="endgames")
    if key == "resilience":
        return Train(kind="play")
    return Train(kind="puzzles")


def _finding(key: str) -> Finding | None:
    """Вывод 16.1 с теми же примерами, если для метрики есть такой вид."""
    stats = Stats(0, 0, 0, 0)
    if key.startswith(MOTIF_PREFIX):
        return Finding("motif", key.removeprefix(MOTIF_PREFIX), "low", 0, stats)
    if key in _PHASE_OF:
        return Finding("phase", _PHASE_OF[key].value, "low", 0, stats)
    if key == "time_trouble_share":
        return Finding("time", "trouble", "low", 0, stats)
    if key == "hasty_per_100":
        return Finding("time", "hasty", "low", 0, stats)
    if key == "conversion":
        return Finding("conversion", "winning", "low", 0, stats)
    return None


def _condition(key: str) -> Any:
    error = Move.move_class.in_(ERRORS)
    match key:
        case "blunders_per_100":
            return Move.move_class == "blunder"
        case "mistakes_per_100":
            return Move.move_class == "mistake"
        case "misses_per_100":
            return and_(Move.is_miss, ~error)
        case "resilience":
            # Ошибки в худших позициях: защиту проигрывают здесь.
            return and_(error, Move.win_before <= 30)
    return and_(error, Move.win_before.between(10, 90))


async def _gap_examples(session: AsyncSession, ug: CTE, key: str) -> list[ExampleRow]:
    finding = _finding(key)
    if finding is not None:
        return await _finding_examples(session, ug, finding, INSIGHT_THRESHOLDS)
    return await _examples(session, ug, _condition(key))


def _example_out(row: ExampleRow) -> ExampleOut:
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


def _train_out(train: Train, available: int) -> TrainOut:
    return TrainOut(
        kind=train.kind,
        query=TrainQueryOut(theme=train.theme, phase=train.phase, eco=train.eco),
        available=available,
    )


# --- Сборка ответа ----------------------------------------------------------------------------


async def current_rating(session: AsyncSession, user_id: uuid.UUID, goal: CoachGoal) -> int:
    """Рейтинг пользователя в последней партии цели (нет — стартовый рейтинг цели)."""
    ug = user_games(user_id, GameSource(goal.source), _tc(goal))
    rating = await session.scalar(
        select(ug.c.rating)
        .where(ug.c.rating.is_not(None), ug.c.user_color.is_not(None))
        .order_by(ug.c.ts.desc())
        .limit(1)
    )
    return int(rating) if rating is not None else goal.start_rating


def _tc(goal: CoachGoal) -> TimeClass:
    return goal.time_class  # type: ignore[return-value]


def goal_out(goal: CoachGoal, rating: int) -> GoalOut:
    return GoalOut(
        id=goal.id,
        source=goal.source.value,
        time_class=_tc(goal),
        start_rating=goal.start_rating,
        current_rating=rating,
        target_rating=goal.target_rating,
        minutes_per_day=goal.minutes_per_day,
        days_per_week=goal.days_per_week,
        tz=goal.tz,
        created_at=goal.created_at,
        achieved_at=goal.achieved_at,
    )


def norm_bands(norms: Norms, goal: CoachGoal) -> tuple[Band, ...]:
    if GameSource(goal.source) != GameSource.CHESSCOM:
        return ()
    tc = NORM_FALLBACK.get(goal.time_class, goal.time_class)
    return norms.bands.get(tc, ())


def _band_center(bands: Sequence[Band], rating: int) -> int:
    nearest = min(bands, key=lambda b: abs(b.center - rating), default=None)
    if nearest is not None:
        return nearest.center
    clamped = min(max(rating, 800), 2600)
    return nearest_center(clamped) or clamped


async def _gap(
    session: AsyncSession, user_id: uuid.UUID, ug: CTE, e: MetricEval, *, strength: bool
) -> GapOut:
    assert e.value is not None
    key = e.spec.key
    kind = "motif" if key.startswith(MOTIF_PREFIX) else "metric"
    short = key.removeprefix(MOTIF_PREFIX)
    train = train_for(key)
    train_out = None
    if train is not None and not strength:
        train_out = _train_out(train, await _available(session, user_id, train))
    examples = [] if strength else [_example_out(r) for r in await _gap_examples(session, ug, key)]
    target = e.target.p50 if e.target is not None else None
    return GapOut(
        kind=kind,
        key=short,
        severity=e.severity or "low",
        score=e.score,
        value=round(e.value.value, 2),
        target_p50=None if target is None else round(target, 2),
        train=train_out,
        lesson=lesson_for(kind, short),
        examples=examples,
    )


async def _opening_gaps(
    session: AsyncSession, user_id: uuid.UUID, goal: CoachGoal, t: DiagnosisThresholds
) -> tuple[list[MetricOut], list[GapOut]]:
    """Дебюты — выводы 16.1 как есть, без эталона."""
    result = await user_insights(
        session, user_id, source=GameSource(goal.source), time_class=_tc(goal)
    )
    metrics, gaps = [], []
    for insight in result.insights:
        f = insight.finding
        if f.kind != "opening":
            continue
        metrics.append(
            MetricOut(
                kind="opening",
                key=f.key,
                value=f.stats.value,
                n=f.stats.count,
                direction="higher_better",
                current=None,
                target=None,
                percentile=None,
                status="weakness",
            )
        )
        gaps.append(
            GapOut(
                kind="opening",
                key=f.key,
                severity=f.severity,
                score=f.score,
                value=f.stats.value,
                target_p50=None,
                train=None if f.train is None else _train_out(f.train, insight.available or 0),
                lesson=lesson_for("opening", f.key),
                examples=[_example_out(r) for r in insight.examples],
            )
        )
    return metrics, gaps[: t.max_opening_weaknesses]


async def diagnose(
    session: AsyncSession,
    user_id: uuid.UUID,
    goal: CoachGoal,
    *,
    norms: Norms | None = None,
    t: DiagnosisThresholds = THRESHOLDS,
) -> DiagnosisOut:
    norms = norms or load_norms()
    rating = await current_rating(session, user_id, goal)
    ug = user_games(user_id, GameSource(goal.source), _tc(goal))
    games = await load_game_aggs(session, ug)
    bands = norm_bands(norms, goal)
    evals = evaluate_all(games, bands, rating, goal.target_rating, t)
    metrics = [metric_out(e) for e in evals]
    strengths: list[GapOut] = []
    weaknesses: list[GapOut] = []
    if has_enough(games, t):
        strong, weak = find_gaps(evals, t)
        strengths = [await _gap(session, user_id, ug, e, strength=True) for e in strong]
        weaknesses = [await _gap(session, user_id, ug, e, strength=False) for e in weak]
        opening_metrics, opening_gaps = await _opening_gaps(session, user_id, goal, t)
        metrics += opening_metrics
        weaknesses = sorted(
            [*weaknesses, *opening_gaps],
            key=lambda g: (_SEVERITY_ORDER[g.severity], -g.score, g.kind, g.key),
        )[: t.max_weaknesses]
    return DiagnosisOut(
        goal=goal_out(goal, rating),
        current_rating=rating,
        current_band=_band_center(bands, rating),
        target_band=_band_center(bands, goal.target_rating),
        norms_version=norms.version,
        analyzed_games=len(games),
        min_games=t.min_games,
        metrics=metrics,
        strengths=strengths,
        weaknesses=weaknesses,
    )
