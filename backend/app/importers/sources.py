"""Партия, полученная от Lichess / Chess.com, → запись для `games`.

Клиенты источников отдают страницы `SourceGame` (сырой PGN + id источника), разбор
и определение цвета — здесь, общие для обоих источников.
"""

import dataclasses
from collections.abc import Iterable

from app.importers.pgn import PgnError, read_games, to_imported
from app.importers.store import user_color
from app.importers.types import ImportedGame


@dataclasses.dataclass(frozen=True, slots=True)
class SourceGame:
    external_id: str
    pgn: str
    # Классические шахматы; варианты (Chess960, crazyhouse, …) пропускаются.
    standard: bool = True
    # Точность белых и чёрных по версии площадки, если она есть.
    white_accuracy: float | None = None
    black_accuracy: float | None = None


def convert(game: SourceGame, username: str) -> ImportedGame | None:
    """None — партия не импортируется: вариант, нет ходов или PGN не разбирается."""
    if not game.standard:
        return None
    try:
        (parsed,) = read_games(game.pgn, max_games=1)
    except PgnError:
        return None
    imported = to_imported(parsed)
    # Цвет — по нику, с которого импортируем, а не по профилю пользователя.
    return dataclasses.replace(
        imported,
        external_id=game.external_id,
        user_color=user_color(imported, [username]),
        source_white_accuracy=game.white_accuracy,
        source_black_accuracy=game.black_accuracy,
    )


def convert_page(games: Iterable[SourceGame], username: str) -> list[ImportedGame]:
    return [imported for game in games if (imported := convert(game, username)) is not None]
