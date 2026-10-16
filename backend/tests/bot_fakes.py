"""Фейки для тестов бота: Telegram Bot API (httpx.MockTransport) и движок «по материалу»."""

import asyncio
import json
import uuid
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

import chess
import httpx
from chess.engine import Cp, Mate, Score

from app.review.types import EngineLine, PositionEval
from app.workers.analysis import analyze_game

TOKEN = "123:TEST"
API_URL = "https://telegram.test"
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


@dataclass
class FakeTelegram:
    """Bot API: записывает вызовы, `getUpdates` отдаёт пачки из `updates` по очереди."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    updates: list[list[dict[str, Any]]] = field(default_factory=list)
    # Метод → описание ошибки (один раз).
    failures: dict[str, str] = field(default_factory=dict)
    next_message_id: int = 100
    message_sent: asyncio.Event = field(default_factory=asyncio.Event)

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        prefix = f"/bot{TOKEN}/"
        assert request.url.path.startswith(prefix), request.url.path
        method = request.url.path.removeprefix(prefix)
        payload: dict[str, Any] = json.loads(request.content or b"{}")
        self.calls.append((method, payload))
        if description := self.failures.pop(method, None):
            return httpx.Response(
                400, json={"ok": False, "error_code": 400, "description": description}
            )
        result: Any = True
        if method == "getMe":
            result = {"id": 1, "is_bot": True, "username": "review_test_bot"}
        elif method == "getUpdates":
            if self.updates:
                result = self.updates.pop(0)
            else:
                # Long polling без событий: не крутить цикл вхолостую.
                await asyncio.sleep(0.01)
                result = []
        elif method == "sendMessage":
            self.next_message_id += 1
            self.message_sent.set()
            result = {
                "message_id": self.next_message_id,
                "chat": {"id": payload["chat_id"], "type": "private"},
                "text": payload["text"],
            }
        return httpx.Response(200, json={"ok": True, "result": result})

    def sent(self, method: str | None = None) -> list[dict[str, Any]]:
        """Отправленные и изменённые сообщения (или вызовы `method`)."""
        methods = {method} if method else {"sendMessage", "editMessageText"}
        return [payload for name, payload in self.calls if name in methods]

    @property
    def last_text(self) -> str:
        text: str = self.sent()[-1]["text"]
        return text


def message_update(
    text: str, *, chat_id: int = 501, language_code: str | None = "ru", update_id: int = 1
) -> dict[str, Any]:
    user: dict[str, Any] = {"id": chat_id, "is_bot": False, "first_name": "Test"}
    if language_code is not None:
        user["language_code"] = language_code
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": chat_id, "type": "private"},
            "from": user,
            "text": text,
        },
    }


def callback_update(
    data: str, *, message_id: int, chat_id: int = 501, update_id: int = 2
) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "cb-1",
            "from": {"id": chat_id, "is_bot": False, "first_name": "Test", "language_code": "ru"},
            "message": {"message_id": message_id, "date": 0, "chat": {"id": chat_id}},
            "data": data,
        },
    }


def _material(board: chess.Board) -> int:
    """Материал в сантипешках за сторону, которая ходит."""
    total = 0
    for piece_type, value in VALUES.items():
        own = len(board.pieces(piece_type, board.turn))
        other = len(board.pieces(piece_type, not board.turn))
        total += (own - other) * value * 100
    return total


class MaterialEngine:
    """Поиск на один полуход: мат в 1 или лучший размен по материалу. Зевок ферзя
    (2... Qh4?? 3. Nxh4) для него — зевок, в отличие от `FakeEngine`."""

    async def analyse(
        self,
        board: chess.Board,
        *,
        depth: int,
        multipv: int,
        exclude: Collection[chess.Move] = (),
    ) -> PositionEval:
        scored: list[tuple[int, str, chess.Move, Score]] = []
        for move in board.legal_moves:
            if move in exclude:
                continue
            board.push(move)
            mate = board.is_checkmate()
            value = -_material(board)
            board.pop()
            score: Score = Mate(1) if mate else Cp(value)
            scored.append((100_000 if mate else value, move.uci(), move, score))
        scored.sort(key=lambda item: (-item[0], item[1]))
        lines = tuple(EngineLine(score=score, pv=(move,)) for _, _, move, score in scored[:multipv])
        return PositionEval(score=lines[0].score, lines=lines, depth=depth)


class InlineRunner:
    """Анализ прямо в процессе: задача воркера с фейковым движком (`ctx` как у ARQ)."""

    def __init__(self, ctx: dict[str, Any]) -> None:
        self.ctx = ctx
        self.runs: list[uuid.UUID] = []

    async def run(self, analysis_id: uuid.UUID) -> None:
        self.runs.append(analysis_id)
        await analyze_game(self.ctx, str(analysis_id))


class HangingRunner:
    """Анализ, который не успевает за BOT_ANALYSIS_TIMEOUT_S."""

    async def run(self, analysis_id: uuid.UUID) -> None:
        await asyncio.Event().wait()
