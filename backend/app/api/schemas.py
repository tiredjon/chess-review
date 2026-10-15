"""Схемы запросов и ответов API v1 (SPEC §8)."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.models import AnalysisStatus, Color, GameSource, ImportStatus
from app.review.game_rating import game_rating, time_class
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
        """Точность для показа: официальная Chess.com, иначе наша «как у Chess.com»,
        иначе (старый анализ) — по формуле Lichess."""
        white = color == Color.WHITE
        official = self.source_white_accuracy if white else self.source_black_accuracy
        if official is not None:
            return official
        analysis = self.analysis
        if analysis is None or analysis.status != AnalysisStatus.DONE:
            return None
        cc = analysis.cc_white_accuracy if white else analysis.cc_black_accuracy
        return (
            cc
            if cc is not None
            else (analysis.white_accuracy if white else analysis.black_accuracy)
        )

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
