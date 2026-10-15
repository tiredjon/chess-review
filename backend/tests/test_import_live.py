"""Импорт с настоящих Lichess и Chess.com. Ходит в сеть — только с NETWORK_TESTS=1.

Ловит изменения внешних API, которые фейки не покажут (так нашлось, что Lichess
отвечает 404 на дефолтный User-Agent httpx).
"""

import os
from datetime import UTC, datetime

import pytest

from app.core.config import Settings
from app.importers.chesscom import ChessComClient
from app.importers.http import UserNotFoundError, make_http_client
from app.importers.lichess import LichessClient
from app.importers.sources import convert_page

pytestmark = pytest.mark.skipif(
    os.environ.get("NETWORK_TESTS") != "1", reason="сетевые тесты: NETWORK_TESTS=1"
)


async def test_lichess_live() -> None:
    async with make_http_client(Settings()) as http:
        client = LichessClient(http, page_size=3)
        pages = [page async for page in client.games("thibault", 5)]
        games = convert_page([game for page in pages for game in page], "thibault")

        assert [len(page) for page in pages] == [3, 2]
        assert games
        assert all(game.user_color is not None for game in games)
        with pytest.raises(UserNotFoundError):
            [page async for page in client.games("zz-no-such-user-zz", 1)]


async def test_chesscom_live() -> None:
    today = datetime.now(UTC).date()
    async with make_http_client(Settings()) as http:
        client = ChessComClient(http)
        pages = [page async for page in client.games("Hikaru", 2, today=today)]
        games = convert_page(pages[0], "hikaru")

        assert games
        assert all(game.user_color is not None for game in games)
        with pytest.raises(UserNotFoundError):
            [page async for page in client.games("zz-no-such-user-zz", 1, today=today)]
