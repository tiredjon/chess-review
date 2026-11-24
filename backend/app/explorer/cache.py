"""Кэш Lichess Opening Explorer в БД: позиции — на `explorer_cache_days` дней, PGN партий
мастеров — навсегда (партия не меняется). Ключ позиции — источник + `board.epd()` +
нормализованные параметры запроса (у `lichess` — скорости и рейтинги, у `masters` пусто)."""

import dataclasses
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import chess
import httpx
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.db.models import ExplorerCacheEntry, MasterGame
from app.db.session import Database
from app.explorer.client import LICHESS_PARAMS_KEY, LichessExplorer
from app.explorer.types import (
    ExplorerMove,
    ExplorerPosition,
    ExplorerSource,
    MasterGamePgn,
    MasterGameRef,
    OpeningExplorer,
)


def params_key(source: ExplorerSource) -> str:
    return LICHESS_PARAMS_KEY if source is ExplorerSource.LICHESS else ""


def position_to_data(position: ExplorerPosition) -> dict[str, Any]:
    data = dataclasses.asdict(position)
    data["source"] = position.source.value
    return data


def position_from_data(data: dict[str, Any]) -> ExplorerPosition:
    return ExplorerPosition(
        source=ExplorerSource(data["source"]),
        white=data["white"],
        draws=data["draws"],
        black=data["black"],
        moves=tuple(ExplorerMove(**m) for m in data["moves"]),
        top_games=tuple(MasterGameRef(**g) for g in data["top_games"]),
        opening_eco=data["opening_eco"],
        opening_name=data["opening_name"],
    )


class CachedExplorer:
    """Тот же протокол `OpeningExplorer`, но сначала — БД."""

    def __init__(
        self,
        inner: OpeningExplorer,
        db: Database,
        *,
        ttl_days: int = 30,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._inner = inner
        self._db = db
        self._ttl = timedelta(days=ttl_days)
        self._now = now

    async def position(
        self, board: chess.Board, *, source: ExplorerSource = ExplorerSource.MASTERS
    ) -> ExplorerPosition:
        key = (source.value, board.epd(), params_key(source))
        async with self._db.sessionmaker() as session:
            row = await session.get(ExplorerCacheEntry, key)
            if row is not None and self._now() - _aware(row.fetched_at) < self._ttl:
                return position_from_data(row.data)
        position = await self._inner.position(board, source=source)
        stmt = insert(ExplorerCacheEntry).values(
            source=key[0],
            epd=key[1],
            params=key[2],
            data=position_to_data(position),
            fetched_at=self._now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "epd", "params"],
            set_={"data": stmt.excluded.data, "fetched_at": stmt.excluded.fetched_at},
        )
        async with self._db.sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()
        return position

    async def master_game(self, game_id: str) -> MasterGamePgn:
        async with self._db.sessionmaker() as session:
            row = await session.get(MasterGame, game_id)
            if row is not None:
                return MasterGamePgn(
                    id=row.id,
                    pgn=row.pgn,
                    white=row.white,
                    black=row.black,
                    white_rating=row.white_rating,
                    black_rating=row.black_rating,
                    year=row.year,
                    result=row.result,
                )
        game = await self._inner.master_game(game_id)
        stmt = (
            insert(MasterGame)
            .values(
                id=game.id,
                pgn=game.pgn,
                white=game.white,
                black=game.black,
                white_rating=game.white_rating,
                black_rating=game.black_rating,
                year=game.year,
                result=game.result,
            )
            .on_conflict_do_nothing()
        )
        async with self._db.sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()
        return game

    async def purge_expired(self) -> int:
        """Удалить просроченные позиции (партии мастеров не трогает)."""
        stmt = delete(ExplorerCacheEntry).where(
            ExplorerCacheEntry.fetched_at < self._now() - self._ttl
        )
        async with self._db.sessionmaker() as session:
            result = await session.execute(stmt)
            await session.commit()
            return int(getattr(result, "rowcount", 0) or 0)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def make_explorer(settings: Settings, http: httpx.AsyncClient, db: Database) -> CachedExplorer:
    """Explorer с кэшем в БД: общий для API и воркера (один экземпляр на процесс — пауза и
    «один запрос за раз» действуют на весь процесс)."""
    return CachedExplorer(
        LichessExplorer.from_settings(settings, http), db, ttl_days=settings.explorer_cache_days
    )
