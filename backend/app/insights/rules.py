"""Слабые места (SPEC «Сессия 16», 16.1): агрегаты по партиям → выводы.

Чистая логика без I/O: агрегаты считает SQL (`queries.py`), здесь решается, что из них —
слабое место, насколько оно важно и чем его тренировать. Все пороги — в `Thresholds`.

Каждый вывод сравнивает показатель пользователя с его же базой (другие мотивы, фазы, ходы
не в цейтноте, другие дебюты тем же цветом, ожидание по оценке позиции): чужих данных
нет, а «вы ошибаетесь в эндшпиле чаще, чем в миттельшпиле» правдиво без них. Чтобы
не выдавать шум за слабость, у каждого вида два условия: заметная разница (`min_lift` /
`min_gap`) и достаточная уверенность — z-статистика разницы долей не ниже `min_z`.

Важность: `score` 0…100 = 60 · min(z, z_cap) / z_cap + 40 · min(отн. разница, 1);
`severity` — high (z ≥ `high_z` и отн. разница ≥ `high_lift` − 1), medium (z ≥ `medium_z`),
иначе low. Порядок — по важности, затем по `score`.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from app.db.models import Color
from app.review.types import Phase

Kind = Literal["motif", "phase", "time", "opening", "conversion"]
Severity = Literal["high", "medium", "low"]
TrainKind = Literal["puzzles", "endgames", "course", "play"]

SEVERITY_ORDER: dict[Severity, int] = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True, slots=True)
class Thresholds:
    # Меньше разобранных партий — выводов нет (SPEC: `min_games`).
    min_games: int = 10
    # Общие условия значимости.
    min_z: float = 1.65
    medium_z: float = 2.3
    high_z: float = 3.0
    high_lift: float = 1.5
    z_cap: float = 5.0
    # Мотивы: возможностей (лучший ход с мотивом) и упущенных — не меньше; доля упущенных
    # больше средней по остальным мотивам хотя бы в `min_lift` раз.
    motif_min_opportunities: int = 8
    motif_min_missed: int = 4
    motif_min_lift: float = 1.3
    # Фазы и время считаются по ходам из неясных позиций (win% до хода в этих границах):
    # в решённой позиции ошибиться «на класс» почти нельзя, а таких ходов много в эндшпиле
    # и в цейтноте — без отсечения они разбавляли бы ошибки.
    contested_min: float = 10.0
    contested_max: float = 90.0
    # Фазы: ходов фазы и ошибок в ней — не меньше; ошибок на ход больше, чем в остальных.
    phase_min_moves: int = 150
    phase_min_errors: int = 8
    phase_min_lift: float = 1.3
    # Время: ходов в цейтноте / быстрых ходов и ошибок среди них — не меньше.
    time_min_moves: int = 30
    time_min_errors: int = 5
    time_min_lift: float = 1.4
    # Дебюты (семейство тем же цветом): партий не меньше; очков (%) меньше, чем в остальных
    # дебютах этим цветом, хотя бы на `opening_min_gap` пунктов.
    opening_min_games: int = 10
    opening_min_gap: float = 12.0
    opening_max_findings: int = 3
    # Реализация: партий с выигранной позицией (win% ≥ `conversion_win`) не меньше; потеряно
    # очков больше ожидаемого по win% хотя бы на `conversion_min_gap` пунктов.
    conversion_win: float = 80.0
    conversion_min_games: int = 8
    conversion_min_gap: float = 10.0
    # Мотивов-выводов не больше.
    motif_max_findings: int = 4


THRESHOLDS = Thresholds()


# --- Агрегаты (вход) -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MotifAgg:
    """Мотив лучшего хода: сколько раз был (сыгран лучший ход с ним или упущен) и сколько
    раз упущен ошибкой (mistake / blunder / miss)."""

    motif: str
    opportunities: int
    missed: int


@dataclass(frozen=True, slots=True)
class PhaseAgg:
    """Ходы пользователя в фазе и ошибки среди них (mistake / blunder)."""

    phase: Phase
    moves: int
    errors: int


@dataclass(frozen=True, slots=True)
class TimeAgg:
    """Ходы с известным временем: в цейтноте и вне его; вне цейтнота — быстрые
    (`review/clock.py`) и остальные. Ошибки — mistake / blunder."""

    trouble_moves: int
    trouble_errors: int
    calm_moves: int
    calm_errors: int
    fast_moves: int
    fast_errors: int


@dataclass(frozen=True, slots=True)
class OpeningAgg:
    """Семейство дебюта (имя до двоеточия) за один цвет: партии и набранные очки."""

    color: Color
    family: str
    eco: str | None
    games: int
    points: float


@dataclass(frozen=True, slots=True)
class ConversionAgg:
    """Партии, где после хода пользователя была выигранная позиция: набранные очки и
    ожидание по win% в момент, когда позиция впервые стала выигранной."""

    games: int
    points: float
    expected_points: float
    not_won: int


@dataclass(frozen=True, slots=True)
class Aggregates:
    analyzed_games: int
    motifs: Sequence[MotifAgg] = ()
    phases: Sequence[PhaseAgg] = ()
    time: TimeAgg | None = None
    openings: Sequence[OpeningAgg] = ()
    conversion: ConversionAgg | None = None


# --- Выводы (выход) --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Stats:
    """`value` против `baseline` (в процентах), `count` из `total` — то, на чём вывод держится."""

    value: float
    baseline: float
    count: int
    total: int


@dataclass(frozen=True, slots=True)
class Train:
    kind: TrainKind
    theme: str | None = None
    phase: Phase | None = None
    eco: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    kind: Kind
    key: str
    severity: Severity
    score: float
    stats: Stats
    train: Train | None = field(default=None)

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.key}"


# --- Статистика -------------------------------------------------------------------------------


def two_proportion_z(hits: float, n: int, base_hits: float, base_n: int) -> float:
    """z разницы долей hits/n и base_hits/base_n (объединённая дисперсия); 0 — нет данных.
    `hits` может быть дробным — очки (ничья ½) ведут себя как доля с не большей дисперсией."""
    if n <= 0 or base_n <= 0:
        return 0.0
    pooled = (hits + base_hits) / (n + base_n)
    var = pooled * (1 - pooled) * (1 / n + 1 / base_n)
    if var <= 0:
        return 0.0
    return (hits / n - base_hits / base_n) / math.sqrt(var)


def _grade(z: float, lift: float, t: Thresholds) -> tuple[Severity, float]:
    """Важность по уверенности `z` и относительной разнице `lift` (1.0 — нет разницы)."""
    rel = max(0.0, lift - 1)
    score = 60 * min(max(z, 0.0), t.z_cap) / t.z_cap + 40 * min(rel, 1.0)
    if z >= t.high_z and lift >= t.high_lift:
        severity: Severity = "high"
    elif z >= t.medium_z:
        severity = "medium"
    else:
        severity = "low"
    return severity, round(score, 1)


def _pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


# --- Правила по видам -------------------------------------------------------------------------


def motif_findings(motifs: Sequence[MotifAgg], t: Thresholds = THRESHOLDS) -> list[Finding]:
    """Мотивы, которые пользователь упускает чаще, чем остальные: доля упущенных возможностей
    против той же доли по всем остальным мотивам."""
    total_opp = sum(m.opportunities for m in motifs)
    total_missed = sum(m.missed for m in motifs)
    found: list[Finding] = []
    for m in motifs:
        if m.opportunities < t.motif_min_opportunities or m.missed < t.motif_min_missed:
            continue
        base_n, base_hits = total_opp - m.opportunities, total_missed - m.missed
        if base_n <= 0:
            continue
        rate, base_rate = m.missed / m.opportunities, base_hits / base_n
        lift = rate / base_rate if base_rate > 0 else math.inf
        z = two_proportion_z(m.missed, m.opportunities, base_hits, base_n)
        if lift < t.motif_min_lift or z < t.min_z:
            continue
        severity, score = _grade(z, lift, t)
        found.append(
            Finding(
                kind="motif",
                key=m.motif,
                severity=severity,
                score=score,
                stats=Stats(
                    _pct(m.missed, m.opportunities),
                    _pct(base_hits, base_n),
                    m.missed,
                    m.opportunities,
                ),
                train=Train(kind="puzzles", theme=m.motif),
            )
        )
    return _top(found, t.motif_max_findings)


def phase_findings(phases: Sequence[PhaseAgg], t: Thresholds = THRESHOLDS) -> list[Finding]:
    """Фаза, где ошибок на ход больше, чем в других фазах. Дебют почти весь из книжных
    ходов и ошибок в нём всегда мало, поэтому миттельшпиль и эндшпиль сравниваются только
    друг с другом, а дебют — с ними обоими (вывод о дебюте — только если там хуже)."""
    by_phase = {p.phase: p for p in phases}
    found: list[Finding] = []
    for p in phases:
        if p.moves < t.phase_min_moves or p.errors < t.phase_min_errors:
            continue
        others = [
            o
            for o in by_phase.values()
            if o.phase != p.phase and (p.phase == Phase.OPENING or o.phase != Phase.OPENING)
        ]
        base_n, base_hits = sum(o.moves for o in others), sum(o.errors for o in others)
        if base_n < t.phase_min_moves or base_hits <= 0:
            continue
        lift = (p.errors / p.moves) / (base_hits / base_n)
        z = two_proportion_z(p.errors, p.moves, base_hits, base_n)
        if lift < t.phase_min_lift or z < t.min_z:
            continue
        severity, score = _grade(z, lift, t)
        train = (
            Train(kind="endgames")
            if p.phase == Phase.ENDGAME
            else Train(kind="puzzles", phase=p.phase)
        )
        found.append(
            Finding(
                kind="phase",
                key=p.phase.value,
                severity=severity,
                score=score,
                stats=Stats(_pct(p.errors, p.moves), _pct(base_hits, base_n), p.errors, p.moves),
                train=train,
            )
        )
    return found


def time_findings(time: TimeAgg | None, t: Thresholds = THRESHOLDS) -> list[Finding]:
    """`trouble` — в цейтноте ошибок на ход больше, чем при нормальном времени;
    `hasty` — быстрые ходы вне цейтнота ошибочнее остальных ходов вне цейтнота."""
    if time is None:
        return []
    found: list[Finding] = []
    slow_moves = time.calm_moves - time.fast_moves
    slow_errors = time.calm_errors - time.fast_errors
    cases = (
        ("trouble", time.trouble_moves, time.trouble_errors, time.calm_moves, time.calm_errors),
        ("hasty", time.fast_moves, time.fast_errors, slow_moves, slow_errors),
    )
    for key, n, hits, base_n, base_hits in cases:
        if n < t.time_min_moves or hits < t.time_min_errors or base_n <= 0 or base_hits <= 0:
            continue
        lift = (hits / n) / (base_hits / base_n)
        z = two_proportion_z(hits, n, base_hits, base_n)
        if lift < t.time_min_lift or z < t.min_z:
            continue
        severity, score = _grade(z, lift, t)
        found.append(
            Finding(
                kind="time",
                key=key,
                severity=severity,
                score=score,
                stats=Stats(_pct(hits, n), _pct(base_hits, base_n), hits, n),
                # Цейтнот — решать быстрее (забег на время, ссылку строит экран); поспешность —
                # считать варианты спокойно (пазлы по темам).
                train=Train(kind="puzzles"),
            )
        )
    return found


def opening_findings(openings: Sequence[OpeningAgg], t: Thresholds = THRESHOLDS) -> list[Finding]:
    """Семейства дебютов, где очков заметно меньше, чем в остальных дебютах тем же цветом.
    Ключ — `"{цвет}:{семейство}"`. Очки — победа 1, ничья ½; z — по долям очков."""
    found: list[Finding] = []
    for color in Color:
        mine = [o for o in openings if o.color == color]
        games = sum(o.games for o in mine)
        points = sum(o.points for o in mine)
        for o in mine:
            if o.games < t.opening_min_games:
                continue
            base_n, base_pts = games - o.games, points - o.points
            if base_n < t.opening_min_games:
                continue
            value, base = 100 * o.points / o.games, 100 * base_pts / base_n
            if base - value < t.opening_min_gap:
                continue
            # «Промах» — недобранное очко: доля недобора против остальных дебютов.
            z = two_proportion_z(o.games - o.points, o.games, base_n - base_pts, base_n)
            if z < t.min_z:
                continue
            lost, base_lost = 1 - o.points / o.games, 1 - base_pts / base_n
            lift = lost / base_lost if base_lost > 0 else math.inf
            severity, score = _grade(z, lift, t)
            found.append(
                Finding(
                    kind="opening",
                    key=f"{color.value}:{o.family}",
                    severity=severity,
                    score=score,
                    stats=Stats(round(value, 1), round(base, 1), o.games, games),
                    train=Train(kind="course", eco=o.eco),
                )
            )
    return _top(found, t.opening_max_findings)


def conversion_findings(conv: ConversionAgg | None, t: Thresholds = THRESHOLDS) -> list[Finding]:
    """Выигранные позиции, которые не превращаются в победу: недобрано очков против
    ожидания по win% в момент, когда позиция стала выигранной."""
    if conv is None or conv.games < t.conversion_min_games:
        return []
    lost = conv.games - conv.points
    expected_lost = conv.games - conv.expected_points
    value, base = 100 * lost / conv.games, 100 * expected_lost / conv.games
    if value - base < t.conversion_min_gap:
        return []
    # Ожидание — не выборка, а модель: одновыборочный z по биномиальной дисперсии ожидания.
    p0 = expected_lost / conv.games
    z = (lost / conv.games - p0) / math.sqrt(p0 * (1 - p0) / conv.games) if 0 < p0 < 1 else 0.0
    if z < t.min_z:
        return []
    severity, score = _grade(z, value / base if base > 0 else math.inf, t)
    return [
        Finding(
            kind="conversion",
            key="winning",
            severity=severity,
            score=score,
            stats=Stats(round(value, 1), round(base, 1), conv.not_won, conv.games),
            train=Train(kind="endgames"),
        )
    ]


def _top(findings: list[Finding], limit: int) -> list[Finding]:
    return sorted(findings, key=_order)[:limit]


def _order(f: Finding) -> tuple[int, float, str]:
    return (SEVERITY_ORDER[f.severity], -f.score, f.id)


def find_weaknesses(agg: Aggregates, t: Thresholds = THRESHOLDS) -> list[Finding]:
    """Все выводы по важности. Меньше `min_games` разобранных партий — ничего."""
    if agg.analyzed_games < t.min_games:
        return []
    findings = [
        *motif_findings(agg.motifs, t),
        *phase_findings(agg.phases, t),
        *time_findings(agg.time, t),
        *opening_findings(agg.openings, t),
        *conversion_findings(agg.conversion, t),
    ]
    return sorted(findings, key=_order)
