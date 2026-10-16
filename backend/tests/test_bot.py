"""Telegram-бот сквозь: событие Telegram → фейковые Lichess / Chess.com → анализ задачей
воркера на фейковом движке → ответ с точностью, ошибками и публичной ссылкой."""

import asyncio
import re
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy import delete, func, select

from app.bot import __main__ as bot_main
from app.bot.handler import BotHandler, parse_command
from app.bot.report import time_control_label
from app.bot.runner import AnalysisRunner, QueueRunner, QueueUnavailableError
from app.bot.service import ReviewService
from app.bot.telegram import TelegramClient, TelegramError, parse_update
from app.core.config import Settings
from app.core.rates import Rate
from app.db.models import Analysis, AnalysisStatus, Game, TelegramChat
from app.db.session import Database
from app.explain.service import Explainer
from app.workers.progress import ProgressEvent, publish
from tests.bot_fakes import (
    API_URL,
    TOKEN,
    FakeTelegram,
    HangingRunner,
    InlineRunner,
    MaterialEngine,
    callback_update,
    message_update,
)
from tests.conftest import api_client
from tests.import_fakes import FAST_RETRY, FakeChessCom, FakeLichess, make_pgn, mock_client, routed
from tests.test_api_explain import insert_review

pytestmark = pytest.mark.integration

BLUNDER_MOVES = "1. e4 e5 2. Nf3 Qh4 3. Nxh4 d6"


@dataclass
class Bot:
    handler: BotHandler
    telegram: FakeTelegram
    lichess: FakeLichess
    chesscom: FakeChessCom
    runner: InlineRunner
    client: TelegramClient

    async def send(self, update: dict[str, Any]) -> None:
        await self.handler.handle(parse_update(update))


def add_lichess_game(lichess: FakeLichess, white: str, black: str, moves: str) -> None:
    games = lichess.users.setdefault(white.lower(), [])
    games.insert(
        0,
        {
            "id": f"lc{len(games):04d}",
            "variant": "standard",
            "createdAt": 1_790_000_000_000 + len(games),
            "pgn": make_pgn(white, black, moves=moves, result="1-0"),
        },
    )
    lichess.users.setdefault(black.lower(), games)


@pytest.fixture
async def chats(db: Database) -> None:
    async with db.sessionmaker() as session:
        await session.execute(delete(TelegramChat))
        await session.commit()


def make_bot(
    settings: Settings,
    db: Database,
    redis: Redis,
    *,
    runner: AnalysisRunner | None = None,
) -> Bot:
    telegram, lichess, chesscom = FakeTelegram(), FakeLichess(), FakeChessCom()
    client = TelegramClient(
        TOKEN, api_url=API_URL, http=httpx.AsyncClient(transport=httpx.MockTransport(telegram))
    )
    ctx = {
        "settings": settings,
        "db": db,
        "redis": redis,
        "engine": MaterialEngine(),
        "engine_version": "Material 1.0",
    }
    inline = InlineRunner(ctx)
    service = ReviewService(
        settings,
        db,
        mock_client(routed(lichess, chesscom)),
        runner or inline,
        Explainer(None, db.sessionmaker),
        policy=FAST_RETRY,
    )
    handler = BotHandler(settings, client, service, db, redis)
    return Bot(handler, telegram, lichess, chesscom, inline, client)


@pytest.fixture
def bot(settings: Settings, db: Database, redis: Redis, chats: None) -> Bot:
    return make_bot(settings, db, redis)


def share_token(text: str) -> str:
    match = re.search(r"/share/([A-Za-z0-9_-]+)", text)
    assert match is not None, text
    return match[1]


async def test_lichess_nick_gets_review_with_mistakes_and_link(
    bot: Bot, db: Database, settings: Settings
) -> None:
    add_lichess_game(bot.lichess, "Alice", "Bob", BLUNDER_MOVES)

    await bot.send(message_update("/lichess Bob"))

    # Сначала «Анализирую…», затем это же сообщение заменяется результатом.
    (progress,) = bot.telegram.sent("sendMessage")
    assert progress["text"].startswith("Анализирую последнюю партию Bob на Lichess")
    assert progress["parse_mode"] == "HTML"
    assert progress["link_preview_options"] == {"is_disabled": True}
    (result,) = bot.telegram.sent("editMessageText")
    assert result["message_id"] == bot.telegram.next_message_id
    text = result["text"]
    assert "<b>Alice (1500) — Bob (1600)</b>" in text
    assert "1-0, поражение Bob · Блиц 5+3 · Lichess · 01.10.2026" in text
    assert re.search(r"Точность: Alice \d+\.\d · Bob \d+\.\d", text)
    assert "Рейтинг партии: Alice" in text
    assert "<b>Ключевые ошибки Bob</b>" in text
    token = share_token(text)
    assert f'<a href="http://localhost:3000/share/{token}?ply=4">2... Qh4??</a> — зевок' in text
    assert "<b>Итог</b>" in text
    assert f'<a href="http://localhost:3000/share/{token}">Открыть полный разбор</a>' in text
    # Анализ — задача воркера; партия — у пользователя бота, цвет — по нику.
    assert len(bot.runner.runs) == 1
    async with db.sessionmaker() as session:
        game = await session.scalar(select(Game).where(Game.share_token == token))
        assert game is not None
        assert game.user_id == settings.bot_user_id
        assert game.user_color == "black"
        chat = await session.get(TelegramChat, 501)
        assert chat is not None
        assert chat.last_request_at is not None
    # Lichess — только последняя партия.
    assert bot.lichess.requests[0].url.params["max"] == "1"

    # Ссылка открывается без входа.
    async with api_client(settings, anonymous=True) as anonymous:
        shared = await anonymous.get(f"/api/v1/shared/{token}")
    assert shared.status_code == 200
    assert shared.json()["analysis"]["status"] == "done"


async def test_repeat_request_reuses_game_and_analysis(bot: Bot, db: Database) -> None:
    add_lichess_game(bot.lichess, "Alice", "Bob", BLUNDER_MOVES)

    await bot.send(message_update("/lichess bob"))
    first = bot.telegram.last_text
    # Соперник спрашивает о той же партии: она уже разобрана, ошибки — уже его.
    await bot.send(message_update("/lichess alice", update_id=2))
    second = bot.telegram.last_text

    assert len(bot.runner.runs) == 1
    assert share_token(first) == share_token(second)
    assert "1-0, победа Alice" in second
    assert "Серьёзных ошибок у Alice нет." in second
    async with db.sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(Game)) == 1
        assert await session.scalar(select(func.count()).select_from(Analysis)) == 1


async def test_chesscom_falls_back_to_previous_month(bot: Bot) -> None:
    chesscom = bot.chesscom
    # Последний месяц — только Chess960, партия — в предыдущем; официальная точность есть.
    chesscom.add_game("Carol", 2026, 10, 2, rules="chess960")
    chesscom.add_game("Carol", 2026, 9, 1, black="Dave", accuracies={"white": 91.4, "black": 55})
    chesscom.users["carol"][(2026, 9)][0]["pgn"] = make_pgn(
        "Carol", "Dave", moves=BLUNDER_MOVES, result="1-0"
    )
    chesscom.add_game("Carol", 2026, 7, 0)

    await bot.send(message_update("/chesscom Carol"))

    text = bot.telegram.last_text
    assert "Chess.com" in text
    assert "Точность: Carol 91.4 · Dave 55.0" in text
    assert "1-0, победа Carol" in text
    # Ошибок у Carol нет; июль не запрашивался — только два последних архива.
    assert "Серьёзных ошибок у Carol нет." in text
    paths = [request.url.path for request in chesscom.requests]
    assert paths == [
        "/pub/player/carol/games/archives",
        "/pub/player/carol/games/2026/10",
        "/pub/player/carol/games/2026/09",
    ]


async def test_plain_nick_offers_sources_then_callback(bot: Bot) -> None:
    add_lichess_game(bot.lichess, "Alice", "Bob", BLUNDER_MOVES)

    await bot.send(message_update("Bob"))
    (offer,) = bot.telegram.sent("sendMessage")
    assert offer["text"] == "Где искать партии Bob?"
    buttons = offer["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in buttons] == ["lichess:Bob", "chesscom:Bob"]
    assert [b["text"] for b in buttons] == ["Lichess", "Chess.com"]

    offer_id = bot.telegram.next_message_id
    await bot.send(callback_update("lichess:Bob", message_id=offer_id))

    (answer,) = bot.telegram.sent("answerCallbackQuery")
    assert answer["callback_query_id"] == "cb-1"
    edits = bot.telegram.sent("editMessageText")
    # Сообщение с кнопками → «Анализирую…» (кнопки убираются) → результат.
    assert [edit["message_id"] for edit in edits] == [offer_id, offer_id]
    assert edits[0]["text"].startswith("Анализирую")
    assert "reply_markup" not in edits[0]
    assert "2... Qh4??" in edits[1]["text"]
    assert len(bot.telegram.sent("sendMessage")) == 1


async def test_invalid_input_and_commands(bot: Bot) -> None:
    await bot.send(message_update("not a nick!"))
    await bot.send(message_update("/lichess"))
    await bot.send(message_update("/chesscom bad/nick"))
    await bot.send(message_update("/unknown"))
    await bot.send(callback_update("lichess:bad nick", message_id=1))
    group = message_update("Bob")
    group["message"]["chat"] = {"id": -100, "type": "group"}
    await bot.send(group)

    texts = [payload["text"] for payload in bot.telegram.sent()]
    assert texts[0].startswith("Не похоже на ник")
    assert texts[1] == "Укажите ник: /lichess &lt;ник&gt;."
    assert texts[2].startswith("Не похоже на ник")
    assert texts[3] == "Не знаю такой команды. Список — /help."
    # Кривой callback — только ответ на нажатие; реплика в группе — без ответа.
    assert len(texts) == 4
    assert len(bot.telegram.sent("answerCallbackQuery")) == 1
    assert bot.runner.runs == []


async def test_language_from_client_and_lang_command(bot: Bot, db: Database) -> None:
    await bot.send(message_update("/start", chat_id=777, language_code="de"))
    assert bot.telegram.last_text.startswith("Hi! Send me a Lichess or Chess.com username")

    await bot.send(message_update("/lang xx", chat_id=777, language_code="de"))
    assert bot.telegram.last_text == "Language: /lang ru or /lang en."
    await bot.send(message_update("/lang@review_test_bot RU", chat_id=777, language_code="de"))
    assert bot.telegram.last_text == "Язык ответов: русский."
    # Язык клиента больше не важен — у чата свой.
    await bot.send(message_update("/help", chat_id=777, language_code="en"))
    assert bot.telegram.last_text.startswith("Привет!")

    async with db.sessionmaker() as session:
        chat = await session.get(TelegramChat, 777)
    assert chat is not None
    assert chat.lang == "ru"


async def test_english_report(bot: Bot) -> None:
    add_lichess_game(bot.lichess, "Alice", "Bob", BLUNDER_MOVES)

    await bot.send(message_update("/lichess Bob", language_code="en-US"))

    text = bot.telegram.last_text
    assert "1-0, Bob lost · Blitz 5+3 · Lichess" in text
    assert "<b>Key mistakes by Bob</b>" in text
    assert "2... Qh4??</a> — blunder" in text
    assert "<b>Summary</b>" in text
    assert "Open the full review" in text


async def test_source_errors_are_friendly(bot: Bot) -> None:
    bot.lichess.users["empty"] = []

    await bot.send(message_update("/lichess Nobody"))
    not_found = bot.telegram.last_text
    await bot.send(message_update("/lichess empty"))
    no_games = bot.telegram.last_text
    bot.lichess.failures.extend(httpx.Response(503) for _ in range(3))
    await bot.send(message_update("/lichess empty"))
    unavailable = bot.telegram.last_text

    assert not_found == "Пользователь Nobody не найден на Lichess."
    assert no_games == "У empty на Lichess не нашлось партий в классические шахматы."
    assert unavailable.startswith("Lichess")
    assert bot.runner.runs == []


async def test_rate_limit_per_chat(
    settings: Settings, db: Database, redis: Redis, chats: None
) -> None:
    rules = settings.model_copy(
        update={"rate_limit_enabled": True, "rate_limit_bot": Rate(1, 3600)}
    )
    bot = make_bot(rules, db, redis)
    bot.lichess.users["empty"] = []

    await bot.send(message_update("/lichess empty"))
    await bot.send(message_update("/lichess empty"))
    limited = bot.telegram.last_text
    # Другой чат — свой счётчик; справка лимит не тратит.
    await bot.send(message_update("/help"))
    await bot.send(message_update("/lichess empty", chat_id=502))

    assert re.fullmatch(
        r"Слишком много запросов из этого чата\. Попробуйте через \d+ мин\.", limited
    )
    assert bot.telegram.sent()[-1]["text"].startswith("У empty на Lichess")
    assert len(bot.lichess.requests) == 2


async def test_slow_analysis_replies_with_link(
    settings: Settings, db: Database, redis: Redis, chats: None
) -> None:
    impatient = settings.model_copy(update={"bot_analysis_timeout_s": 0.05})
    bot = make_bot(impatient, db, redis, runner=HangingRunner())
    add_lichess_game(bot.lichess, "Alice", "Bob", BLUNDER_MOVES)

    await bot.send(message_update("/lichess Bob"))

    text = bot.telegram.last_text
    assert "Анализ ещё идёт — результат появится по ссылке." in text
    assert "/share/" in text
    assert "Точность" not in text


async def test_reply_falls_back_to_new_message(bot: Bot) -> None:
    bot.lichess.users["empty"] = []
    bot.telegram.failures["editMessageText"] = "Bad Request: message to edit not found"

    await bot.send(message_update("/lichess empty"))

    sent = bot.telegram.sent("sendMessage")
    assert [payload["text"][:9] for payload in sent] == ["Анализиру", "У empty н"]


async def test_queue_runner_waits_for_final_event(db: Database, redis: Redis) -> None:
    """Боевой запуск: задача в очереди ARQ, ответ — по событию в канале прогресса."""
    analysis_id, _ = await insert_review(db, Settings().bot_user_id, AnalysisStatus.QUEUED)

    class Queue:
        def __init__(self, redis: Redis) -> None:
            self.redis = redis
            self.jobs: list[tuple[Any, ...]] = []
            self.enqueued = asyncio.Event()

        def pubsub(self) -> Any:
            return self.redis.pubsub()

        async def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
            self.jobs.append(args)
            self.enqueued.set()

    queue = Queue(redis)
    runner = QueueRunner(queue, db)  # type: ignore[arg-type]
    task = asyncio.create_task(runner.run(analysis_id))
    await asyncio.wait_for(queue.enqueued.wait(), timeout=5)
    await publish(redis, analysis_id, ProgressEvent(status=AnalysisStatus.RUNNING, done=1, total=9))
    await publish(redis, analysis_id, ProgressEvent(status=AnalysisStatus.DONE, done=9, total=9))
    await asyncio.wait_for(task, timeout=5)

    assert queue.jobs == [("analyze_game", str(analysis_id))]


async def test_queue_runner_marks_failed_without_queue(db: Database, redis: Redis) -> None:
    analysis_id, _ = await insert_review(db, Settings().bot_user_id, AnalysisStatus.QUEUED)

    class BrokenQueue:
        def pubsub(self) -> Any:
            return redis.pubsub()

        async def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
            raise ConnectionError("redis down")

    with pytest.raises(QueueUnavailableError):
        await QueueRunner(BrokenQueue(), db).run(analysis_id)  # type: ignore[arg-type]
    async with db.sessionmaker() as session:
        analysis = await session.get(Analysis, analysis_id)
    assert analysis is not None
    assert analysis.status == AnalysisStatus.FAILED
    assert analysis.error_code == "enqueue_failed"


async def test_poll_loop_dispatches_and_acknowledges(bot: Bot) -> None:
    bot.telegram.updates = [[message_update("/start", update_id=41)]]
    stop = asyncio.Event()

    task = asyncio.create_task(bot_main.poll(bot.client, bot.handler, stop))
    await asyncio.wait_for(bot.telegram.message_sent.wait(), timeout=5)
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    polls = bot.telegram.sent("getUpdates")
    assert "offset" not in polls[0]
    assert polls[0]["allowed_updates"] == ["message", "callback_query"]
    # Последний вызов подтверждает обработанное событие.
    assert polls[-1]["offset"] == 42
    assert bot.telegram.last_text.startswith("Привет!")


def test_main_requires_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(bot_main, "get_settings", lambda: Settings(telegram_bot_token=None))

    assert bot_main.main() == 2
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().err


async def test_run_stops_when_telegram_is_unreachable(settings: Settings) -> None:
    broken = settings.model_copy(
        update={"telegram_bot_token": SecretStr("1:x"), "telegram_api_url": "http://127.0.0.1:9"}
    )

    assert await bot_main.run(broken) == 1


async def test_telegram_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getMe"):
            return httpx.Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "description": "Too Many Requests",
                    "parameters": {"retry_after": 7},
                },
            )
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(502, text="<html>Bad Gateway</html>")
        raise httpx.ConnectError("boom")

    client = TelegramClient(
        TOKEN, api_url=API_URL, http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(TelegramError) as limited:
        await client.get_me()
    with pytest.raises(TelegramError) as gateway:
        await client.get_updates(None)
    with pytest.raises(TelegramError) as network:
        await client.send_message(1, "hi")

    assert (limited.value.error_code, limited.value.retry_after) == (429, 7)
    assert gateway.value.error_code == 502
    assert network.value.error_code is None
    # Токен (часть URL) не попадает в текст ошибки.
    assert TOKEN not in str(network.value)


def test_parse_command_and_time_control() -> None:
    assert parse_command("/lichess@my_bot  DrNykterstein ") == ("lichess", "DrNykterstein")
    assert parse_command("/START") == ("start", "")
    assert parse_command("hello") is None
    assert time_control_label("180+2", "ru") == "Блиц 3+2"
    assert time_control_label("30+0", "en") == "Bullet 0.5+0"
    assert time_control_label("1/259200", "ru") == "По переписке, 3 дн. на ход"
    assert time_control_label("-", "ru") is None
    assert time_control_label(None, "en") is None
    assert parse_update({"update_id": 5, "message": {"oops": 1}}).message is None
