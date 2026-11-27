"""Схемы тренера (SPEC «Сессия 17») — общий контракт 17.1 (диагностика), 17.2 (цель, план,
задания, прогноз, уроки) и 17.3 (веб, зеркало — `web/src/lib/coach-api.ts`).

Фундамент: только формы ответов и запросов. Менять поля — только согласованно со SPEC и
`coach-api.ts`; добавлять необязательные поля можно, описав это в отчёте подсессии.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.schemas_insights import ExampleOut, TrainOut
from app.review.game_rating import TimeClass

# --- Цель -------------------------------------------------------------------------------------

GoalSource = Literal["chesscom", "lichess"]


class GoalIn(BaseModel):
    """`PUT /coach/goal`: новая цель архивирует прежнюю. `start_rating` берётся с площадки —
    рейтинг из последней партии пользователя в этом контроле (нет партий → 422
    `coach_no_rating`). `target_rating` должен быть выше текущего."""

    source: GoalSource
    time_class: TimeClass
    target_rating: int = Field(ge=400, le=3200)
    minutes_per_day: int = Field(ge=10, le=240)
    days_per_week: int = Field(ge=1, le=7)
    # IANA-зона браузера (`Intl.DateTimeFormat().resolvedOptions().timeZone`).
    tz: str = Field(min_length=1, max_length=64)


class GoalOut(BaseModel):
    id: int
    source: GoalSource
    time_class: TimeClass
    start_rating: int
    # Рейтинг из последней партии в этом контроле — сейчас.
    current_rating: int
    target_rating: int
    minutes_per_day: int
    days_per_week: int
    tz: str
    created_at: datetime
    achieved_at: datetime | None


class RatingOptionOut(BaseModel):
    """Где у пользователя есть рейтинг — варианты для мастера цели."""

    source: GoalSource
    time_class: TimeClass
    rating: int
    games: int
    last_played_at: datetime | None


class GoalStateOut(BaseModel):
    """`GET /coach/goal`: активная цель (или `null`) и доступные рейтинги."""

    goal: GoalOut | None
    ratings: list[RatingOptionOut]


# --- Диагностика (17.1) -----------------------------------------------------------------------

# Метрики с фиксированными ключами; `motif` — пропуски мотива (ключ — тип мотива, как в
# `common.motifs`), `opening` — вывод о дебюте из `/insights/me` (ключ `цвет:семейство`).
MetricKey = Literal[
    "accuracy",
    "accuracy_opening",
    "accuracy_middlegame",
    "accuracy_endgame",
    "blunders_per_100",
    "mistakes_per_100",
    "misses_per_100",
    "conversion",
    "resilience",
    "time_trouble_share",
    "hasty_per_100",
]
MetricKind = Literal["metric", "motif", "opening"]
Direction = Literal["higher_better", "lower_better"]
MetricStatus = Literal["strength", "weakness", "neutral", "insufficient"]
Severity = Literal["high", "medium", "low"]


class NormOut(BaseModel):
    """Распределение метрики в рейтинговой группе (квартили)."""

    p25: float
    p50: float
    p75: float


class MetricOut(BaseModel):
    kind: MetricKind
    key: str
    # Значение пользователя; `null` — данных мало (`status: insufficient`).
    value: float | None
    # На чём держится значение: ходов (для «на 100 ходов» и мотивов) или партий.
    n: int
    direction: Direction
    current: NormOut | None
    target: NormOut | None
    # Место пользователя среди целевой группы, 0–100 (больше — лучше с учётом direction).
    percentile: float | None
    status: MetricStatus


class GapOut(BaseModel):
    """Сильная или слабая сторона относительно целевой группы."""

    kind: MetricKind
    key: str
    severity: Severity
    # Для сортировки: чем больше, тем важнее (сила — чем дальше выше нормы).
    score: float
    value: float
    target_p50: float | None
    train: TrainOut | None
    # Ключ урока (`GET /coach/lessons/{key}`), если урок есть.
    lesson: str | None
    examples: list[ExampleOut]


class DiagnosisOut(BaseModel):
    """`GET /coach/diagnosis`: по партиям цели (площадка + контроль). Пока разобранных партий
    меньше `min_games` — `metrics` со `status: insufficient`, `strengths`/`weaknesses` пусты."""

    goal: GoalOut
    current_rating: int
    # Центры групп эталона (например, 1700 и 2000).
    current_band: int
    target_band: int
    norms_version: str
    analyzed_games: int
    min_games: int
    metrics: list[MetricOut]
    strengths: list[GapOut]
    weaknesses: list[GapOut]


# --- План и задания (17.2) --------------------------------------------------------------------

TaskKind = Literal["puzzles", "rush", "endgames", "course", "play", "review", "lesson"]
TaskUnit = Literal["puzzles", "runs", "attempts", "games", "lessons"]


class TaskOut(BaseModel):
    id: int
    day: date
    position: int
    kind: TaskKind
    # Параметры ссылки: theme / phase / eco (пазлы), course_id, bot_elo, game_id, lesson и т.п.
    params: dict[str, str | int]
    target: int
    progress: int
    unit: TaskUnit
    minutes: int
    done: bool
    done_at: datetime | None
    # Куда ведёт задание (ссылки сессии 16: `/puzzles?mode=practice&theme=fork` и т.д.).
    href: str
    # Ключ слабой стороны, ради которой задание (`GapOut.key`), или `null`.
    focus: str | None


class TodayOut(BaseModel):
    """`GET /coach/today`: задания на сегодня по зоне цели. Нет плана на эту неделю — план
    собирается при обращении. Прогресс пересчитывается по таблицам активности при каждом
    запросе."""

    goal: GoalOut
    day: date
    rest_day: bool
    tasks: list[TaskOut]
    minutes_total: int
    minutes_done: int
    # Дней подряд (до вчера включительно плюс сегодня, если всё выполнено) без пропуска
    # учебного дня.
    streak_days: int


class AllocationOut(BaseModel):
    kind: TaskKind
    minutes_per_week: int
    share: float
    # Ключи слабых сторон, на которые идёт это время.
    focus: list[str]


class PlanDayOut(BaseModel):
    day: date
    rest_day: bool
    minutes: int
    tasks: list[TaskOut]


class PlanOut(BaseModel):
    """`GET /coach/plan` (текущая неделя), `POST /coach/plan/rebuild` — пересобрать с сегодня
    (прошедшие дни недели не меняются)."""

    goal: GoalOut
    week_start: date
    created_at: datetime
    focus: list[GapOut]
    allocation: list[AllocationOut]
    days: list[PlanDayOut]
    next_rebuild: date


class MetricDeltaOut(BaseModel):
    kind: MetricKind
    key: str
    before: float | None
    after: float | None
    direction: Direction


class WeekReportOut(BaseModel):
    week_start: date
    tasks_total: int
    tasks_done: int
    minutes_done: int
    games_played: int
    rating_start: int | None
    rating_end: int | None
    metrics: list[MetricDeltaOut]


class ReportOut(BaseModel):
    """`GET /coach/report`: отчёт за прошлую неделю плана (или `null`, если её не было)."""

    report: WeekReportOut | None


# --- Прогноз (17.2) ---------------------------------------------------------------------------

ForecastStatus = Literal["achieved", "ahead", "on_track", "behind", "insufficient"]
Confidence = Literal["low", "medium", "high"]


class RatingPointOut(BaseModel):
    date: date
    rating: int


class ForecastPointOut(BaseModel):
    date: date
    p10: float
    p50: float
    p90: float


class ForecastBasisOut(BaseModel):
    # Игроков выборки эталона с похожим стартом, на которых построена базовая кривая.
    sample_players: int
    user_games: int
    # Рейтинг в неделю по своему тренду (может быть отрицательным).
    weekly_trend: float | None
    # Доля выполненных заданий за последние 4 недели плана, 0–1; `null` — плана ещё нет.
    adherence: float | None
    games_per_week: float


class ForecastOut(BaseModel):
    """`GET /coach/forecast`: срок как диапазон, не обещание. `weeks_*`/`date_*` — `null`, если
    по данным цель за 3 года не достигается или данных мало (`status: insufficient`)."""

    start_rating: int
    current_rating: int
    target_rating: int
    status: ForecastStatus
    weeks_p50: int | None
    weeks_p80: int | None
    date_p50: date | None
    date_p80: date | None
    reach_probability_1y: float | None
    confidence: Confidence
    basis: ForecastBasisOut
    history: list[RatingPointOut]
    projection: list[ForecastPointOut]


# --- Уроки (17.2) -----------------------------------------------------------------------------

LessonKind = Literal["motif", "phase", "skill"]


class LessonItemOut(BaseModel):
    key: str
    kind: LessonKind
    read: bool


class LessonListOut(BaseModel):
    lessons: list[LessonItemOut]


class LessonOut(BaseModel):
    """`GET /coach/lessons/{key}`: текст урока — на фронте (`web/src/lib/coach-lessons/`) по
    ключу; бэкенд даёт позиции из своих партий и ссылку на тренировку. Неизвестный ключ — 404
    `lesson_not_found`."""

    key: str
    kind: LessonKind
    read: bool
    examples: list[ExampleOut]
    train: TrainOut | None
