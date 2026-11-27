"""Эталоны рейтинговых групп и траектории рейтинга (общий контракт 17.1 → 17.2).

Файлы `app/coach/data/norms.json` и `trajectories.json` собирает 17.1 (выборка игроков
Chess.com, анализ нашим же конвейером); в репозитории — только агрегаты, без ников и партий.
До сборки лежат заглушки `"version": "placeholder"` с пустыми `time_classes`: диагностика и
прогноз тогда отвечают `insufficient`. Формат — SPEC «Сессия 17».
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True, slots=True)
class Quartiles:
    p25: float
    p50: float
    p75: float
    # Игроков (для метрик по партиям) или ходов (для «на 100 ходов» и мотивов) в основе.
    n: int


@dataclass(frozen=True, slots=True)
class Band:
    center: int
    lo: int
    hi: int
    players: int
    games: int
    moves: int
    # Ключи — `MetricKey` и `motif:<тип мотива>`.
    metrics: dict[str, Quartiles]


@dataclass(frozen=True, slots=True)
class Norms:
    version: str
    # time_class → группы по возрастанию `center`.
    bands: dict[str, tuple[Band, ...]]

    def nearest(self, time_class: str, rating: int) -> Band | None:
        bands = self.bands.get(time_class, ())
        return min(bands, key=lambda b: abs(b.center - rating), default=None)


@dataclass(frozen=True, slots=True)
class Activity:
    """Подгруппа по активности: партий в неделю в [lo, hi)."""

    games_per_week_lo: float
    games_per_week_hi: float
    players: int
    reached_104w: float
    weeks_p50: float | None


@dataclass(frozen=True, slots=True)
class TrajectoryRow:
    """Игроки, бывшие в группе `from_center`: доля поднявшихся на `gain` за 1–3 года и за
    сколько недель (квартили среди поднявшихся)."""

    from_center: int
    gain: int
    players: int
    reached_52w: float
    reached_104w: float
    reached_156w: float
    weeks_p25: float | None
    weeks_p50: float | None
    weeks_p75: float | None
    activity: tuple[Activity, ...]


@dataclass(frozen=True, slots=True)
class Trajectories:
    version: str
    rows: dict[str, tuple[TrajectoryRow, ...]]

    def nearest(self, time_class: str, from_rating: int, gain: int) -> TrajectoryRow | None:
        rows = self.rows.get(time_class, ())
        return min(
            rows,
            key=lambda r: (abs(r.from_center - from_rating), abs(r.gain - gain)),
            default=None,
        )


def _quartiles(raw: dict[str, Any]) -> Quartiles:
    return Quartiles(
        p25=float(raw["p25"]), p50=float(raw["p50"]), p75=float(raw["p75"]), n=int(raw["n"])
    )


def parse_norms(raw: dict[str, Any]) -> Norms:
    bands: dict[str, tuple[Band, ...]] = {}
    for time_class, tc in raw.get("time_classes", {}).items():
        items = [
            Band(
                center=int(b["center"]),
                lo=int(b["lo"]),
                hi=int(b["hi"]),
                players=int(b["players"]),
                games=int(b["games"]),
                moves=int(b["moves"]),
                metrics={k: _quartiles(v) for k, v in b["metrics"].items()},
            )
            for b in tc["bands"]
        ]
        bands[time_class] = tuple(sorted(items, key=lambda b: b.center))
    return Norms(version=str(raw["version"]), bands=bands)


def _opt(value: Any) -> float | None:
    return None if value is None else float(value)


def parse_trajectories(raw: dict[str, Any]) -> Trajectories:
    rows: dict[str, tuple[TrajectoryRow, ...]] = {}
    for time_class, tc in raw.get("time_classes", {}).items():
        rows[time_class] = tuple(
            TrajectoryRow(
                from_center=int(r["from_center"]),
                gain=int(r["gain"]),
                players=int(r["players"]),
                reached_52w=float(r["reached_52w"]),
                reached_104w=float(r["reached_104w"]),
                reached_156w=float(r["reached_156w"]),
                weeks_p25=_opt(r.get("weeks_p25")),
                weeks_p50=_opt(r.get("weeks_p50")),
                weeks_p75=_opt(r.get("weeks_p75")),
                activity=tuple(
                    Activity(
                        games_per_week_lo=float(a["games_per_week_lo"]),
                        games_per_week_hi=float(a["games_per_week_hi"]),
                        players=int(a["players"]),
                        reached_104w=float(a["reached_104w"]),
                        weeks_p50=_opt(a.get("weeks_p50")),
                    )
                    for a in r.get("activity", [])
                ),
            )
            for r in tc["rows"]
        )
    return Trajectories(version=str(raw["version"]), rows=rows)


@cache
def load_norms() -> Norms:
    return parse_norms(json.loads((DATA_DIR / "norms.json").read_text()))


@cache
def load_trajectories() -> Trajectories:
    return parse_trajectories(json.loads((DATA_DIR / "trajectories.json").read_text()))
