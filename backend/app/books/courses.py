"""Партии из книг (`data/master_games.pgn`) как образцовые партии курса.

Курс хранит партии мастеров Lichess, выбранные при сборке. Партии книг подмешиваются при
выдаче курса (`GET /courses/{id}`): дерево не меняется, id узлов стабильны, и уже
собранные курсы получают партии без пересборки.

Партия книги привязывается к самому глубокому узлу курса, через позицию которого она
прошла (позиция — без счётчиков ходов, как `board.epd()`). Узлы раньше `MIN_PLY`
полуходов не считаются: через «1. e4 e5» проходит половина партий, это не образец к линии.
"""

import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chess
import chess.pgn

from app.courses.types import CourseTree, ModelGame

DATA = Path(__file__).parent / "data" / "master_games.pgn"

MIN_PLY = 8
MAX_BOOK_GAMES = 3

BOOK_TITLES = {
    "Edward Lasker": "Chess Strategy (1915)",
    "J. R. Capablanca": "Chess Fundamentals (1921)",
}


@dataclass(frozen=True, slots=True)
class BookGame:
    key: str  # «lasker-35» — заголовок BookGame
    white: str
    black: str
    year: int | None
    result: str
    annotator: str
    pgn: str
    positions: frozenset[str]  # позиции после каждого хода (epd)


def _year(date: str) -> int | None:
    head = date.split(".", maxsplit=1)[0]
    return int(head) if head.isdigit() else None


@lru_cache(maxsize=1)
def book_games(path: Path = DATA) -> tuple[BookGame, ...]:
    text = path.read_text(encoding="utf-8")
    stream = io.StringIO(text)
    games = []
    while (game := chess.pgn.read_game(stream)) is not None:
        board = game.board()
        positions = set()
        for move in game.mainline_moves():
            board.push(move)
            positions.add(board.epd())
        headers = game.headers
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        games.append(
            BookGame(
                key=headers["BookGame"],
                white=headers["White"],
                black=headers["Black"],
                year=_year(headers.get("Date", "")),
                result=headers["Result"],
                annotator=headers["Annotator"],
                pgn=game.accept(exporter),
                positions=frozenset(positions),
            )
        )
    return tuple(games)


def book_model_games(
    tree: CourseTree, games: tuple[BookGame, ...] | None = None
) -> list[ModelGame]:
    """Партии книг через позиции курса: до `MAX_BOOK_GAMES`, глубже привязанные — первыми."""
    games = book_games() if games is None else games
    nodes = [node for node in tree.nodes if node.ply >= MIN_PLY]
    epds = [(node, chess.Board(node.fen).epd()) for node in nodes]
    found: list[tuple[int, int, BookGame]] = []
    for game in games:
        deepest = max(
            ((node.ply, node.id) for node, epd in epds if epd in game.positions), default=None
        )
        if deepest is not None:
            found.append((deepest[0], deepest[1], game))
    found.sort(key=lambda item: (-item[0], item[2].key))
    return [
        ModelGame(
            id=f"book:{game.key}",
            node_id=node_id,
            white=game.white,
            black=game.black,
            year=game.year,
            result=game.result,
            pgn=game.pgn,
            source="book",
            annotator=game.annotator,
            book=BOOK_TITLES.get(game.annotator),
        )
        for _, node_id, game in found[:MAX_BOOK_GAMES]
    ]
