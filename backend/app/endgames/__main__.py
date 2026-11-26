"""Сверка каталога с живыми таблицами Lichess и пересборка фикстуры ответов.

    cd backend && PYTHONPATH=. uv run python -m app.endgames fixtures [путь]

Печатает цель и ответ таблиц по каждой позиции и пишет сокращённые ответы в
`tests/data/endgame_tablebase.json` (по ним тест каталога проверяет цели без сети). Запросы —
через тот же вежливый клиент, что и API (User-Agent, пауза, один за раз).
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import chess

from app.core.config import get_settings
from app.endgames.catalog import CATALOG
from app.endgames.tablebase import LichessTablebase, parse_position
from app.importers.http import make_http_client

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "data" / "endgame_tablebase.json"
_MOVE_FIELDS = ("uci", "san", "category", "dtz", "dtm", "checkmate")
_FIELDS = ("category", "dtz", "dtm", "checkmate", "stalemate")


def trim(data: dict[str, Any]) -> dict[str, Any]:
    """Только поля, которые разбирает `parse_position`."""
    return {
        **{key: data.get(key) for key in _FIELDS},
        "moves": [{key: m.get(key) for key in _MOVE_FIELDS} for m in data.get("moves", [])],
    }


async def fetch() -> dict[str, Any]:
    settings = get_settings()
    out: dict[str, Any] = {}
    async with make_http_client(settings) as http:
        tablebase = LichessTablebase.from_settings(settings, http)
        for position in CATALOG:
            raw = trim(await tablebase.raw(chess.Board(position.fen)))
            parsed = parse_position(raw)
            best = [m.san for m in parsed.moves if m.category == parsed.moves[0].category]
            mark = "ok" if parsed.category == position.goal else "РАСХОЖДЕНИЕ"
            print(
                f"{position.id:24} цель={position.goal:4} таблицы={parsed.category:12} "
                f"лучшие={len(best)}/{len(parsed.moves)} {' '.join(best[:6])}  {mark}"
            )
            out[position.fen] = raw
    return out


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.endgames")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("fixtures", help="сверить каталог с таблицами и записать фикстуру")
    cmd.add_argument("path", nargs="?", type=Path, default=FIXTURE)
    args = parser.parse_args()
    out = asyncio.run(fetch())
    args.path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"записано: {args.path}")


if __name__ == "__main__":
    main()
