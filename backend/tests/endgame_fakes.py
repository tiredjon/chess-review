"""Фейки таблиц Syzygy для тестов тренажёра эндшпиля: ответы — живые ответы Lichess по
позициям каталога (`tests/data/endgame_tablebase.json`), без сети."""

import json
from pathlib import Path
from typing import Any

import chess

from app.endgames.tablebase import TablebaseUnavailableError, TbPosition, parse_position

FIXTURE = Path(__file__).parent / "data" / "endgame_tablebase.json"


def fixture_answers() -> dict[str, dict[str, Any]]:
    """Ответы Lichess по позициям каталога: ключ — FEN позиции каталога."""
    data: dict[str, dict[str, Any]] = json.loads(FIXTURE.read_text())
    return data


def _by_epd() -> dict[str, dict[str, Any]]:
    return {chess.Board(fen).epd(): raw for fen, raw in fixture_answers().items()}


class FakeRawTablebase:
    """«Сырой» Lichess (`raw`) — для теста кэша и CLI: ответы по EPD, вызовы записываются."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.answers = _by_epd()
        self.calls: list[str] = []

    async def raw(self, board: chess.Board) -> dict[str, Any]:
        self.calls.append(board.epd())
        if self.fail:
            raise TablebaseUnavailableError("тест")
        try:
            return self.answers[board.epd()]
        except KeyError:
            raise TablebaseUnavailableError(f"нет ответа для {board.epd()}") from None


class FakeTablebase(FakeRawTablebase):
    """Протокол `Tablebase` для API."""

    async def probe(self, board: chess.Board) -> TbPosition:
        return parse_position(await self.raw(board))
