"""Обработка событий Telegram: команды, ник с выбором площадки, кнопки.

- `/start`, `/help` — справка; `/lang ru|en` — язык ответов чата;
- `/lichess <ник>`, `/chesscom <ник>` — разбор последней партии;
- просто ник — кнопки [Lichess] [Chess.com] (callback `lichess:<ник>` / `chesscom:<ник>`).

Язык чата хранится в `telegram_chats` (новый чат — по `language_code` клиента).
Разбор — не больше `RATE_LIMIT_BOT` на чат; сразу отвечает «Анализирую…» и потом
заменяет это сообщение результатом. Одновременных разборов — `BOT_MAX_CONCURRENCY`.
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

import structlog
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from app.api.errors import ApiError
from app.api.ratelimit import hit
from app.bot.report import format_report
from app.bot.runner import QueueUnavailableError
from app.bot.service import BotError, ReviewService
from app.bot.telegram import TelegramClient, TelegramError, TgMessage, TgUser, Update
from app.bot.texts import SOURCE_NAMES, chat_lang, error_text, text
from app.core.config import Settings
from app.core.errors import ErrorCode
from app.db.models import GameSource, TelegramChat
from app.db.session import Database
from app.explain.templates import Lang
from app.importers.http import SourceError

log = structlog.get_logger(__name__)

# Тот же формат ника, что `Username` в `app/api/schemas.py`.
NICK_RE = re.compile(r"^[A-Za-z0-9_-]{2,50}$")
SOURCE_COMMANDS: dict[str, GameSource] = {
    "lichess": GameSource.LICHESS,
    "chesscom": GameSource.CHESSCOM,
}
LANGS: tuple[Lang, ...] = ("ru", "en")


def source_keyboard(nick: str) -> dict[str, Any]:
    """Кнопки выбора площадки; callback_data ≤ 64 байт (ник ≤ 50)."""
    return {
        "inline_keyboard": [
            [
                {"text": SOURCE_NAMES[source], "callback_data": f"{command}:{nick}"}
                for command, source in SOURCE_COMMANDS.items()
            ]
        ]
    }


def parse_command(message_text: str) -> tuple[str, str] | None:
    """`/lichess@MyBot  nick` → ("lichess", "nick"); не команда — None."""
    if not message_text.startswith("/"):
        return None
    head, _, rest = message_text.strip().partition(" ")
    command = head[1:].split("@", 1)[0].lower()
    return command, rest.strip()


class BotHandler:
    def __init__(
        self,
        settings: Settings,
        telegram: TelegramClient,
        service: ReviewService,
        db: Database,
        redis: Redis,
    ) -> None:
        self.settings = settings
        self.telegram = telegram
        self.service = service
        self.db = db
        self.redis = redis
        self._slots = asyncio.Semaphore(settings.bot_max_concurrency)

    async def handle(self, update: Update) -> None:
        """Одно событие; ошибки логируются, а не роняют цикл опроса."""
        log_ = log.bind(update_id=update.update_id)
        try:
            if update.callback_query is not None:
                await self._on_callback(update)
            elif update.message is not None and update.message.text:
                await self._on_message(update.message)
        except TelegramError as exc:
            log_.warning("bot.telegram_failed", method=exc.method, error=exc.description)
        except Exception:
            log_.exception("bot.update_failed")

    async def _on_message(self, message: TgMessage) -> None:
        chat_id = message.chat.id
        lang = await self._chat_lang(chat_id, message.from_user)
        message_text = (message.text or "").strip()
        parsed = parse_command(message_text)
        if parsed is None:
            if message.chat.type != "private":
                # В группах отвечаем только на команды, а не на любую реплику.
                return
            if NICK_RE.match(message_text):
                await self.telegram.send_message(
                    chat_id,
                    text("choose_source", lang, nick=message_text),
                    reply_markup=source_keyboard(message_text),
                )
            else:
                await self.telegram.send_message(chat_id, text("bad_nick", lang))
            return

        command, argument = parsed
        if command in ("start", "help"):
            await self.telegram.send_message(chat_id, text("start", lang))
        elif command == "lang":
            await self._set_lang(chat_id, argument.lower(), lang)
        elif command in SOURCE_COMMANDS:
            if not argument:
                await self.telegram.send_message(chat_id, text("usage", lang, command=command))
            elif not NICK_RE.match(argument):
                await self.telegram.send_message(chat_id, text("bad_nick", lang))
            else:
                await self._review(chat_id, lang, SOURCE_COMMANDS[command], argument)
        else:
            await self.telegram.send_message(chat_id, text("unknown_command", lang))

    async def _on_callback(self, update: Update) -> None:
        query = update.callback_query
        assert query is not None
        # Ответ на нажатие — сразу, иначе у кнопки крутятся часики.
        await self.telegram.answer_callback_query(query.id)
        command, _, nick = (query.data or "").partition(":")
        message = query.message
        if message is None or command not in SOURCE_COMMANDS or not NICK_RE.match(nick):
            return
        lang = await self._chat_lang(message.chat.id, query.from_user)
        # Сообщение с кнопками становится «Анализирую…», а потом — результатом.
        await self._review(
            message.chat.id, lang, SOURCE_COMMANDS[command], nick, message_id=message.message_id
        )

    async def _set_lang(self, chat_id: int, value: str, current: Lang) -> None:
        if value not in LANGS:
            await self.telegram.send_message(chat_id, text("lang_usage", current))
            return
        lang: Lang = "en" if value == "en" else "ru"
        async with self.db.sessionmaker() as session:
            await session.execute(
                update(TelegramChat).where(TelegramChat.chat_id == chat_id).values(lang=lang)
            )
            await session.commit()
        await self.telegram.send_message(chat_id, text("lang_set", lang))

    async def _chat_lang(self, chat_id: int, user: TgUser | None) -> Lang:
        """Язык чата; новый чат запоминается с языком клиента Telegram."""
        initial = chat_lang(user.language_code if user else None)
        async with self.db.sessionmaker() as session:
            stmt = insert(TelegramChat).values(chat_id=chat_id, lang=initial)
            # DO UPDATE без изменений — чтобы RETURNING вернул и существующую строку.
            stmt = stmt.on_conflict_do_update(
                index_elements=[TelegramChat.chat_id], set_={"lang": TelegramChat.lang}
            )
            stored = await session.scalar(stmt.returning(TelegramChat.lang))
            await session.commit()
        return "en" if stored == "en" else "ru"

    async def _review(
        self,
        chat_id: int,
        lang: Lang,
        source: GameSource,
        nick: str,
        *,
        message_id: int | None = None,
    ) -> None:
        log_ = log.bind(chat_id=chat_id, source=source, nick=nick)
        try:
            await hit(self.redis, self.settings, "bot", str(chat_id))
        except ApiError as exc:
            retry_after = int(exc.params.get("retry_after", 60))
            minutes = max(1, -(-retry_after // 60))
            await self._reply(chat_id, message_id, text("rate_limited", lang, minutes=minutes))
            return
        await self._touch(chat_id)

        progress = text("analyzing", lang, nick=nick, source=SOURCE_NAMES[source])
        message_id = await self._reply(chat_id, message_id, progress)
        log_.info("bot.review_started")
        try:
            async with self._slots:
                report = await self.service.review_last_game(source, nick, lang)
            reply = format_report(report, lang)
            log_.info("bot.review_done", status=report.status)
        except (BotError, SourceError) as exc:
            log_.info("bot.review_failed", code=exc.code, error=str(exc))
            reply = error_text(exc.code, lang, nick=nick, source=SOURCE_NAMES[source])
        except QueueUnavailableError:
            reply = error_text(ErrorCode.QUEUE_UNAVAILABLE, lang)
        except Exception:
            log_.exception("bot.review_crashed")
            reply = error_text(ErrorCode.INTERNAL, lang)
        await self._reply(chat_id, message_id, reply)

    async def _reply(self, chat_id: int, message_id: int | None, reply: str) -> int:
        """Заменить сообщение бота (`message_id`) текстом; не вышло — новое сообщение."""
        if message_id is not None:
            try:
                await self.telegram.edit_message_text(chat_id, message_id, reply)
                return message_id
            except TelegramError as exc:
                log.warning("bot.edit_failed", chat_id=chat_id, error=exc.description)
        sent = await self.telegram.send_message(chat_id, reply)
        return sent.message_id

    async def _touch(self, chat_id: int) -> None:
        async with self.db.sessionmaker() as session:
            await session.execute(
                update(TelegramChat)
                .where(TelegramChat.chat_id == chat_id)
                .values(last_request_at=datetime.now(UTC))
            )
            await session.commit()
