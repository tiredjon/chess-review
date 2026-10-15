"""Схемы запросов и ответов API v1 (SPEC §8)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.models import AnalysisStatus, Color, GameSource
from app.review.types import MoveClass, Phase

# Вставленный PGN: ~1 МБ — это сотни партий, больше через этот эндпоинт не нужно.
PGN_MAX_CHARS = 1_000_000


class PgnImportIn(BaseModel):
    pgn: str = Field(min_length=1, max_length=PGN_MAX_CHARS)


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
    white_accuracy: float | None
    black_accuracy: float | None
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
    created_at: datetime
    # Последний анализ партии.
    analysis: AnalysisSummary | None = None


class GameDetail(GameOut):
    pgn: str
    analysis: AnalysisOut | None = None


class GamePage(BaseModel):
    items: list[GameOut]
    # Передать в `cursor`, чтобы получить следующую страницу; None — страниц больше нет.
    next_cursor: str | None
