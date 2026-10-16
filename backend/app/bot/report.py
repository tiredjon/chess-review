"""Ответ бота о партии: шапка, точность, ключевые ошибки, итог и ссылка (HTML Telegram).

Чистые функции: данные собирает `service.py`, здесь — только выбор ошибок и текст.
"""

import dataclasses
import html
import re
from collections.abc import Sequence

from app.api.schemas import GameOut
from app.bot.texts import SOURCE_NAMES, text
from app.db.models import AnalysisStatus, Color
from app.explain.facts import MoveLike
from app.explain.templates import Lang
from app.review.game_rating import time_class
from app.review.types import MoveClass

# Ошибок в ответе: самые дорогие по падению win%.
KEY_MISTAKES = 3
MISTAKE_CLASSES = (MoveClass.MISTAKE, MoveClass.BLUNDER)
SYMBOLS: dict[MoveClass, str] = {
    MoveClass.BLUNDER: "??",
    MoveClass.MISTAKE: "?",
    MoveClass.INACCURACY: "?!",
}
_TIME_CONTROL_RE = re.compile(r"^(\d+)(?:\+(\d+))?$")
# Запас до лимита Telegram (4096 символов после разбора разметки).
MESSAGE_LIMIT = 4000


@dataclasses.dataclass(frozen=True, slots=True)
class KeyMistake:
    ply: int
    fullmove: int
    color: Color
    san: str
    move_class: MoveClass
    is_miss: bool
    best_san: str | None
    # Падение win% сделавшего ход.
    drop: float


@dataclasses.dataclass(frozen=True, slots=True)
class GameReport:
    # Партия и её последний анализ (сводка): точность и рейтинг партии — как на плашках.
    game: GameOut
    # Цвет игрока, о котором спросили (None — ник не совпал ни с одной стороной).
    color: Color | None
    # Статус анализа; queued / running — не дождались за BOT_ANALYSIS_TIMEOUT_S.
    status: AnalysisStatus
    mistakes: Sequence[KeyMistake]
    # Общий разбор (`Explainer.summarize`): строки «- …».
    summary: str | None
    # Публичная ссылка на разбор; на ход — с `?ply=` (`app/db/share.py`).
    url: str


def move_color(move: MoveLike) -> Color:
    return Color.WHITE if move.fen_before.split()[1] == "w" else Color.BLACK


def key_mistakes(moves: Sequence[MoveLike], color: Color) -> list[KeyMistake]:
    """До KEY_MISTAKES ошибок игрока (mistake / blunder / miss) с наибольшим падением
    win%, в порядке партии."""
    own = [
        move
        for move in moves
        if move_color(move) == color and (move.move_class in MISTAKE_CLASSES or move.is_miss)
    ]
    top = sorted(own, key=lambda move: move.win_before - move.win_after, reverse=True)
    return [
        KeyMistake(
            ply=move.ply,
            fullmove=int(move.fen_before.split()[5]),
            color=color,
            san=move.san,
            move_class=move.move_class,
            is_miss=move.is_miss,
            best_san=move.best_san,
            drop=move.win_before - move.win_after,
        )
        for move in sorted(top[:KEY_MISTAKES], key=lambda move: move.ply)
    ]


def _e(value: object) -> str:
    """Текст для HTML Telegram (кавычки экранировать не нужно — только в атрибутах)."""
    return html.escape(str(value), quote=False)


def _player(name: str, elo: int | None) -> str:
    return f"{_e(name)} ({elo})" if elo else _e(name)


def name_of(game: GameOut, color: Color) -> str:
    return game.white if color == Color.WHITE else game.black


def _outcome(game: GameOut, color: Color | None, lang: Lang) -> str:
    result = _e(game.result)
    if game.result in ("1/2-1/2", "½-½"):
        return f"{result}, {text('draw', lang)}"
    if color is None or game.result not in ("1-0", "0-1"):
        return result
    won = (game.result == "1-0") == (color == Color.WHITE)
    return f"{result}, {text('win' if won else 'loss', lang, name=name_of(game, color))}"


def time_control_label(time_control: str | None, lang: Lang) -> str | None:
    """«Блиц 5+3», «Пуля 0.5+0», «По переписке, 3 дн. на ход»; неизвестный — None."""
    if not time_control or time_control == "-":
        return None
    label = text(f"time_{time_class(time_control)}", lang)
    if time_control.startswith("1/"):
        seconds = time_control.removeprefix("1/")
        if not seconds.isdigit():
            return label
        days = max(1, int(seconds) // 86400)
        return f"{label}, {text('daily', lang, days=days)}"
    match = _TIME_CONTROL_RE.match(time_control)
    if match is None:
        return label
    base, increment = int(match[1]), int(match[2] or 0)
    minutes = str(base // 60) if base % 60 == 0 else f"{base / 60:g}"
    return f"{label} {minutes}+{increment}"


def _header(game: GameOut, color: Color | None, lang: Lang) -> list[str]:
    lines = [
        f"<b>{_player(game.white, game.white_elo)} — {_player(game.black, game.black_elo)}</b>"
    ]
    details = [_outcome(game, color, lang)]
    if label := time_control_label(game.time_control, lang):
        details.append(label)
    details.append(SOURCE_NAMES[game.source])
    if game.played_at is not None:
        details.append(game.played_at.strftime("%d.%m.%Y"))
    lines.append(" · ".join(details))
    if game.opening_name:
        opening = (
            f"{game.opening_eco} {game.opening_name}" if game.opening_eco else game.opening_name
        )
        lines.append(f"{text('opening', lang)}: {_e(opening)}")
    return lines


def _accuracy(game: GameOut, lang: Lang) -> list[str]:
    lines: list[str] = []
    values = [(color, game.accuracy_of(color)) for color in (Color.WHITE, Color.BLACK)]
    if any(value is not None for _, value in values):
        shown = " · ".join(
            f"{_e(name_of(game, color))} {value:.1f}"
            for color, value in values
            if value is not None
        )
        lines.append(f"{text('accuracy', lang)}: {shown}")
    rating = game.game_rating
    if rating is not None:
        ratings = [(Color.WHITE, rating.white), (Color.BLACK, rating.black)]
        shown = " · ".join(
            f"{_e(name_of(game, color))} {value}" for color, value in ratings if value is not None
        )
        lines.append(f"{text('game_rating', lang)}: {shown}")
    return lines


def mistake_line(mistake: KeyMistake, url: str, lang: Lang) -> str:
    """«• 14... Qxd5?? — зевок, лучше было Nf3» со ссылкой на ход в разборе."""
    dots = "." if mistake.color == Color.WHITE else "..."
    label = f"{mistake.fullmove}{dots} {mistake.san}{SYMBOLS.get(mistake.move_class, '')}"
    kinds = [text(mistake.move_class.value, lang)] if mistake.move_class in MISTAKE_CLASSES else []
    if mistake.is_miss:
        kinds.append(text("miss", lang))
    line = f'• <a href="{html.escape(url)}">{_e(label)}</a> — {", ".join(kinds)}'
    if mistake.best_san and mistake.best_san != mistake.san:
        line += f", {text('better', lang, san=mistake.best_san)}"
    return line


def _summary(summary: str, lang: Lang) -> list[str]:
    points = [line.strip().removeprefix("- ").strip() for line in summary.splitlines()]
    return [f"<b>{text('summary', lang)}</b>", *(f"• {_e(point)}" for point in points if point)]


def format_report(report: GameReport, lang: Lang) -> str:
    """Текст ответа о партии. Не влезает в сообщение — без общего разбора."""
    game = report.game
    head = _header(game, report.color, lang)
    link = f'<a href="{html.escape(report.url)}">{text("open_review", lang)}</a>'
    if report.status == AnalysisStatus.FAILED:
        return "\n".join([*head, "", text("analysis_failed", lang)])
    if report.status != AnalysisStatus.DONE:
        return "\n".join([*head, "", text("pending", lang), link])

    blocks = [head]
    if accuracy := _accuracy(game, lang):
        blocks.append(accuracy)
    if report.color is not None:
        name = name_of(game, report.color)
        if report.mistakes:
            lines = [f"<b>{text('key_mistakes', lang, name=name)}</b>"]
            lines += [
                mistake_line(mistake, f"{report.url}?ply={mistake.ply}", lang)
                for mistake in report.mistakes
            ]
            blocks.append(lines)
        else:
            blocks.append([text("no_mistakes", lang, name=name)])
    without_summary = [*blocks, [link]]
    if report.summary:
        full = "\n\n".join(
            "\n".join(block) for block in [*blocks, _summary(report.summary, lang), [link]]
        )
        if len(full) <= MESSAGE_LIMIT:
            return full
    return "\n\n".join("\n".join(block) for block in without_summary)
