"""Сборка эталонов (`python -m app.coach.norms build`): БД эталонов → `norms.json` и
`trajectories.json` в формате SPEC (парсер — `app/coach/norms_data.py`). В файлы попадают
только агрегаты: ни ников, ни партий.

**Группы.** Центры 1500…2200 через 100 (`PRIORITY_BANDS`; остальные пока не собираются),
в группу — партии с рейтингом игрока в момент партии в [центр − 100, центр + 100]; группы
перекрываются. Группа попадает в файл, если в ней
не меньше `MIN_BAND_PLAYERS` игроков; метрика — если у неё не меньше `MIN_METRIC_PLAYERS`.

**Квартили.** Метрика игрока — по его партиям группы той же функцией, что у пользователя
(`app.coach.metrics`). Но у игрока выборки ≤ 5 партий, а у пользователя — десятки: разброс
сырых значений по 5 партиям шире разброса «настоящего уровня», и пользователь со средними
показателями выглядел бы ровнее группы. Поэтому значения сжимаются к среднему группы
(эмпирический Байес): шум игрока σ²ᵢ = s² / Mᵢ (s² — дисперсия на единицу знаменателя,
`unit_variance`; Mᵢ — его знаменатель), межигровая дисперсия B = max(V − mean σ²ᵢ, 5 % V),
значение → μ + √(B / (B + σ²ᵢ)) · (vᵢ − μ) (корень сохраняет разброс ≈ B, а не сжимает
его вдвое, как апостериорное среднее). Квартили — по сжатым значениям.

**Траектории.** По месячным архивам тех же игроков (через `trajectory_stride` месяцев,
не старше 3 лет): старт — первый наблюдённый месяц в каждой группе (рейтинг в первой партии
месяца), цель — старт + прирост; время — до первого месяца, где рейтинг (в первой или последней
партии) не ниже цели. Доли «дошли за 52/104/156 недель» — по Каплану — Мейеру (наблюдение
обрывается последним загруженным месяцем), недели — квартили среди дошедших (меньше
`MIN_REACHED` — null). Активность — партий в неделю в наблюдённые месяцы (месяц без партий
виден по списку архивов как 0). Выборка — игроки, активные сейчас: тех, кто бросил, в ней
нет, поэтому доли — скорее оптимистичная оценка.
"""

import json
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.coach.metrics import GameAgg, MetricSpec, all_specs, load_game_aggs
from app.coach.norms import (
    BAND_HALF_WIDTH,
    NORM_TIME_CLASSES,
    PRIORITY_BANDS,
    TARGETS,
    nearest_center,
)
from app.coach.norms.db import service_user
from app.coach.norms_data import DATA_DIR, parse_norms, parse_trajectories
from app.db.models import GameSource
from app.review.motifs.base import MotifType
from app.stats.queries import user_games

log = structlog.get_logger(__name__)

MIN_BAND_PLAYERS = 15
MIN_METRIC_PLAYERS = 12
MIN_BETWEEN_SHARE = 0.05
MIN_MULTI_PLAYERS = 5
GAINS: tuple[int, ...] = (100, 200, 300, 400, 500, 600)
HORIZONS_W: tuple[int, ...] = (52, 104, 156)
MIN_TRAJECTORY_PLAYERS = 10
MIN_REACHED = 5
WEEKS_PER_MONTH = 365.25 / 12 / 7
# Подгруппы активности: партий в неделю [lo, hi).
ACTIVITY: tuple[tuple[float, float], ...] = ((0, 2), (2, 5), (5, 10), (10, 1000))


# --- Квартили группы --------------------------------------------------------------------------


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """Линейная интерполяция между порядковыми статистиками (как numpy по умолчанию)."""
    pos = (len(sorted_values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def unit_variance(
    players: Sequence[Sequence[tuple[float, float]]], mu: float, *, proportion: bool
) -> float:
    """Дисперсия шума на единицу знаменателя. По разбросу партий внутри игроков с ≥ 2
    партиями (поправка kᵢ/(kᵢ − 1)), если таких игроков не меньше `MIN_MULTI_PLAYERS`; иначе
    у долей (`proportion`: c ≤ m — ходы класса, партии с исходом) — биномиальная μ(1 − μ),
    у остального — 0 (без сжатия: оценить шум не по чему)."""
    multi = [p for p in players if len(p) >= 2]
    if len(multi) >= MIN_MULTI_PLAYERS:
        resid = 0.0
        for parts in multi:
            k = len(parts)
            v = sum(c for c, _ in parts) / sum(m for _, m in parts)
            resid += k / (k - 1) * sum((c - v * m) ** 2 for c, m in parts)
        return resid / sum(m for p in multi for _, m in p)
    return mu * (1 - mu) if proportion else 0.0


def shrunk_values(
    per_player: Sequence[Sequence[tuple[float, float]]], scale: float, *, proportion: bool = False
) -> list[float]:
    """Значения игроков (Σc/Σm × scale), сжатые к среднему группы (см. модуль)."""
    players = [parts for parts in per_player if parts and sum(m for _, m in parts) > 0]
    if not players:
        return []
    totals = [(sum(c for c, _ in p), sum(m for _, m in p)) for p in players]
    values = [c / m for c, m in totals]
    if len(values) < 2:
        return [v * scale for v in values]
    mu = sum(c for c, _ in totals) / sum(m for _, m in totals)
    unit_var = unit_variance(players, mu, proportion=proportion)
    spread = statistics.pvariance(values)
    noise = [unit_var / m for _, m in totals]
    between = max(spread - statistics.fmean(noise), MIN_BETWEEN_SHARE * spread)
    if between <= 0:
        return [mu * scale for _ in values]
    return [
        (mu + math.sqrt(between / (between + n)) * (v - mu)) * scale
        for v, n in zip(values, noise, strict=True)
    ]


def band_metric(
    players: Mapping[str, Sequence[GameAgg]], spec: MetricSpec
) -> dict[str, float | int] | None:
    per_player = [
        [p for g in games if (p := spec.part(g)) is not None and p[1] > 0]
        for games in players.values()
    ]
    per_player = [p for p in per_player if p]
    if len(per_player) < MIN_METRIC_PLAYERS:
        return None
    # Доли (ходов класса, партий с исходом) — у метрик с масштабом 100, кроме точности.
    values = sorted(shrunk_values(per_player, spec.scale, proportion=spec.scale == 100.0))
    n = len(per_player) if spec.per_game else round(sum(m for p in per_player for _, m in p))
    return {
        "p25": round(_quantile(values, 0.25), 3),
        "p50": round(_quantile(values, 0.5), 3),
        "p75": round(_quantile(values, 0.75), 3),
        "n": n,
    }


@dataclass(frozen=True, slots=True)
class SampleGame:
    player: str
    rating: int
    agg: GameAgg


def build_bands(games: Sequence[SampleGame], specs: Sequence[MetricSpec]) -> list[dict[str, Any]]:
    """Группы одного контроля (только с достаточным числом игроков)."""
    bands = []
    for center in PRIORITY_BANDS:
        lo, hi = center - BAND_HALF_WIDTH, center + BAND_HALF_WIDTH
        players: dict[str, list[GameAgg]] = defaultdict(list)
        for g in games:
            if lo <= g.rating <= hi:
                players[g.player].append(g.agg)
        if len(players) < MIN_BAND_PLAYERS:
            continue
        metrics = {s.key: q for s in specs if (q := band_metric(players, s)) is not None}
        bands.append(
            {
                "center": center,
                "lo": lo,
                "hi": hi,
                "players": len(players),
                "games": sum(len(v) for v in players.values()),
                "moves": sum(g.moves for v in players.values() for g in v),
                "metrics": metrics,
            }
        )
    return bands


# --- Траектории -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MonthPoint:
    month: date
    games: int
    first_rating: int | None
    last_rating: int | None


def _weeks(a: date, b: date) -> float:
    return (b - a).days / 7


def _month_end(month: date) -> date:
    nxt = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


@dataclass(frozen=True, slots=True)
class Start:
    """Старт траектории: группа, рейтинг, время до цели по приростам (None — не дошёл),
    сколько недель наблюдался после старта и партий в неделю."""

    center: int
    rating: int
    reached: Mapping[int, float | None]
    observed_weeks: float
    games_per_week: float


def _first_reach(points: Sequence[MonthPoint], goal: int) -> date | None:
    """Первый месяц, где рейтинг дошёл до `goal`: в стартовом месяце — по последней партии
    (первая и есть старт), дальше — по первой или последней."""
    for i, q in enumerate(points):
        ratings = (q.last_rating,) if i == 0 else (q.first_rating, q.last_rating)
        if any(r is not None and r >= goal for r in ratings):
            return q.month
    return None


def trajectory_starts(points: Sequence[MonthPoint], gains: Sequence[int] = GAINS) -> list[Start]:
    """Старты игрока в одном контроле. `points` — наблюдённые месяцы по возрастанию (включая
    месяцы без партий: `games = 0`, рейтинги None)."""
    rated = [p for p in points if p.games > 0 and p.first_rating is not None]
    if len(rated) < 2:
        return []
    end = _month_end(points[-1].month)
    starts: list[Start] = []
    seen: set[int] = set()
    for i, p in enumerate(rated):
        assert p.first_rating is not None
        center = nearest_center(p.first_rating)
        if center is None or center in seen:
            continue
        seen.add(center)
        t0 = p.month
        after = rated[i:]
        reached: dict[int, float | None] = {}
        for gain in gains:
            hit = _first_reach(after, p.first_rating + gain)
            reached[gain] = None if hit is None else max(_weeks(t0, _month_end(hit)), 1.0)
        observed = [q for q in points if q.month >= t0]
        weeks = max(_weeks(t0, end), 1.0)
        per_month = statistics.fmean(q.games for q in observed)
        starts.append(
            Start(
                center=center,
                rating=p.first_rating,
                reached=reached,
                observed_weeks=weeks,
                games_per_week=per_month / WEEKS_PER_MONTH,
            )
        )
    return starts


def kaplan_meier(events: Sequence[tuple[float, bool]], horizon: float) -> float:
    """Доля «событие произошло к `horizon`»: (время, произошло ли) — иначе цензура."""
    survival = 1.0
    times = sorted({t for t, hit in events if hit and t <= horizon})
    for t in times:
        at_risk = sum(1 for u, _ in events if u >= t)
        hits = sum(1 for u, hit in events if hit and u == t)
        if at_risk:
            survival *= 1 - hits / at_risk
    return 1 - survival


def _events(starts: Sequence[Start], gain: int) -> list[tuple[float, bool]]:
    events = []
    for s in starts:
        weeks = s.reached[gain]
        events.append((weeks, True) if weeks is not None else (s.observed_weeks, False))
    return events


def _weeks_quartiles(starts: Sequence[Start], gain: int) -> list[float | None]:
    weeks = sorted(w for s in starts if (w := s.reached[gain]) is not None)
    if len(weeks) < MIN_REACHED:
        return [None, None, None]
    return [round(_quantile(weeks, q), 1) for q in (0.25, 0.5, 0.75)]


def trajectory_rows(starts: Sequence[Start]) -> list[dict[str, Any]]:
    rows = []
    for center in PRIORITY_BANDS:
        group = [s for s in starts if s.center == center]
        if len(group) < MIN_TRAJECTORY_PLAYERS:
            continue
        for gain in GAINS:
            events = _events(group, gain)
            p25, p50, p75 = _weeks_quartiles(group, gain)
            activity = []
            for lo, hi in ACTIVITY:
                sub = [s for s in group if lo <= s.games_per_week < hi]
                if len(sub) < MIN_REACHED:
                    continue
                activity.append(
                    {
                        "games_per_week_lo": lo,
                        "games_per_week_hi": hi,
                        "players": len(sub),
                        "reached_104w": round(kaplan_meier(_events(sub, gain), 104), 3),
                        "weeks_p50": _weeks_quartiles(sub, gain)[1],
                    }
                )
            rows.append(
                {
                    "from_center": center,
                    "gain": gain,
                    "players": len(group),
                    **{f"reached_{h}w": round(kaplan_meier(events, h), 3) for h in HORIZONS_W},
                    "weeks_p25": p25,
                    "weeks_p50": p50,
                    "weeks_p75": p75,
                    "activity": activity,
                }
            )
    return rows


def observed_points(
    months: Mapping[date, tuple[int, int | None, int | None]],
    fetched: Iterable[date],
    archives: Iterable[date],
    today: date,
) -> list[MonthPoint]:
    """Наблюдённые месяцы игрока в контроле: загруженные (с партиями в контроле или без)
    и месяцы без партий вовсе (их нет в списке архивов) в пределах окна наблюдения."""
    fetched_set, archive_set = set(fetched), set(archives)
    if not fetched_set:
        return []
    first = min(fetched_set)
    oldest = date(today.year - TARGETS.trajectory_months // 12, today.month, 1)
    first = max(first, oldest)
    result = []
    m = first
    current = today.replace(day=1)
    while m < current:
        if m in fetched_set:
            games, fr, lr = months.get(m, (0, None, None))
            result.append(MonthPoint(m, games, fr, lr))
        elif m not in archive_set:
            result.append(MonthPoint(m, 0, None, None))
        m = date(m.year + m.month // 12, m.month % 12 + 1, 1)
    return result


# --- IO ---------------------------------------------------------------------------------------


async def _sample_games(session: AsyncSession, tc: str) -> list[SampleGame]:
    user = await service_user(session)
    aggs = await load_game_aggs(session, user_games(user.id, GameSource.CHESSCOM, tc))  # type: ignore[arg-type]
    rows = await session.execute(
        text("SELECT game_id, username, rating FROM norms_samples WHERE time_class = :tc"),
        {"tc": tc},
    )
    meta = {row.game_id: (row.username, int(row.rating)) for row in rows}
    return [
        SampleGame(player=meta[a.game_id][0], rating=meta[a.game_id][1], agg=a)
        for a in aggs
        if a.game_id in meta
    ]


async def _starts(session: AsyncSession, tc: str, today: date) -> list[Start]:
    players = await session.execute(
        text(
            "SELECT p.username, p.archives FROM norms_players p WHERE p.status = 'sampled' "
            "AND p.archives IS NOT NULL"
        )
    )
    fetched: dict[str, list[date]] = defaultdict(list)
    for row in await session.execute(text("SELECT username, month FROM norms_fetched")):
        fetched[row.username].append(row.month)
    months: dict[str, dict[date, tuple[int, int | None, int | None]]] = defaultdict(dict)
    for row in await session.execute(
        text(
            "SELECT username, month, games, first_rating, last_rating FROM norms_months "
            "WHERE time_class = :tc"
        ),
        {"tc": tc},
    ):
        months[row.username][row.month] = (row.games, row.first_rating, row.last_rating)
    starts: list[Start] = []
    for row in players:
        if not months.get(row.username):
            continue
        points = observed_points(months[row.username], fetched[row.username], row.archives, today)
        starts += trajectory_starts(points)
    return starts


async def build(session: AsyncSession, *, out_dir: str | None = None) -> tuple[Path, Path]:
    now = datetime.now(UTC)
    specs = all_specs(m.value for m in MotifType)
    norms_tc: dict[str, Any] = {}
    traj_tc: dict[str, Any] = {}
    for tc in NORM_TIME_CLASSES:
        bands = build_bands(await _sample_games(session, tc), specs)
        norms_tc[tc] = {"bands": bands}
        rows = trajectory_rows(await _starts(session, tc, now.date()))
        traj_tc[tc] = {"rows": rows}
        log.info(
            "norms.build.time_class",
            time_class=tc,
            bands=[(b["center"], b["players"], b["games"]) for b in bands],
            trajectory_rows=len(rows),
        )
    version = now.strftime("%Y-%m-%d")
    norms = {"version": version, "source": "chesscom", "built_at": now.isoformat(),
             "time_classes": norms_tc}  # fmt: skip
    trajectories = {"version": version, "source": "chesscom", "built_at": now.isoformat(),
                    "time_classes": traj_tc}  # fmt: skip
    # Проверка формата тем же парсером, что читает приложение.
    parse_norms(norms)
    parse_trajectories(trajectories)
    out = Path(out_dir) if out_dir else DATA_DIR
    out.mkdir(parents=True, exist_ok=True)
    norms_path, traj_path = out / "norms.json", out / "trajectories.json"
    norms_path.write_text(json.dumps(norms, ensure_ascii=False, indent=1) + "\n")
    traj_path.write_text(json.dumps(trajectories, ensure_ascii=False, indent=1) + "\n")
    return norms_path, traj_path
