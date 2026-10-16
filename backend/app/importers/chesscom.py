"""Клиент Chess.com Published-Data API: партии пользователя по месяцам.

Пагинация — помесячные архивы: `/pub/player/{user}/games/archives` перечисляет месяцы,
в которых были партии, каждый месяц — отдельный запрос. `months` — календарные
месяцы, считая текущий. Месяцы идут от нового к старому, партии внутри — тоже.
Ник в URL — в нижнем регистре (иначе Chess.com отвечает редиректом 301).
"""

import re
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import httpx

from app.importers.http import RetryPolicy, SourceError, UserNotFoundError, get_with_retry
from app.importers.sources import SourceGame

SOURCE = "Chess.com"
_ARCHIVE_RE = re.compile(r"/games/(\d{4})/(\d{2})/?$")
_GAME_URL_RE = re.compile(r"/game/(live|daily)/(\d+)")


def _month_index(year: int, month: int) -> int:
    return year * 12 + month - 1


class ChessComClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str = "https://api.chess.com",
        policy: RetryPolicy | None = None,
    ) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.policy = policy or RetryPolicy()

    async def games(
        self, username: str, months: int, *, today: date
    ) -> AsyncIterator[list[SourceGame]]:
        """Партии за последние `months` календарных месяцев, по странице на месяц."""
        oldest = _month_index(today.year, today.month) - (months - 1)
        for year, month in await self._archives(username):
            if _month_index(year, month) < oldest:
                break
            if page := await self._month(username, year, month):
                yield page

    async def recent(self, username: str, *, archives: int = 2) -> AsyncIterator[list[SourceGame]]:
        """Партии последних `archives` месяцев, в которых пользователь играл (по архивам,
        а не по календарю): последняя партия — даже если она была давно."""
        for year, month in (await self._archives(username))[:archives]:
            if page := await self._month(username, year, month):
                yield page

    async def _archives(self, username: str) -> list[tuple[int, int]]:
        """Месяцы с партиями, новые первыми."""
        archives = await self._json(f"{self._player(username)}/games/archives", username)
        return sorted(
            {
                (int(match[1]), int(match[2]))
                for url in archives.get("archives", [])
                if isinstance(url, str) and (match := _ARCHIVE_RE.search(url))
            },
            reverse=True,
        )

    async def _month(self, username: str, year: int, month: int) -> list[SourceGame]:
        """Партии месяца, новые первыми."""
        # URL месяца строим сами, а не берём из ответа: только наш base_url.
        data = await self._json(f"{self._player(username)}/games/{year:04d}/{month:02d}", username)
        rows = sorted(
            (row for row in data.get("games", []) if isinstance(row, dict)),
            key=lambda row: int(row.get("end_time") or 0),
            reverse=True,
        )
        return [game for row in rows if (game := _source_game(row)) is not None]

    def _player(self, username: str) -> str:
        return f"{self.base_url}/pub/player/{username.lower()}"

    async def _json(self, url: str, username: str) -> dict[str, Any]:
        response = await get_with_retry(self.http, url, source=SOURCE, policy=self.policy)
        # 410 — закрытый аккаунт.
        if response.status_code in (httpx.codes.NOT_FOUND, httpx.codes.GONE):
            raise UserNotFoundError(f"Пользователь {username} не найден на Chess.com")
        if response.status_code != httpx.codes.OK:
            raise SourceError(f"{SOURCE}: ответ {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError(f"{SOURCE}: некорректный ответ") from exc
        if not isinstance(data, dict):
            raise SourceError(f"{SOURCE}: некорректный ответ")
        return data


def _external_id(row: dict[str, Any]) -> str | None:
    """`live/183193101523` / `daily/…` из URL партии; у live и daily — разные счётчики."""
    match = _GAME_URL_RE.search(str(row.get("url", "")))
    if match is not None:
        return f"{match[1]}/{match[2]}"
    uuid = row.get("uuid")
    return str(uuid) if uuid else None


def _accuracy(row: dict[str, Any], color: str) -> float | None:
    """Точность из `accuracies` — есть только у партий, разобранных на Chess.com."""
    accuracies = row.get("accuracies")
    value = accuracies.get(color) if isinstance(accuracies, dict) else None
    return float(value) if isinstance(value, int | float) and 0 <= value <= 100 else None


def _source_game(row: dict[str, Any]) -> SourceGame | None:
    external_id = _external_id(row)
    if external_id is None:
        return None
    return SourceGame(
        external_id=external_id,
        pgn=str(row.get("pgn", "")),
        standard=row.get("rules", "chess") == "chess",
        white_accuracy=_accuracy(row, "white"),
        black_accuracy=_accuracy(row, "black"),
    )
