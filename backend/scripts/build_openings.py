"""Сборка `app/review/data/openings.tsv` из lichess-org/chess-openings (CC0).

    cd backend && uv run python scripts/build_openings.py [--ref <commit>] [--src <dir>]

Исходные a–e.tsv содержат только eco, name, pgn; скрипт добавляет uci (ходы линии)
и epd (позиция после линии), как в прежних `dist/*.tsv` репозитория.
"""

import argparse
import csv
import io
import sys
from pathlib import Path

import chess
import chess.pgn
import httpx

REPO = "lichess-org/chess-openings"
DEFAULT_REF = "a6189a30dc273ccb21fc2536a9a2fefd5592a67a"
VOLUMES = "abcde"
OUT = Path(__file__).resolve().parent.parent / "app" / "review" / "data" / "openings.tsv"


def read_volume(name: str, ref: str, src: Path | None) -> str:
    if src is not None:
        return (src / f"{name}.tsv").read_text(encoding="utf-8")
    url = f"https://raw.githubusercontent.com/{REPO}/{ref}/{name}.tsv"
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    return response.text


def convert(text: str) -> list[dict[str, str]]:
    rows = []
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        game = chess.pgn.read_game(io.StringIO(row["pgn"]))
        if game is None or game.errors:
            raise ValueError(f"не разобрать линию {row}")
        board = game.board()
        uci = []
        for move in game.mainline_moves():
            uci.append(move.uci())
            board.push(move)
        rows.append({**row, "uci": " ".join(uci), "epd": board.epd()})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ref", default=DEFAULT_REF, help="коммит или ветка репозитория")
    parser.add_argument("--src", type=Path, help="папка с уже скачанными a–e.tsv")
    args = parser.parse_args()

    rows = [row for name in VOLUMES for row in convert(read_volume(name, args.ref, args.src))]
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["eco", "name", "pgn", "uci", "epd"], delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    sys.stdout.write(f"{len(rows)} линий → {OUT}\n")


if __name__ == "__main__":
    main()
