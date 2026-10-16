"""Разбор PGN: одна или несколько партий из текста → записи для таблицы `games`.

`external_id` PGN-партии — sha256 нормализованной записи (решение 2026-10-15):
семь обязательных тегов, стартовая позиция (FEN/SetUp) и ходы основной линии в SAN —
без комментариев, вариантов, NAG, форматирования. Та же партия, вставленная повторно
с другими пробелами или пометками, получает тот же id.
"""

import hashlib
import io
import re
from datetime import UTC, datetime

import chess
import chess.pgn

from app.importers.types import ImportedGame
from app.review.evaluate import replay
from app.review.openings import default_openings

MAX_GAMES = 100

# Seven Tag Roster + стартовая позиция: всё, что определяет партию.
_IDENTITY_TAGS = ("Event", "Site", "Date", "Round", "White", "Black", "Result", "SetUp", "FEN")
_DATE_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})$")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")
_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2", "*"})


class PgnError(ValueError):
    """Текст не удалось разобрать как PGN; `game` — номер партии в тексте (с 1).

    `code` — код для интерфейса (`app/api/errors.py`: pgn_invalid, pgn_too_many, …),
    `params` — его параметры (номер партии, причина, максимум)."""

    def __init__(self, code: str, message: str, game: int | None = None, **params: object) -> None:
        super().__init__(message if game is None else f"Партия {game}: {message}")
        self.code = code
        self.game = game
        self.params: dict[str, object] = {**params, **({"game": game} if game else {})}


def read_games(text: str, *, max_games: int = MAX_GAMES) -> list[chess.pgn.Game]:
    """Все партии из текста PGN; ошибка — если хоть одна некорректна."""
    handle = io.StringIO(text.lstrip("﻿"))
    games: list[chess.pgn.Game] = []
    while (game := chess.pgn.read_game(handle)) is not None:
        number = len(games) + 1
        if number > max_games:
            raise PgnError(
                "pgn_too_many", f"Слишком много партий, максимум {max_games}", max=max_games
            )
        check_game(game, number)
        games.append(game)
    if not games:
        raise PgnError("pgn_empty", "В тексте нет партий")
    return games


def check_game(game: chess.pgn.Game, number: int | None = None) -> None:
    if game.errors:
        raise PgnError("pgn_invalid", str(game.errors[0]), number, reason=str(game.errors[0]))
    board = game.board()
    if board.uci_variant != "chess" or board.chess960:
        raise PgnError("pgn_variant", "поддерживаются только классические шахматы", number)
    if game.next() is None:
        raise PgnError("pgn_no_moves", "в партии нет ходов", number)


def parse_game(pgn: str) -> chess.pgn.Game:
    """Одна партия из сохранённого PGN (для воркера анализа)."""
    games = read_games(pgn, max_games=1)
    return games[0]


def normalized_record(game: chess.pgn.Game) -> str:
    headers = "\n".join(
        f'[{tag} "{game.headers[tag]}"]' for tag in _IDENTITY_TAGS if tag in game.headers
    )
    exporter = chess.pgn.StringExporter(headers=False, variations=False, comments=False)
    return f"{headers}\n\n{game.accept(exporter)}"


def pgn_hash(game: chess.pgn.Game) -> str:
    return hashlib.sha256(normalized_record(game).encode("utf-8")).hexdigest()


def stored_pgn(game: chess.pgn.Game) -> str:
    """PGN для хранения: все заголовки и комментарии (там %clk, %eval), без вариантов."""
    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
    return game.accept(exporter)


def _tag(game: chess.pgn.Game, name: str) -> str | None:
    value = game.headers.get(name, "").strip()
    return None if value in {"", "?", "-"} else value


def _elo(game: chess.pgn.Game, name: str) -> int | None:
    value = _tag(game, name)
    return int(value) if value is not None and value.isdigit() else None


def played_at(game: chess.pgn.Game) -> datetime | None:
    """Время партии: UTCDate/UTCTime (Lichess, Chess.com), иначе Date/Time — как UTC.

    Неполная дата («2024.??.??») не используется: сортировать по ней нельзя.
    """
    for date_tag, time_tag in (("UTCDate", "UTCTime"), ("Date", "Time")):
        date = _DATE_RE.match(game.headers.get(date_tag, ""))
        if date is None:
            continue
        clock = _TIME_RE.match(game.headers.get(time_tag, ""))
        year, month, day = (int(part) for part in date.groups())
        hour, minute, second = (int(part) for part in clock.groups()) if clock else (0, 0, 0)
        try:
            return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
        except ValueError:
            continue
    return None


def to_imported(game: chess.pgn.Game) -> ImportedGame:
    moves = list(game.mainline_moves())
    opening = default_openings().identify(replay(game.board(), moves))
    result = game.headers.get("Result", "*")
    return ImportedGame(
        external_id=pgn_hash(game),
        pgn=stored_pgn(game),
        white=(_tag(game, "White") or "?")[:100],
        black=(_tag(game, "Black") or "?")[:100],
        white_elo=_elo(game, "WhiteElo"),
        black_elo=_elo(game, "BlackElo"),
        result=result if result in _RESULTS else "*",
        time_control=(_tag(game, "TimeControl") or "")[:32] or None,
        played_at=played_at(game),
        opening_eco=opening.eco if opening else None,
        opening_name=opening.name[:255] if opening else None,
    )


def parse_pgn(text: str, *, max_games: int = MAX_GAMES) -> list[ImportedGame]:
    """Текст PGN (одна или несколько партий) → записи для импорта."""
    return [to_imported(game) for game in read_games(text, max_games=max_games)]
