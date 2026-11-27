"""Недельный план тренера (SPEC «Сессия 17», 17.2): чистая детерминированная функция
«слабые стороны + цель + доступные тренировки → задания по дням».

Правила (все числа — в `PlannerRules`):

1. **Учебные дни** — `days_per_week` дней с понедельника равномерно: день `i` — `⌊i·7/d⌋`
   (5 дней → пн, вт, ср, пт, сб; 3 → пн, ср, пт). План собирается «с сегодня»: прошедшие дни
   не планируются. Если в неделе от сегодня не осталось ни одного учебного дня, учебным
   становится сегодня — иначе новая цель в воскресенье ждала бы понедельника.
2. **Бюджет** — `minutes_per_day` на каждый учебный день; сумма норм дня попадает в ±10 %
   (кроме дня с партией, которая одна длиннее бюджета, — партию не разрезать).
3. **Распределение недели** по видам:
   - партия + разбор — не меньше 25 %: партий в неделю — наименьшее число, при котором
     «партия + разбор» занимают ≥ 25 % (хотя бы одна); разбор — по одному на партию, в тот же
     день, если влезает в бюджет дня, иначе в следующий учебный день;
   - тактика — не меньше 30 % при цели ≤ 2200 (выше — 20 %): пазлы без темы;
   - остальное — по слабым сторонам пропорционально `score`, до 3 главных (`focus`);
     слабая сторона без доступной тренировки (`train.available == 0`, нет курса по дебюту)
     времени не получает — её доля уходит в тактику (нет пазлов — в партии);
   - нет слабых сторон (диагностика `insufficient`) — остаток делится между тактикой и
     партиями поровну.
   Вид слабой стороны: мотив / фаза → пазлы с фильтром (`theme` / `phase`), эндшпиль и
   реализация → эндшпиль своих партий, цейтнот и поспешность → забег на время, дебют → курс.
4. **Уроки** — один на слабую сторону из `focus` (если у неё есть урок), непрочитанные первыми,
   по одному в учебный день начиная с первого; время урока берётся из бюджета дня.
5. **Нормы** — из минут: пазл 1,5 мин, забег 5, позиция эндшпиля 4, позиция курса 1, партия —
   по контролю цели, разбор 10, урок 8. Мелкие виды (пазлы, забег, эндшпиль, курс) делят
   остаток дня пропорционально недоплаченным минутам недели — так недельные доли сходятся
   к распределению, а дни остаются в бюджете.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, Protocol

from app.api.schemas_coach import GapOut, TaskKind, TaskUnit

TimeClassName = Literal["bullet", "blitz", "rapid", "daily"]
SMALL_KINDS: tuple[TaskKind, ...] = ("puzzles", "rush", "endgames", "course")
KIND_ORDER: tuple[TaskKind, ...] = (
    "lesson",
    "play",
    "review",
    "puzzles",
    "rush",
    "endgames",
    "course",
)
TIME_METRICS = frozenset({"time_trouble_share", "hasty_per_100"})


@dataclass(frozen=True, slots=True)
class PlannerRules:
    tactics_share: float = 0.30
    tactics_share_high: float = 0.20
    tactics_high_from: int = 2200
    play_share: float = 0.25
    max_focus: int = 3
    tolerance: float = 0.10
    # Мелкое задание короче — не ставится (остаток дня меньше — день и так в бюджете).
    min_task_minutes: float = 5.0
    # Минут на единицу нормы.
    unit_minutes: Mapping[str, float] = field(
        default_factory=lambda: {
            "puzzles": 1.5,
            "rush": 5.0,
            "endgames": 4.0,
            "course": 1.0,
            "review": 10.0,
            "lesson": 8.0,
        }
    )
    # Партия — по контролю цели (минут на партию вместе с ожиданием соперника).
    game_minutes: Mapping[str, float] = field(
        default_factory=lambda: {"bullet": 3.0, "blitz": 10.0, "rapid": 25.0, "daily": 15.0}
    )


RULES = PlannerRules()

UNITS: dict[TaskKind, TaskUnit] = {
    "puzzles": "puzzles",
    "rush": "runs",
    "endgames": "attempts",
    "course": "attempts",
    "play": "games",
    "review": "games",
    "lesson": "lessons",
}


@dataclass(frozen=True, slots=True)
class Availability:
    """Что есть для тренировок у пользователя (собирает `tasks.py`)."""

    # Пазлов всего (без фильтров) — для тактики и забега.
    puzzles: int
    # ECO → id готового курса пользователя (для слабости по дебюту).
    courses_by_eco: Mapping[str, str] = field(default_factory=dict)
    read_lessons: frozenset[str] = frozenset()
    # Рекомендуемый бот для партии (`/play`).
    bot_elo: int = 1200


@dataclass(frozen=True, slots=True)
class PlanGoal:
    time_class: TimeClassName
    target_rating: int
    minutes_per_day: int
    days_per_week: int


@dataclass(frozen=True, slots=True)
class TaskSpec:
    day: date
    position: int
    kind: TaskKind
    params: dict[str, str | int]
    target: int
    unit: TaskUnit
    minutes: int
    focus: str | None


@dataclass(frozen=True, slots=True)
class Allocation:
    kind: TaskKind
    minutes_per_week: int
    share: float
    focus: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WeekPlan:
    week_start: date
    study_days: tuple[date, ...]
    focus: tuple[str, ...]
    allocation: tuple[Allocation, ...]
    tasks: tuple[TaskSpec, ...]


@dataclass(frozen=True, slots=True)
class _Stream:
    """Мелкий вид занятий с параметрами: на сколько минут недели он претендует."""

    kind: TaskKind
    params: tuple[tuple[str, str | int], ...]
    focus: str | None
    minutes: float


def week_start_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def study_weekdays(days_per_week: int) -> tuple[int, ...]:
    d = max(1, min(7, days_per_week))
    return tuple(sorted({(i * 7) // d for i in range(d)}))


def study_days(week_start: date, days_per_week: int, from_day: date) -> tuple[date, ...]:
    days = tuple(
        week_start + timedelta(days=i)
        for i in study_weekdays(days_per_week)
        if week_start + timedelta(days=i) >= from_day
    )
    if not days and week_start <= from_day < week_start + timedelta(days=7):
        return (from_day,)
    return days


def focus_of(weaknesses: Sequence[GapOut], rules: PlannerRules = RULES) -> list[GapOut]:
    """Главные слабые стороны недели: по `score`, при равенстве — по виду и ключу."""
    return sorted(weaknesses, key=lambda g: (-g.score, g.kind, g.key))[: rules.max_focus]


def _weakness_stream(
    gap: GapOut, avail: Availability
) -> tuple[TaskKind, dict[str, str | int]] | None:
    """Чем тренировать слабую сторону; `None` — тренировки нет."""
    train = gap.train
    stream: tuple[TaskKind, dict[str, str | int]] | None = None
    if gap.key in TIME_METRICS:
        stream = ("rush", {}) if avail.puzzles > 0 else None
    elif train is None or train.available <= 0:
        stream = None
    elif train.kind == "puzzles":
        query = {"theme": train.query.theme, "phase": train.query.phase, "eco": train.query.eco}
        params: dict[str, str | int] = {k: v for k, v in query.items() if v}
        stream = ("puzzles", params) if avail.puzzles > 0 else None
    elif train.kind == "endgames":
        stream = ("endgames", {"tab": "mine"})
    elif train.kind == "course":
        course = avail.courses_by_eco.get(train.query.eco or "")
        stream = ("course", {"course_id": course}) if course else None
    elif train.kind == "play":
        stream = ("play", {})
    return stream


def _spread(count: int, days: Sequence[date]) -> list[date]:
    """`count` событий по дням равномерно (детерминированно)."""
    n = len(days)
    if n == 0 or count <= 0:
        return []
    return [days[min(n - 1, (i * n) // count)] for i in range(count)]


# Задание при раскладке: вид, параметры, норма, минуты, слабая сторона.
_Item = tuple[TaskKind, dict[str, str | int], int, float, str | None]


@dataclass(slots=True)
class _Week:
    """Раскладка недели: состояние сборки (см. правила модуля)."""

    goal: PlanGoal
    avail: Availability
    rules: PlannerRules
    days: tuple[date, ...]
    ordered: list[GapOut]
    per_day: dict[date, list[_Item]] = field(default_factory=dict)
    used: dict[date, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.per_day = {d: [] for d in self.days}
        self.used = dict.fromkeys(self.days, 0.0)

    @property
    def budget(self) -> float:
        return float(self.goal.minutes_per_day)

    @property
    def unit(self) -> Mapping[str, float]:
        return self.rules.unit_minutes

    @property
    def game_cost(self) -> float:
        game = self.rules.game_minutes
        return game.get(self.goal.time_class, game["rapid"])

    def add(self, d: date, item: _Item) -> None:
        self.per_day[d].append(item)
        self.used[d] += item[3]

    def lessons(self) -> list[tuple[str, str]]:
        keys: list[tuple[str, str]] = []
        for gap in self.ordered:
            if gap.lesson and gap.lesson not in {k for k, _ in keys}:
                keys.append((gap.lesson, gap.key))
        keys.sort(key=lambda item: item[0] in self.avail.read_lessons)
        return keys

    def streams(self, games: int, lessons: int) -> tuple[list[_Stream], int]:
        """Мелкие виды с минутами недели и итоговое число партий."""
        week_minutes = self.budget * len(self.days)
        pair = self.game_cost + self.unit["review"]
        tactics_share = (
            self.rules.tactics_share
            if self.goal.target_rating <= self.rules.tactics_high_from
            else self.rules.tactics_share_high
        )
        free = max(0.0, week_minutes - self.unit["lesson"] * lessons - games * pair)
        tactics = min(free, tactics_share * week_minutes)
        rest = free - tactics
        trainable = [
            (g, s)
            for g in self.ordered
            if (s := _weakness_stream(g, self.avail)) is not None and s[0] != "play"
        ]
        total_score = sum(max(g.score, 0.0) for g, _ in trainable)
        streams: list[_Stream] = []
        leftover = rest
        if trainable and total_score > 0:
            leftover = 0.0
            for gap, (kind, params) in trainable:
                share = rest * max(gap.score, 0.0) / total_score
                streams.append(_Stream(kind, tuple(sorted(params.items())), gap.key, share))
        elif not self.ordered:
            # Нет слабых сторон: остаток — поровну тактике и партиям.
            extra = math.floor((rest / 2) / pair)
            games += extra
            leftover = rest - extra * pair
        if self.avail.puzzles > 0:
            if tactics + leftover > 0:
                streams.insert(0, _Stream("puzzles", (), None, tactics + leftover))
        else:
            # Пазлов нет — время тактики уходит в партии.
            games += math.floor((tactics + leftover) / pair)
        return streams, games

    def place_lessons(self, keys: Sequence[tuple[str, str]]) -> None:
        for i, (lesson, gap_key) in enumerate(keys):
            d = self.days[i % len(self.days)]
            self.add(d, ("lesson", {"lesson": lesson}, 1, self.unit["lesson"], gap_key))

    def place_games(self, games: int) -> None:
        """Партии равномерно; разбор — в тот же день, если влезает, иначе в следующий."""
        review = self.unit["review"]
        hi = self.budget * (1 + self.rules.tolerance) + 1e-9
        games_on: dict[date, int] = {}
        for d in _spread(games, self.days):
            games_on[d] = games_on.get(d, 0) + 1
        play_focus = next(
            (
                g.key
                for g in self.ordered
                if (s := _weakness_stream(g, self.avail)) is not None and s[0] == "play"
            ),
            None,
        )
        pending = 0
        for d in self.days:
            count = games_on.get(d, 0)
            if count:
                params: dict[str, str | int] = {"bot_elo": self.avail.bot_elo}
                self.add(d, ("play", params, count, count * self.game_cost, play_focus))
            pending += count
            fit = 0
            while fit < pending and self.used[d] + (fit + 1) * review <= hi:
                fit += 1
            if fit == 0 and pending and d == self.days[-1]:
                fit = pending
            if fit:
                self.add(d, ("review", {}, fit, fit * review, None))
                pending -= fit

    def place_small(self, streams: Sequence[_Stream]) -> None:
        remaining = {i: s.minutes for i, s in enumerate(streams)}
        for d in self.days:
            room = self.budget - self.used[d]
            need = {i: m for i, m in remaining.items() if m > 1e-9}
            if room <= 0 or not need:
                continue
            added = self._share_day(d, room, streams, need, remaining)
            if not added and room >= self.rules.min_task_minutes:
                # Места мало на всех — весь остаток дня получает самый недоплаченный вид.
                i = max(need, key=lambda j: (need[j], -j))
                s = streams[i]
                per = self.unit[s.kind]
                count = max(1, math.floor(room / per + 1e-9))
                self.add(d, (s.kind, dict(s.params), count, count * per, s.focus))
                remaining[i] -= count * per
            self._fit_day(d)

    def _share_day(
        self,
        d: date,
        room: float,
        streams: Sequence[_Stream],
        need: Mapping[int, float],
        remaining: dict[int, float],
    ) -> bool:
        """Дню — доля недоплаченного каждым видом, пропорционально, в пределах места."""
        total_need = sum(need.values())
        added = False
        for i in sorted(need):
            s = streams[i]
            want = room * need[i] / total_need
            per = self.unit[s.kind]
            count = max(1, round(want / per)) if want >= per * 0.5 else 0
            if count == 0 or count * per < min(self.rules.min_task_minutes, room):
                continue
            self.add(d, (s.kind, dict(s.params), count, count * per, s.focus))
            remaining[i] -= count * per
            added = True
        return added

    def _fit_day(self, d: date) -> None:
        """Подогнать мелкие задания дня в ±10 % бюджета: добавить, потом убрать единицы."""
        items = self.per_day[d]
        tol = self.rules.tolerance
        lo, hi = self.budget * (1 - tol), self.budget * (1 + tol) + 1e-9
        small = [i for i, it in enumerate(items) if it[0] in SMALL_KINDS]
        if not small:
            return
        unit = self.unit
        # Добавлять — к самому мелкому по единице (точнее попадает).
        while self.used[d] < lo:
            i = min(small, key=lambda j: (unit[items[j][0]], j))
            kind, params, count, minutes, gap_key = items[i]
            if self.used[d] + unit[kind] > hi:
                break
            items[i] = (kind, params, count + 1, minutes + unit[kind], gap_key)
            self.used[d] += unit[kind]
        while self.used[d] > hi:
            candidates = [j for j in small if items[j][2] > 1]
            if not candidates:
                break
            i = max(candidates, key=lambda j: (unit[items[j][0]], -j))
            kind, params, count, minutes, gap_key = items[i]
            items[i] = (kind, params, count - 1, minutes - unit[kind], gap_key)
            self.used[d] -= unit[kind]

    def tasks(self) -> list[TaskSpec]:
        out: list[TaskSpec] = []
        for d in self.days:
            items = sorted(self.per_day[d], key=lambda t: KIND_ORDER.index(t[0]))
            for pos, (kind, params, target, minutes, gap_key) in enumerate(items):
                out.append(
                    TaskSpec(
                        day=d,
                        position=pos,
                        kind=kind,
                        params=params,
                        target=target,
                        unit=UNITS[kind],
                        minutes=max(1, round(minutes)),
                        focus=gap_key,
                    )
                )
        return out


def build_week_plan(
    weaknesses: Sequence[GapOut],
    goal: PlanGoal,
    avail: Availability,
    week_start: date,
    from_day: date,
    *,
    rules: PlannerRules = RULES,
) -> WeekPlan:
    days = study_days(week_start, goal.days_per_week, from_day)
    ordered = focus_of(weaknesses, rules)
    focus = tuple(g.key for g in ordered)
    if not days:
        return WeekPlan(week_start, days, focus, (), ())
    week = _Week(goal, avail, rules, days, ordered)
    lessons = week.lessons()
    pair = week.game_cost + week.unit["review"]
    play_floor = rules.play_share * week.budget * len(days)
    games = max(1, math.ceil(play_floor / pair - 1e-9))
    streams, games = week.streams(games, len(lessons))
    week.place_lessons(lessons)
    week.place_games(games)
    week.place_small(streams)
    tasks = week.tasks()
    return WeekPlan(week_start, days, focus, allocation(tasks), tuple(tasks))


class _TaskLike(Protocol):
    @property
    def kind(self) -> TaskKind: ...
    @property
    def minutes(self) -> int: ...
    @property
    def focus(self) -> str | None: ...


def allocation(tasks: Sequence[_TaskLike]) -> tuple[Allocation, ...]:
    """Распределение недели по видам — по фактическим заданиям."""
    total = sum(t.minutes for t in tasks)
    by_kind: dict[TaskKind, tuple[int, list[str]]] = {}
    for t in tasks:
        minutes, focus = by_kind.get(t.kind, (0, []))
        if t.focus and t.focus not in focus:
            focus.append(t.focus)
        by_kind[t.kind] = (minutes + t.minutes, focus)
    return tuple(
        Allocation(
            kind=kind,
            minutes_per_week=minutes,
            share=round(minutes / total, 3) if total else 0.0,
            focus=tuple(focus),
        )
        for kind in KIND_ORDER
        if kind in by_kind
        for minutes, focus in [by_kind[kind]]
    )
