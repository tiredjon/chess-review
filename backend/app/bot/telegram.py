"""Минимальный клиент Telegram Bot API на httpx: long polling и сообщения.

Токен бота — часть URL (`/bot<token>/<метод>`), поэтому URL запросов не логируются
и не попадают в тексты ошибок (логгер `httpx` бот приглушает в `__main__`).
"""

from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

log = structlog.get_logger(__name__)

# Long polling: столько Telegram держит `getUpdates` без новых событий.
POLL_TIMEOUT_S = 30
# Запас поверх таймаута long polling до таймаута HTTP.
POLL_SLACK_S = 10
REQUEST_TIMEOUT_S = 20.0
# Ограничение Telegram на длину текста сообщения.
MESSAGE_MAX_CHARS = 4096
ALLOWED_UPDATES = ("message", "callback_query")


class TelegramError(Exception):
    """Ошибка Bot API или сети. `error_code` — HTTP-код Telegram (None — сеть),
    `retry_after` — пауза при 429."""

    def __init__(
        self,
        method: str,
        description: str,
        *,
        error_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(f"{method}: {description}")
        self.method = method
        self.description = description
        self.error_code = error_code
        self.retry_after = retry_after

    @property
    def not_modified(self) -> bool:
        """editMessageText с тем же текстом — не ошибка."""
        return "message is not modified" in self.description


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class TgUser(_Model):
    id: int
    language_code: str | None = None


class TgChat(_Model):
    id: int
    type: str = "private"


class TgMessage(_Model):
    message_id: int
    chat: TgChat
    from_user: TgUser | None = Field(default=None, alias="from")
    text: str | None = None


class TgCallbackQuery(_Model):
    id: str
    from_user: TgUser = Field(alias="from")
    # Сообщение с кнопкой; у очень старых сообщений Telegram его не присылает.
    message: TgMessage | None = None
    data: str | None = None


class Update(_Model):
    update_id: int
    message: TgMessage | None = None
    callback_query: TgCallbackQuery | None = None


def parse_update(raw: dict[str, Any]) -> Update:
    """Событие; непонятное — пустое событие с тем же id (offset всё равно сдвигается)."""
    try:
        return Update.model_validate(raw)
    except ValidationError:
        log.warning("telegram.bad_update", update_id=raw.get("update_id"))
        return Update(update_id=int(raw.get("update_id", 0)))


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.telegram.org",
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = f"{api_url.rstrip('/')}/bot{token}"
        self._http = http or httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S)
        self._own_http = http is None

    async def aclose(self) -> None:
        if self._own_http:
            await self._http.aclose()

    async def call(
        self, method: str, payload: dict[str, Any], *, http_timeout_s: float = REQUEST_TIMEOUT_S
    ) -> Any:
        """Метод Bot API; ответ `ok: false` или сбой сети — TelegramError."""
        try:
            response = await self._http.post(
                f"{self._base}/{method}",
                json=payload,
                timeout=http_timeout_s,
            )
        except httpx.HTTPError as exc:
            # Не str(exc): в тексте может оказаться URL с токеном.
            raise TelegramError(method, f"сеть ({type(exc).__name__})") from exc
        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise TelegramError(
                method, f"ответ {response.status_code}", error_code=response.status_code
            )
        if not data.get("ok"):
            parameters = data.get("parameters") or {}
            raise TelegramError(
                method,
                str(data.get("description") or f"ответ {response.status_code}"),
                error_code=data.get("error_code") or response.status_code,
                retry_after=parameters.get("retry_after"),
            )
        return data.get("result")

    async def get_me(self) -> dict[str, Any]:
        result: dict[str, Any] = await self.call("getMe", {})
        return result

    async def get_updates(self, offset: int | None, poll_s: int = POLL_TIMEOUT_S) -> list[Update]:
        """Новые события после `offset` (long polling); вызов с offset подтверждает
        полученные раньше."""
        payload: dict[str, Any] = {"timeout": poll_s, "allowed_updates": list(ALLOWED_UPDATES)}
        if offset is not None:
            payload["offset"] = offset
        result = await self.call("getUpdates", payload, http_timeout_s=poll_s + POLL_SLACK_S)
        return [parse_update(raw) for raw in result or [] if isinstance(raw, dict)]

    async def send_message(
        self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None
    ) -> TgMessage:
        """Сообщение в HTML-разметке Telegram, без превью ссылок."""
        payload = _text_payload(text, reply_markup)
        payload["chat_id"] = chat_id
        return TgMessage.model_validate(await self.call("sendMessage", payload))

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        """Замена текста сообщения (и клавиатуры: без `reply_markup` она убирается)."""
        payload = _text_payload(text, reply_markup)
        payload.update(chat_id=chat_id, message_id=message_id)
        try:
            await self.call("editMessageText", payload)
        except TelegramError as exc:
            if not exc.not_modified:
                raise

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self.call("answerCallbackQuery", payload)


def _text_payload(text: str, reply_markup: dict[str, Any] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return payload
