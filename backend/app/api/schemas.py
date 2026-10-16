"""Схемы запросов и ответов API v1 (SPEC §8)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from app.db.accuracy import pick_accuracy
from app.db.models import AnalysisStatus, Color, GameSource, ImportStatus
from app.review.game_rating import TimeClass, game_rating, time_class
from app.review.thresholds import PUZZLE_MAX_PLAYER_MOVES
from app.review.types import MoveClass, Phase

# Вставленный PGN: ~1 МБ — это сотни партий, больше через этот эндпоинт не нужно.
PGN_MAX_CHARS = 1_000_000


class PgnImportIn(BaseModel):
    pgn: str = Field(min_length=1, max_length=PGN_MAX_CHARS)


# Ники Lichess и Chess.com: латиница, цифры, «_» и «-».
Username = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{2,50}$")]


class LichessImportIn(BaseModel):
    username: Username
    # Последние `max` партий (классические шахматы, без вариантов).
    max: int = Field(default=100, ge=1, le=1000)


class ChessComImportIn(BaseModel):
    username: Username
    # Календарные месяцы, считая текущий.
    months: int = Field(default=3, ge=1, le=24)


Lang = Literal["ru", "en"]
# Пароль: длина ограничена и сверху — argon2 на мегабайтной строке это DoS.
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterIn(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: Password
    # Язык, выбранный гостем на странице входа; None — по умолчанию (ru).
    lang: Lang | None = None


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class ProfileIn(BaseModel):
    """Изменяются только переданные поля; ник `null` или "" — удалить."""

    lang: Lang | None = None
    lichess_username: Username | Literal[""] | None = None
    chesscom_username: Username | Literal[""] | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    lang: Lang
    lichess_username: str | None
    chesscom_username: str | None
    created_at: datetime


class AuthOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    # Секунд до истечения access-токена.
    expires_in: int
    user: UserOut


class StreamTokenOut(BaseModel):
    """Токен для `GET /analyses/{id}/events?token=` (EventSource не умеет заголовки)."""

    token: str
    expires_in: int


class AnalyzeIn(BaseModel):
    # None — глубина из настроек (ANALYSIS_DEPTH).
    depth: int | None = Field(default=None, ge=1, le=30)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Progress(BaseModel):
    """Проанализировано позиций из total (повторы позиций считаются один раз)."""

    done: int
    total: int


class AnalysisSummary(ORMModel):
    id: uuid.UUID
    status: AnalysisStatus
    depth: int
    # Точность по формуле Lichess.
    white_accuracy: float | None
    black_accuracy: float | None
    # Точность «как у Chess.com» (`review/cc_accuracy.py`); у старых анализов может не быть.
    cc_white_accuracy: float | None = None
    cc_black_accuracy: float | None = None
    created_at: datetime
    finished_at: datetime | None


class MoveOut(ORMModel):
    """Ход с разбором. Оценки — с точки зрения игрока, делающего ход (SPEC §4.1);
    `mate_after == 0` — ход ставит мат. Формат `pv`/`multipv`/`reply_pv`/`motifs` —
    в app/workers/serialize.py."""

    id: int
    ply: int
    san: str
    uci: str
    fen_before: str
    eval_before_cp: int | None
    eval_after_cp: int | None
    mate_before: int | None
    mate_after: int | None
    win_before: float
    win_after: float
    accuracy: float
    move_class: MoveClass = Field(serialization_alias="class")
    is_miss: bool
    best_uci: str | None
    best_san: str | None
    pv: list[Any] | None
    multipv: list[Any] | None
    reply_pv: list[Any] | None
    motifs: dict[str, Any] | None
    phase: Phase

    @computed_field  # type: ignore[prop-decorator]
    @property
    def color(self) -> Color:
        return Color.WHITE if self.fen_before.split()[1] == "w" else Color.BLACK

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fullmove(self) -> int:
        return int(self.fen_before.split()[5])


class AnalysisOut(AnalysisSummary):
    game_id: uuid.UUID
    engine_version: str | None
    # {"white": {"opening": 91.2, "middlegame": …, "endgame": null}, "black": {…}}
    phase_accuracy: dict[str, Any] | None
    error: str | None
    error_code: str | None = None
    started_at: datetime | None
    # Только у queued/running, если воркер уже сообщил прогресс.
    progress: Progress | None = None
    # Только у done.
    moves: list[MoveOut] = []


class GameRating(BaseModel):
    white: int | None
    black: int | None


class GameOut(ORMModel):
    id: uuid.UUID
    source: GameSource
    white: str
    black: str
    white_elo: int | None
    black_elo: int | None
    result: str
    time_control: str | None
    played_at: datetime | None
    user_color: Color | None
    opening_eco: str | None
    opening_name: str | None
    # Точность по версии площадки (Chess.com), если там партию разбирали.
    source_white_accuracy: float | None
    source_black_accuracy: float | None
    created_at: datetime
    # Последний анализ партии.
    analysis: AnalysisSummary | None = None

    def accuracy_of(self, color: Color) -> float | None:
        """Точность для показа (порядок источников — `app/db/accuracy.py`)."""
        picked = pick_accuracy(self, self.analysis, color)
        return None if picked is None else picked[0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def game_rating(self) -> GameRating | None:
        """Рейтинг партии по точности, как «Game Rating» Chess.com; None — точности нет."""
        white, black = self.accuracy_of(Color.WHITE), self.accuracy_of(Color.BLACK)
        if white is None and black is None:
            return None
        tc = time_class(self.time_control)
        return GameRating(
            white=None if white is None else game_rating(white, tc),
            black=None if black is None else game_rating(black, tc),
        )


class GameDetail(GameOut):
    pgn: str
    analysis: AnalysisOut | None = None


class GamePage(BaseModel):
    items: list[GameOut]
    # Передать в `cursor`, чтобы получить следующую страницу; None — страниц больше нет.
    next_cursor: str | None


class ImportJobOut(ORMModel):
    """Импорт партий. `fetched` = `imported` (новые) + `skipped` (варианты, партии
    без ходов, ошибки PGN) + уже бывшие в базе."""

    job_id: uuid.UUID = Field(validation_alias="id")
    source: GameSource
    username: str
    max_games: int | None
    months: int | None
    status: ImportStatus
    fetched: int
    imported: int
    skipped: int
    error: str | None
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


ExplainLang = Literal["ru", "en"]


class ExplainIn(BaseModel):
    # None — язык пользователя.
    lang: ExplainLang | None = None


class MoveExplanationOut(BaseModel):
    move_id: int
    ply: int
    text: str
    # "template" — шаблонное объяснение без LLM, иначе имя провайдера.
    provider: str
    cached: bool


class SummaryOut(BaseModel):
    analysis_id: uuid.UUID
    # 3–5 пунктов, по строке на пункт, каждый начинается с «- ».
    text: str
    provider: str
    cached: bool


# --- Статистика (GET /stats/me) ---

AccuracyKindOut = Literal["official", "cc", "lichess"]
GameOutcome = Literal["win", "draw", "loss"]


class StatsFilters(BaseModel):
    source: GameSource | None
    time_class: TimeClass | None


class StatsTotals(BaseModel):
    """Партии за пользователя (с известным цветом) после фильтров."""

    games: int
    # Партии без цвета пользователя (вставленный PGN без его ника) — в статистику не входят.
    games_without_color: int
    # С готовым анализом: по ним считаются фазы, классы ходов и мотивы.
    analyzed: int
    wins: int
    draws: int
    losses: int
    # Средняя показываемая точность (см. `app/db/accuracy.py`) и по скольким партиям.
    accuracy: float | None
    with_accuracy: int


class AccuracyPoint(BaseModel):
    game_id: uuid.UUID
    played_at: datetime | None
    accuracy: float
    # Откуда точность: официальная Chess.com, наша «как у Chess.com» или формула Lichess.
    kind: AccuracyKindOut
    # Скользящее среднее по последним `window` партиям (включая эту).
    moving_avg: float
    opponent: str
    outcome: GameOutcome | None
    time_class: TimeClass
    color: Color


class AccuracySeries(BaseModel):
    window: int
    # Старые первыми; не больше последних STATS_MAX_POINTS партий.
    points: list[AccuracyPoint]


class OpeningStat(BaseModel):
    eco: str | None
    name: str
    games: int
    wins: int
    draws: int
    losses: int
    accuracy: float | None


class OpeningsStats(BaseModel):
    white: list[OpeningStat]
    black: list[OpeningStat]


class PhaseStat(BaseModel):
    phase: Phase
    # Средняя точность фазы по формуле Lichess (как в обзоре партии).
    accuracy: float | None
    games: int


class ClassStat(BaseModel):
    # Класс хода или "miss" (флаг поверх класса).
    move_class: MoveClass | Literal["miss"] = Field(serialization_alias="class")
    count: int
    per_game: float
    # Доля среди всех ходов пользователя, %.
    share: float


class ClassesStats(BaseModel):
    games: int
    moves: int
    items: list[ClassStat]


class MotifExample(BaseModel):
    game_id: uuid.UUID
    move_id: int
    ply: int
    fullmove: int
    color: Color
    san: str
    move_class: MoveClass = Field(serialization_alias="class")
    is_miss: bool
    played_at: datetime | None
    opponent: str


class MotifStat(BaseModel):
    type: str
    # Ходов-ошибок, где мотив был в опровержении или упущен.
    count: int
    examples: list[MotifExample]


class StatsOut(BaseModel):
    filters: StatsFilters
    totals: StatsTotals
    accuracy: AccuracySeries
    openings: OpeningsStats
    phases: list[PhaseStat]
    classes: ClassesStats
    motifs: list[MotifStat]


# --- Пазлы (GET /puzzles/next, POST /puzzles/{id}/attempt) ---

UciMove = Annotated[str, Field(pattern=r"^[a-h][1-8][a-h][1-8][qrbn]?$")]


class PuzzleSource(BaseModel):
    """Ошибка в партии, из которой сделан пазл (ссылка на ход в разборе)."""

    game_id: uuid.UUID
    ply: int
    fullmove: int
    san: str
    move_class: MoveClass = Field(serialization_alias="class")
    is_miss: bool
    opponent: str
    played_at: datetime | None


class PuzzleLastMove(BaseModel):
    """Ход соперника, после которого возникла позиция пазла: показать его анимацией."""

    uci: str
    san: str
    fen_before: str


class PuzzleOut(BaseModel):
    id: uuid.UUID
    fen: str
    # Сторона игрока (на ходу в `fen`).
    color: Color
    themes: list[str]
    # Ходов игрока в решении.
    player_moves: int
    # Подсказка «показать фигуру»: поле, с которого ходит игрок, на каждый его ход.
    hints: list[str]
    box: int
    attempts: int
    next_review_at: datetime | None
    last_move: PuzzleLastMove | None
    source: PuzzleSource | None


class PuzzleCounts(BaseModel):
    # Пора повторить / новые (ещё не решались) / всего.
    due: int
    new: int
    total: int
    # Решённых подряд (последние завершённые попытки).
    streak: int
    # Ближайшее будущее повторение, если сейчас повторять нечего.
    next_review_at: datetime | None


class PuzzleNextOut(BaseModel):
    # None — на сейчас пазлов нет.
    puzzle: PuzzleOut | None
    counts: PuzzleCounts


class AttemptIn(BaseModel):
    """Ходы попытки с начала пазла: ход игрока, ответ соперника (из ответа API), …"""

    moves_uci: list[UciMove] = Field(max_length=2 * PUZZLE_MAX_PLAYER_MOVES)
    # Подсказка использована: решение засчитывается, но коробка не растёт.
    hint_used: bool = False
    # «Показать решение»: попытка завершается как нерешённая.
    gave_up: bool = False


class AttemptOut(BaseModel):
    """`continue` — ход верный, соперник отвечает `reply_uci`; `solved` / `failed` — попытка
    завершена и записана: `expected_uci` — верный ход там, где ошибся игрок."""

    result: Literal["continue", "solved", "failed"]
    reply_uci: str | None = None
    expected_uci: str | None = None
    # Только у завершённой попытки.
    solution_uci: list[str] | None = None
    solution_san: list[str] | None = None
    box: int | None = None
    next_review_at: datetime | None = None
    streak: int | None = None
