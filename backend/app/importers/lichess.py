"""Клиент Lichess: партии пользователя (`GET /api/games/user/{username}`, NDJSON).

Пагинация — страницами по `page_size` партий через `until` (Lichess отдаёт партии
строго раньше `until`, новые первыми). Следующая страница начинается с самого
старого createdAt предыдущей включительно — партии с одинаковым временем на стыке
не теряются, а повторы отсекаются по id. Страница запрашивается целиком и при
сбое повторяется целиком.

Анонимно Lichess отдаёт 20 партий в секунду, с токеном — 30. На дефолтные
User-Agent библиотек отвечает 404 — UA задаётся в `make_http_client`.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.importers.http import RetryPolicy, SourceError, UserNotFoundError, get_with_retry
from app.importers.sources import SourceGame

SOURCE = "Lichess"
PAGE_SIZE = 100
# Только классические шахматы: варианты не попадают в выдачу и не съедают `max`.
PERF_TYPES = "ultraBullet,bullet,blitz,rapid,classical,correspondence"
STANDARD_VARIANTS = frozenset({"standard", "fromPosition"})


class LichessClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str = "https://lichess.org",
        token: str | None = None,
        policy: RetryPolicy | None = None,
        page_size: int = PAGE_SIZE,
    ) -> None:
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.headers = {"Accept": "application/x-ndjson"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.policy = policy or RetryPolicy()
        self.page_size = page_size

    async def games(self, username: str, max_games: int) -> AsyncIterator[list[SourceGame]]:
        """Последние `max_games` партий пользователя страницами, новые первыми."""
        seen: set[str] = set()
        until: int | None = None
        # Партии последней страницы с её самым старым createdAt: придут повторно.
        repeated = 0
        while len(seen) < max_games:
            remaining = max_games - len(seen)
            requested = min(self.page_size, remaining) + repeated
            rows = await self._page(username, requested, until)
            page = [_source_game(row) for row in rows if row["id"] not in seen][:remaining]
            seen.update(game.external_id for game in page)
            if page:
                yield page
            if len(rows) < requested or not page:
                return
            oldest = min(int(row["createdAt"]) for row in rows)
            # `until` у Lichess исключающий: +1, чтобы не потерять партии с тем же createdAt.
            until = oldest + 1
            repeated = sum(1 for row in rows if int(row["createdAt"]) == oldest)

    async def _page(self, username: str, max_games: int, until: int | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "max": max_games,
            "pgnInJson": "true",
            "clocks": "true",
            "opening": "false",
            "perfType": PERF_TYPES,
        }
        if until is not None:
            params["until"] = until
        response = await get_with_retry(
            self.http,
            f"{self.base_url}/api/games/user/{username}",
            source=SOURCE,
            policy=self.policy,
            params=params,
            headers=self.headers,
        )
        if response.status_code == httpx.codes.NOT_FOUND:
            raise UserNotFoundError(f"Пользователь {username} не найден на Lichess")
        if response.status_code != httpx.codes.OK:
            raise SourceError(f"{SOURCE}: ответ {response.status_code}")
        try:
            rows = [json.loads(line) for line in response.text.splitlines() if line.strip()]
            for row in rows:
                if not isinstance(row.get("id"), str) or "createdAt" not in row:
                    raise ValueError("нет id / createdAt")
        except (ValueError, AttributeError) as exc:
            raise SourceError(f"{SOURCE}: некорректный ответ ({exc})") from exc
        return rows


def _source_game(row: dict[str, Any]) -> SourceGame:
    return SourceGame(
        external_id=row["id"],
        pgn=str(row.get("pgn", "")),
        standard=row.get("variant", "standard") in STANDARD_VARIANTS,
    )
