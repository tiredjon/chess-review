"""Сборка `app/books/data/master_games.pgn` из текстов книг Project Gutenberg.

    python -m app.books.build 5614.txt 33870.txt

Тексты — `https://www.gutenberg.org/cache/epub/{5614,33870}/pg{5614,33870}.txt`
(в репозитории не хранятся). Партии, запись которых в книге ломается (ход противоречит
позиции и исправить его однозначно нельзя), в файл не попадают — список печатается.
У Ласкера каждая диаграмма основной линии сверяется с позицией после конвертации.
"""

import argparse
import sys
from pathlib import Path

from app.books.extract import (
    PREFIXES,
    Converted,
    capablanca_games,
    convert_all,
    diagrams,
    lasker_games,
    to_pgn,
)

OUTPUT = Path(__file__).parent / "data" / "master_games.pgn"

SOURCES = {
    "lasker": (
        "Edward Lasker",
        "Edward Lasker, Chess Strategy (1915), Project Gutenberg #5614, public domain in the USA",
    ),
    "capablanca": (
        "J. R. Capablanca",
        "J. R. Capablanca, Chess Fundamentals (1921), Project Gutenberg #33870, "
        "public domain in the USA",
    ),
}

# Диаграммы книги, которые не совпадают с партией по вине самой книги.
KNOWN_DIAGRAM_ISSUES = {
    ("lasker", "19", 13),  # диаграмма 129 — позиция варианта из комментария
    ("lasker", "22", 32),  # диаграмма: ферзь вместо короля на g8
}


def check_diagrams(item: Converted) -> list[str]:
    raw = item.raw
    start = PREFIXES.get((raw.source, raw.number), ("", 0))[1]
    board = item.game.board()
    boards = [board.board_fen()]
    for move in item.game.mainline_moves():
        board.push(move)
        boards.append(board.board_fen())
    problems = []
    for plies, placement in diagrams(raw):
        ply = plies + start
        if ply >= len(boards) or (raw.source, raw.number, ply) in KNOWN_DIAGRAM_ISSUES:
            continue
        # Диаграмму иногда печатают перед последним ходом строки.
        near = boards[max(0, ply - 1) : ply + 2]
        if placement not in near:
            problems.append(f"{raw.source} {raw.number}: диаграмма после полухода {ply}")
    return problems


def build(lasker_text: str, capablanca_text: str) -> tuple[list[Converted], list[str]]:
    converted = convert_all(lasker_games(lasker_text) + capablanca_games(capablanca_text))
    problems = []
    for item in converted:
        if item.error is None:
            problems += check_diagrams(item)
    return converted, problems


def render(converted: list[Converted]) -> str:
    chunks = []
    for item in converted:
        if item.error is not None:
            continue
        annotator, source = SOURCES[item.raw.source]
        game = item.game
        game.headers["Annotator"] = annotator
        game.headers["Source"] = source
        game.headers["BookGame"] = f"{item.raw.source}-{item.raw.number}"
        chunks.append(to_pgn(game).strip())
    return "\n\n".join(chunks) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("lasker", type=Path, help="pg5614.txt")
    parser.add_argument("capablanca", type=Path, help="pg33870.txt")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    converted, problems = build(
        args.lasker.read_text(encoding="utf-8"), args.capablanca.read_text(encoding="utf-8")
    )
    for item in converted:
        if item.error is not None:
            print(f"пропущена {item.raw.source} {item.raw.number}: {item.error}", file=sys.stderr)
    for problem in problems:
        print(f"не совпала {problem}", file=sys.stderr)
    if problems:
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(converted), encoding="utf-8")
    ok = sum(1 for item in converted if item.error is None)
    plies = sum(item.plies for item in converted if item.error is None)
    print(f"{args.output}: {ok} партий, {plies} полуходов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
