"""Прогноз срока цели (SPEC «Сессия 17», 17.2): чистая функция, всегда диапазон.

Модель — распределение времени T до цели, F(t) = P(T ≤ t недель), t ≤ 156 (3 года).

1. **Базовая кривая** — строка `trajectories` по текущей группе и приросту (ближайшая).
   Точки F: (52, reached_52w), (104, reached_104w), (156, reached_156w) и квартили недель
   среди поднявшихся — (weeks_p25, ¼·reached_156w), (p50, ½·…), (p75, ¾·…); между точками —
   линейно, после последней — ровно (за 3 года выборка не говорит ничего). Время растягивается
   на `gain / row.gain` (прирост не совпадает со строкой) и на поправку активности: подгруппа
   по партиям в неделю пользователя — отношение её `weeks_p50` к строке (0,5–2) и её доли
   поднявшихся за 2 года к строке (0,3–3, на значения F).
2. **Свой тренд** — взвешенная регрессия недельного рейтинга (последний в неделе) по последним
   12 неделям, вес недели — число партий; нужно ≥ 3 недели. Скорость базы v₀ = прирост / время,
   когда F доходит до половины `reached_156w` (типичный поднявшийся) × reached_156w; итоговая
   v = (1 − λ)·v₀ + λ·тренд, λ = n / (n + 50) ≤ 0,7, n — партий за 12 недель. Время делится на
   v / v₀ (0,5–3; v ≤ 0 → 3).
3. **Adherence** (доля выполненных заданий за 4 недели плана): время × 1 / (0,75 + 0,25·a).
4. **Без эталона** (заглушка) при ≥ 30 партиях цели и тренде — F(t) = Φ((v·t − g) / σ(t)),
   σ(t) = se·t + 40 + 8√t; иначе `insufficient`.

Выход: `weeks_p50/p80` — первая неделя, где F ≥ 0,5 / 0,8 (нет за 3 года — `null`);
`reach_probability_1y` = F(52). Коридор `projection` по неделям до p80 (или 3 лет): линии
p90 / p50 / p10 доходят до цели к неделям F = 0,1 / 0,5 / 0,9 (нет такой недели — наклон
пропорционально F(156)), после цели линия растёт вчетверо медленнее; p10/p90 расширены
шумом рейтинга ±1,28·10√t. `status` — текущий
рейтинг против p50-линии первого прогноза плана (`Reference`) на сегодня, ±25; `confidence`:
low — эталон-заглушка или < 30 партий цели, high — ≥ 100 партий и ≥ 4 недели плана.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from app.api.schemas_coach import (
    Confidence,
    ForecastBasisOut,
    ForecastOut,
    ForecastPointOut,
    ForecastStatus,
    RatingPointOut,
)
from app.coach.norms_data import Trajectories, TrajectoryRow

HORIZON_WEEKS = 156
TREND_WEEKS = 12
MIN_TREND_POINTS = 3
LOW_GAMES = 30
HIGH_GAMES = 100
HIGH_PLAN_WEEKS = 4
STATUS_MARGIN = 25
MIN_ROW_PLAYERS = 10
MIN_ACTIVITY_PLAYERS = 5
MAX_RATING = 3200
Z80 = 1.2816
AFTER_TARGET = 0.25


@dataclass(frozen=True, slots=True)
class RatingWeek:
    """Рейтинг по партиям цели за неделю: последний в неделе и число партий."""

    week: date
    rating: int
    games: int


@dataclass(frozen=True, slots=True)
class Reference:
    """p50-линия первого прогноза плана: от (`day`, `rating`) до цели к `date_p50`."""

    day: date
    rating: int
    date_p50: date


@dataclass(frozen=True, slots=True)
class ForecastInput:
    today: date
    time_class: str
    start_rating: int
    current_rating: int
    target_rating: int
    history: Sequence[RatingWeek]
    user_games: int
    games_per_week: float
    adherence: float | None
    plan_weeks: int
    reference: Reference | None = None


Cdf = Callable[[float], float]


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def weighted_trend(
    history: Sequence[RatingWeek], today: date, weeks: int = TREND_WEEKS
) -> tuple[float, float, int] | None:
    """(Elo в неделю, стандартная ошибка, партий) по последним `weeks` неделям."""
    since = today - timedelta(weeks=weeks)
    points = [h for h in history if h.week >= since and h.games > 0]
    if len(points) < MIN_TREND_POINTS:
        return None
    xs = [(h.week - today).days / 7 for h in points]
    ys = [float(h.rating) for h in points]
    ws = [float(h.games) for h in points]
    sw = sum(ws)
    mx = sum(w * x for w, x in zip(ws, xs, strict=True)) / sw
    my = sum(w * y for w, y in zip(ws, ys, strict=True)) / sw
    sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs, strict=True))
    if sxx <= 1e-9:
        return None
    slope = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys, strict=True)) / sxx
    resid = sum(w * (y - (my + slope * (x - mx))) ** 2 for w, x, y in zip(ws, xs, ys, strict=True))
    dof = max(1, len(points) - 2)
    se = math.sqrt(resid / dof / sxx) if resid > 0 else 0.0
    return slope, max(se, 2.0), int(sw)


def _interp(points: Sequence[tuple[float, float]]) -> Cdf:
    def f(t: float) -> float:
        if t <= points[0][0]:
            return points[0][1]
        for (t0, v0), (t1, v1) in pairwise(points):
            if t <= t1:
                return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
        return points[-1][1]

    return f


def base_cdf(row: TrajectoryRow, gain: int, games_per_week: float) -> tuple[Cdf, int]:
    """CDF времени до цели по строке траекторий (п. 1 модуля) и игроков в основе."""
    k = max(0.25, gain / row.gain) if row.gain > 0 else 1.0
    a, pr, players = 1.0, 1.0, row.players
    bucket = next(
        (
            act
            for act in row.activity
            if act.games_per_week_lo <= games_per_week < act.games_per_week_hi
            and act.players >= MIN_ACTIVITY_PLAYERS
        ),
        None,
    )
    if bucket is not None:
        players = bucket.players
        if bucket.weeks_p50 and row.weeks_p50:
            a = min(2.0, max(0.5, bucket.weeks_p50 / row.weeks_p50))
        if row.reached_104w > 0:
            pr = min(3.0, max(0.3, bucket.reached_104w / row.reached_104w))
    r156 = row.reached_156w
    raw = [(52.0, row.reached_52w), (104.0, row.reached_104w), (156.0, r156)]
    for weeks, share in ((row.weeks_p25, 0.25), (row.weeks_p50, 0.5), (row.weeks_p75, 0.75)):
        if weeks is not None:
            raw.append((weeks, share * r156))
    raw.sort()
    points = [(0.0, 0.0)]
    for t, v in raw:
        points.append((t * k * a, max(points[-1][1], min(0.99, v * pr))))
    return _interp(points), players


def _inverse(f: Cdf, q: float, horizon: int = HORIZON_WEEKS) -> int | None:
    for week in range(1, horizon + 1):
        if f(week) >= q - 1e-12:
            return week
    return None


def _confidence(inp: ForecastInput, placeholder: bool) -> Confidence:
    if placeholder or inp.user_games < LOW_GAMES:
        return "low"
    if inp.user_games >= HIGH_GAMES and inp.plan_weeks >= HIGH_PLAN_WEEKS:
        return "high"
    return "medium"


def _status(inp: ForecastInput) -> ForecastStatus:
    ref = inp.reference
    if ref is None or ref.date_p50 <= ref.day:
        return "on_track"
    share = min(1.0, max(0.0, (inp.today - ref.day).days / (ref.date_p50 - ref.day).days))
    expected = ref.rating + (inp.target_rating - ref.rating) * share
    diff = inp.current_rating - expected
    if diff > STATUS_MARGIN:
        return "ahead"
    if diff < -STATUS_MARGIN:
        return "behind"
    return "on_track"


def _history(inp: ForecastInput) -> list[RatingPointOut]:
    return [RatingPointOut(date=h.week, rating=h.rating) for h in inp.history]


def forecast(inp: ForecastInput, trajectories: Trajectories) -> ForecastOut:
    placeholder = trajectories.version == "placeholder"
    gain = inp.target_rating - inp.current_rating
    trend = weighted_trend(inp.history, inp.today)
    basis = ForecastBasisOut(
        sample_players=0,
        user_games=inp.user_games,
        weekly_trend=None if trend is None else round(trend[0], 1),
        adherence=inp.adherence,
        games_per_week=round(inp.games_per_week, 1),
    )
    confidence = _confidence(inp, placeholder)

    def out(
        status: ForecastStatus,
        f: Cdf | None = None,
    ) -> ForecastOut:
        w50 = w80 = None
        prob = None
        projection: list[ForecastPointOut] = []
        if status == "achieved":
            w50 = w80 = 0
            prob = 1.0
        elif f is not None:
            w50, w80 = _inverse(f, 0.5), _inverse(f, 0.8)
            prob = round(f(52), 3)
            projection = _projection(inp, f, w80)
        return ForecastOut(
            start_rating=inp.start_rating,
            current_rating=inp.current_rating,
            target_rating=inp.target_rating,
            status=status,
            weeks_p50=w50,
            weeks_p80=w80,
            date_p50=None if w50 is None else inp.today + timedelta(weeks=w50),
            date_p80=None if w80 is None else inp.today + timedelta(weeks=w80),
            reach_probability_1y=prob,
            confidence=confidence,
            basis=basis,
            history=_history(inp),
            projection=projection,
        )

    if gain <= 0:
        return out("achieved")

    adh = 1.0 if inp.adherence is None else 1 / (0.75 + 0.25 * inp.adherence)
    row = None if placeholder else trajectories.nearest(inp.time_class, inp.current_rating, gain)
    if row is not None and row.players >= MIN_ROW_PLAYERS:
        fb, players = base_cdf(row, gain, inp.games_per_week)
        basis.sample_players = players
        r156 = fb(HORIZON_WEEKS * 10)
        t_half = _inverse(fb, r156 / 2, HORIZON_WEEKS * 10) if r156 > 0 else None
        scale = 1.0
        if trend is not None and t_half:
            v0 = r156 * gain / t_half
            lam = min(0.7, trend[2] / (trend[2] + 50))
            v = (1 - lam) * v0 + lam * trend[0]
            scale = 3.0 if v <= 0 else min(3.0, max(0.5, v0 / v))
        scale *= adh
        return out(_status(inp), lambda t: fb(t / scale))

    if trend is not None and inp.user_games >= LOW_GAMES:
        slope, se, _ = trend
        v = slope / adh

        def ft(t: float) -> float:
            if t <= 0:
                return 0.0
            return _phi((v * t - gain) / (se * t + 40 + 8 * math.sqrt(t)))

        return out(_status(inp), ft)

    return out("insufficient")


def _projection(inp: ForecastInput, f: Cdf, w80: int | None) -> list[ForecastPointOut]:
    gain = inp.target_rating - inp.current_rating
    horizon = min(HORIZON_WEEKS, max(4, w80 or HORIZON_WEEKS))
    end = max(f(HORIZON_WEEKS), 1e-6)

    def slope(q: float) -> float:
        weeks = _inverse(f, q)
        if weeks is not None:
            return gain / weeks
        return gain / HORIZON_WEEKS * min(1.0, end / q)

    def line(v: float, week: int) -> float:
        # После цели рост замедляется вчетверо: выборка не говорит, что бывает дальше.
        value = inp.current_rating + v * week
        if value > inp.target_rating:
            value = inp.target_rating + (value - inp.target_rating) * AFTER_TARGET
        return value

    lo, mid, hi = slope(0.9), slope(0.5), slope(0.1)
    points = []
    for week in range(0, horizon + 1):
        noise = Z80 * 10 * math.sqrt(week)
        p50 = line(mid, week)
        points.append(
            ForecastPointOut(
                date=inp.today + timedelta(weeks=week),
                p10=round(min(p50, line(lo, week) - noise), 1),
                p50=round(min(MAX_RATING, p50), 1),
                p90=round(min(MAX_RATING, max(p50, line(hi, week) + noise)), 1),
            )
        )
    return points
