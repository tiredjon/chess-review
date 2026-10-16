"""Тексты Telegram-бота (RU / EN). Разметка — HTML Telegram: параметры экранируются."""

import html
from typing import Any

from app.core.errors import ErrorCode
from app.db.models import GameSource
from app.explain.templates import Lang

SOURCE_NAMES: dict[GameSource, str] = {
    GameSource.LICHESS: "Lichess",
    GameSource.CHESSCOM: "Chess.com",
    GameSource.PGN: "PGN",
}

TEXTS: dict[str, dict[Lang, str]] = {
    "start": {
        "ru": (
            "Привет! Пришлите ник Lichess или Chess.com — я разберу последнюю партию: "
            "точность, ключевые ошибки и ссылка на полный разбор.\n\n"
            "/lichess &lt;ник&gt; — партия с Lichess\n"
            "/chesscom &lt;ник&gt; — партия с Chess.com\n"
            "/lang ru|en — язык ответов"
        ),
        "en": (
            "Hi! Send me a Lichess or Chess.com username and I will review the latest game: "
            "accuracy, key mistakes and a link to the full review.\n\n"
            "/lichess &lt;username&gt; — a game from Lichess\n"
            "/chesscom &lt;username&gt; — a game from Chess.com\n"
            "/lang ru|en — reply language"
        ),
    },
    "lang_set": {"ru": "Язык ответов: русский.", "en": "Reply language: English."},
    "lang_usage": {"ru": "Язык: /lang ru или /lang en.", "en": "Language: /lang ru or /lang en."},
    "usage": {
        "ru": "Укажите ник: /{command} &lt;ник&gt;.",
        "en": "Add a username: /{command} &lt;username&gt;.",
    },
    "bad_nick": {
        "ru": (
            "Не похоже на ник: латиница, цифры, «_» и «-», от 2 до 50 символов. Подробнее — /help."
        ),
        "en": (
            "That doesn't look like a username: Latin letters, digits, “_” and “-”, "
            "2 to 50 characters. See /help."
        ),
    },
    "unknown_command": {
        "ru": "Не знаю такой команды. Список — /help.",
        "en": "Unknown command. See /help.",
    },
    "choose_source": {
        "ru": "Где искать партии {nick}?",
        "en": "Where should I look for {nick}'s games?",
    },
    "analyzing": {
        "ru": "Анализирую последнюю партию {nick} на {source}… Обычно это занимает минуту-две.",
        "en": "Analysing {nick}'s latest game on {source}… It usually takes a minute or two.",
    },
    "rate_limited": {
        "ru": "Слишком много запросов из этого чата. Попробуйте через {minutes} мин.",
        "en": "Too many requests from this chat. Try again in {minutes} min.",
    },
    "pending": {
        "ru": "Анализ ещё идёт — результат появится по ссылке.",
        "en": "The analysis is still running — the result will appear at the link.",
    },
    "analysis_failed": {
        "ru": "Не получилось проанализировать партию. Попробуйте позже.",
        "en": "Couldn't analyse the game. Please try again later.",
    },
    # Ошибки по коду (`app/core/errors.py`).
    ErrorCode.SOURCE_USER_NOT_FOUND: {
        "ru": "Пользователь {nick} не найден на {source}.",
        "en": "User {nick} was not found on {source}.",
    },
    ErrorCode.SOURCE_NO_GAMES: {
        "ru": "У {nick} на {source} не нашлось партий в классические шахматы.",
        "en": "{nick} has no standard chess games on {source}.",
    },
    ErrorCode.SOURCE_RATE_LIMITED: {
        "ru": "{source} просит подождать. Попробуйте через пару минут.",
        "en": "{source} asks us to slow down. Try again in a couple of minutes.",
    },
    ErrorCode.SOURCE_UNAVAILABLE: {
        "ru": "{source} сейчас недоступен. Попробуйте позже.",
        "en": "{source} is unavailable right now. Please try again later.",
    },
    ErrorCode.SOURCE_BAD_RESPONSE: {
        "ru": "{source} ответил что-то непонятное. Попробуйте позже.",
        "en": "{source} returned an unexpected response. Please try again later.",
    },
    ErrorCode.QUEUE_UNAVAILABLE: {
        "ru": "Анализ сейчас недоступен. Попробуйте позже.",
        "en": "Analysis is unavailable right now. Please try again later.",
    },
    ErrorCode.INTERNAL: {
        "ru": "Что-то пошло не так. Попробуйте позже.",
        "en": "Something went wrong. Please try again later.",
    },
    # Отчёт о партии.
    "accuracy": {"ru": "Точность", "en": "Accuracy"},
    "game_rating": {"ru": "Рейтинг партии", "en": "Game rating"},
    "opening": {"ru": "Дебют", "en": "Opening"},
    "key_mistakes": {"ru": "Ключевые ошибки {name}", "en": "Key mistakes by {name}"},
    "no_mistakes": {
        "ru": "Серьёзных ошибок у {name} нет.",
        "en": "No serious mistakes by {name}.",
    },
    "better": {"ru": "лучше было {san}", "en": "better was {san}"},
    "summary": {"ru": "Итог", "en": "Summary"},
    "open_review": {"ru": "Открыть полный разбор", "en": "Open the full review"},
    "win": {"ru": "победа {name}", "en": "{name} won"},
    "loss": {"ru": "поражение {name}", "en": "{name} lost"},
    "draw": {"ru": "ничья", "en": "draw"},
    "daily": {"ru": "{days} дн. на ход", "en": "{days} d/move"},
    "blunder": {"ru": "зевок", "en": "blunder"},
    "mistake": {"ru": "ошибка", "en": "mistake"},
    "miss": {"ru": "упущенная возможность", "en": "missed chance"},
    "time_bullet": {"ru": "Пуля", "en": "Bullet"},
    "time_blitz": {"ru": "Блиц", "en": "Blitz"},
    "time_rapid": {"ru": "Рапид", "en": "Rapid"},
    "time_daily": {"ru": "По переписке", "en": "Daily"},
}


def text(key: str, lang: Lang, **params: Any) -> str:
    """Текст на языке чата; параметры экранируются для HTML Telegram."""
    template = TEXTS[key][lang]
    return template.format(
        **{name: html.escape(str(value), quote=False) for name, value in params.items()}
    )


def error_text(code: str, lang: Lang, **params: Any) -> str:
    """Понятная ошибка по коду; неизвестный код — общая ошибка."""
    return text(code if code in TEXTS else ErrorCode.INTERNAL, lang, **params)


def chat_lang(language_code: str | None) -> Lang:
    """Язык нового чата по языку клиента Telegram: русский — ru, иначе en."""
    return "ru" if (language_code or "").lower().startswith("ru") else "en"
