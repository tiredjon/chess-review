"""ORM-модели (SPEC §7).

Перечисления хранятся строками с CHECK-ограничением, а не нативными PG enum:
так новые значения добавляются обычной миграцией без ALTER TYPE.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.review.types import MoveClass, Phase


class GameSource(StrEnum):
    LICHESS = "lichess"
    CHESSCOM = "chesscom"
    PGN = "pgn"


class Color(StrEnum):
    WHITE = "white"
    BLACK = "black"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ImportStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


def str_enum(enum_cls: type[StrEnum], name: str) -> sa.Enum:
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=16,
        values_callable=lambda e: [m.value for m in e],
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    # argon2; None — войти нельзя (dev-пользователь до регистрации владельца).
    password_hash: Mapped[str | None] = mapped_column(String(255))
    lichess_username: Mapped[str | None] = mapped_column(String(64))
    chesscom_username: Mapped[str | None] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(8), default="ru", server_default="ru")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    games: Mapped[list["Game"]] = relationship(back_populates="user", passive_deletes=True)


class RefreshToken(Base):
    """Refresh-токен (в cookie — сам токен, здесь — его sha256). Токены одного входа
    образуют цепочку `family_id`: обновление заменяет токен следующим, выход и повтор
    заменённого токена отзывают всю цепочку."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_family_id", "family_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID]
    expires_at: Mapped[datetime]
    # Заменён следующим токеном цепочки (при обновлении).
    replaced_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("source", "external_id", "user_id"),
        Index("ix_games_user_id_played_at", "user_id", "played_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[GameSource] = mapped_column(str_enum(GameSource, "game_source"))
    # Для PGN — хеш нормализованного PGN.
    external_id: Mapped[str] = mapped_column(String(128))
    pgn: Mapped[str] = mapped_column(Text)
    white: Mapped[str] = mapped_column(String(100))
    black: Mapped[str] = mapped_column(String(100))
    white_elo: Mapped[int | None]
    black_elo: Mapped[int | None]
    result: Mapped[str] = mapped_column(String(8))
    time_control: Mapped[str | None] = mapped_column(String(32))
    played_at: Mapped[datetime | None]
    user_color: Mapped[Color | None] = mapped_column(str_enum(Color, "color"))
    opening_eco: Mapped[str | None] = mapped_column(String(8))
    opening_name: Mapped[str | None] = mapped_column(String(255))
    # Точность по версии площадки (Chess.com — у партий, разобранных там).
    source_white_accuracy: Mapped[float | None]
    source_black_accuracy: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="games")
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="game", passive_deletes=True)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        str_enum(AnalysisStatus, "analysis_status"),
        default=AnalysisStatus.QUEUED,
        server_default=AnalysisStatus.QUEUED.value,
    )
    depth: Mapped[int]
    engine_version: Mapped[str | None] = mapped_column(String(64))
    # Точность по формуле Lichess (SPEC §4.3–4.4).
    white_accuracy: Mapped[float | None]
    black_accuracy: Mapped[float | None]
    # Точность «как у Chess.com» — приближение их формулы (`review/cc_accuracy.py`).
    cc_white_accuracy: Mapped[float | None]
    cc_black_accuracy: Mapped[float | None]
    phase_accuracy: Mapped[dict[str, Any] | None]
    error: Mapped[str | None] = mapped_column(Text)
    # Код ошибки для интерфейса (`app/api/errors.py`); `error` — подробности.
    error_code: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    game: Mapped[Game] = relationship(back_populates="analyses")
    moves: Mapped[list["Move"]] = relationship(
        back_populates="analysis", passive_deletes=True, order_by="Move.ply"
    )


class Move(Base):
    __tablename__ = "moves"
    __table_args__ = (UniqueConstraint("analysis_id", "ply"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    ply: Mapped[int]
    san: Mapped[str] = mapped_column(String(16))
    uci: Mapped[str] = mapped_column(String(8))
    fen_before: Mapped[str] = mapped_column(String(100))
    # Оценки — с точки зрения игрока, делающего ход (SPEC §4.1).
    eval_before_cp: Mapped[int | None]
    eval_after_cp: Mapped[int | None]
    mate_before: Mapped[int | None]
    mate_after: Mapped[int | None]
    win_before: Mapped[float]
    win_after: Mapped[float]
    accuracy: Mapped[float]
    move_class: Mapped[MoveClass] = mapped_column("class", str_enum(MoveClass, "move_class"))
    is_miss: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    best_uci: Mapped[str | None] = mapped_column(String(8))
    best_san: Mapped[str | None] = mapped_column(String(16))
    # Формат JSON-полей — в app/workers/serialize.py.
    pv: Mapped[list[Any] | None]
    multipv: Mapped[list[Any] | None]
    # Лучшая линия соперника после хода (чем наказывается ошибка).
    reply_pv: Mapped[list[Any] | None]
    motifs: Mapped[dict[str, Any] | None]
    phase: Mapped[Phase] = mapped_column(str_enum(Phase, "phase"))

    analysis: Mapped[Analysis] = relationship(back_populates="moves")


class ImportJob(Base):
    """Импорт партий пользователя с Lichess / Chess.com (выполняет воркер)."""

    __tablename__ = "import_jobs"
    __table_args__ = (Index("ix_import_jobs_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[GameSource] = mapped_column(str_enum(GameSource, "game_source"))
    username: Mapped[str] = mapped_column(String(64))
    # Параметры: max_games — для Lichess, months — для Chess.com.
    max_games: Mapped[int | None]
    months: Mapped[int | None]
    status: Mapped[ImportStatus] = mapped_column(
        str_enum(ImportStatus, "import_status"),
        default=ImportStatus.QUEUED,
        server_default=ImportStatus.QUEUED.value,
    )
    # Получено от источника / сохранено новых / пропущено (варианты, партии без ходов,
    # ошибки PGN). Остальные полученные уже были в базе.
    fetched: Mapped[int] = mapped_column(default=0, server_default="0")
    imported: Mapped[int] = mapped_column(default=0, server_default="0")
    skipped: Mapped[int] = mapped_column(default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    # Код ошибки для интерфейса (`app/api/errors.py`); `error` — подробности.
    error_code: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class Explanation(Base):
    __tablename__ = "explanations"
    __table_args__ = (UniqueConstraint("facts_hash", "lang"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    facts_hash: Mapped[str] = mapped_column(String(64))
    lang: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(Text)
    # "template" для шаблонных объяснений без LLM.
    provider: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PositionEval(Base):
    """Кэш анализа позиций; fen_key — FEN без счётчиков ходов."""

    __tablename__ = "position_evals"

    fen_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    depth: Mapped[int] = mapped_column(primary_key=True)
    multipv: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict[str, Any]]


class Puzzle(Base):
    """Пазл из ошибки пользователя (`app/puzzles/`): позиция до ошибки и решение — лучшая
    линия до выигрыша материала или мата. Повторение — по коробкам Лейтнера (`srs.py`)."""

    __tablename__ = "puzzles"
    __table_args__ = (
        Index("ix_puzzles_user_id_next_review_at", "user_id", "next_review_at"),
        # Одна позиция — один пазл: повторный анализ партии не плодит дубли.
        UniqueConstraint("user_id", "fen"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # SET NULL: пазл переживает удаление анализа; при повторном анализе ссылка обновляется.
    move_id: Mapped[int | None] = mapped_column(ForeignKey("moves.id", ondelete="SET NULL"))
    fen: Mapped[str] = mapped_column(String(100))
    # Ходы игрока и ответы соперника по очереди, первый и последний — ходы игрока.
    solution_uci: Mapped[list[str]] = mapped_column(ARRAY(String(8)))
    themes: Mapped[list[str]] = mapped_column(ARRAY(String(32)), server_default="{}")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    # Результат последней попытки.
    solved: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    # Коробка Лейтнера: 0 — новый или после ошибки, 1…5 — интервалы повторения.
    box: Mapped[int] = mapped_column(sa.SmallInteger, default=0, server_default="0")
    # None — новый пазл (ещё не решался).
    next_review_at: Mapped[datetime | None]
    last_attempt_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PuzzleAttempt(Base):
    """Завершённая попытка решить пазл (решён или нет) — для серии и истории."""

    __tablename__ = "puzzle_attempts"
    __table_args__ = (Index("ix_puzzle_attempts_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    puzzle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("puzzles.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    correct: Mapped[bool]
    hint_used: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
