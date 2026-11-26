"""Собирает рейтинговые партии Chess.com с PGN по всему диапазону рейтингов — данные для
модели рейтинга партии с учётом позиций (`scripts/analyze_rating_games.py`,
`scripts/fit_position_rating.py`).

В отличие от `collect_chesscom_accuracy.py` официальная точность не нужна: ходы потом
разбирает наш движок. Источники игроков: архив `--user` целиком, его соперники (середина
рейтингов), слабые игроки из уже собранных партий (низ) и титулованные (верх). С одного
игрока — не больше `--per-player` партий, чтобы выборку не определяли несколько человек.

    uv run python scripts/collect_chesscom_games.py --user tiredavalanche --out games.jsonl
"""

import argparse
import asyncio
import json
import random
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from scripts.collect_chesscom_accuracy import API, TITLES, get, player_games

LOW_RATING = 700


def rows(games: list[dict[str, Any]], limit: int, rng: random.Random) -> list[dict[str, Any]]:
    result = []
    for game in games:
        white, black = game.get("white", {}), game.get("black", {})
        if (
            game.get("rules") != "chess"
            or not game.get("rated")
            or not game.get("pgn")
            or not isinstance(white.get("rating"), int)
            or not isinstance(black.get("rating"), int)
        ):
            continue
        raw = game.get("accuracies")
        accuracies: dict[str, Any] = raw if isinstance(raw, dict) else {}
        result.append(
            {
                "url": game.get("url"),
                "time_class": game.get("time_class"),
                "time_control": game.get("time_control"),
                "white": str(white.get("username", "")).lower(),
                "black": str(black.get("username", "")).lower(),
                "white_rating": white["rating"],
                "black_rating": black["rating"],
                "white_accuracy": accuracies.get("white"),
                "black_accuracy": accuracies.get("black"),
                "pgn": game["pgn"],
            }
        )
    rng.shuffle(result)
    return result[:limit]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, action="append", help="можно несколько")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--opponents", type=int, default=150)
    parser.add_argument("--low", type=int, default=80, help=f"игроков рейтинга < {LOW_RATING}")
    parser.add_argument("--titled", type=int, default=20, help="игроков на каждый титул")
    parser.add_argument("--months", type=int, default=1)
    parser.add_argument("--per-player", type=int, default=25)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    headers = {"User-Agent": Settings().import_user_agent}
    seen: set[str] = set()
    collected: list[dict[str, Any]] = []
    with args.out.open("w") as out:

        def write(found: list[dict[str, Any]]) -> int:
            fresh = [row for row in found if row["url"] not in seen]
            for row in fresh:
                seen.add(row["url"])
                collected.append(row)
                out.write(json.dumps(row) + "\n")
            out.flush()
            return len(fresh)

        async def take(http: httpx.AsyncClient, name: str, label: str) -> None:
            games = await player_games(http, name, args.months)
            print(f"{label} {name}: {write(rows(games, args.per_player, rng))}", flush=True)

        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as http:
            seeds = {user.lower() for user in args.user}
            for user in args.user:
                games = await player_games(http, user, None)
                print(f"{user}: {write(rows(games, len(games), rng))}", flush=True)

            opponents = sorted(
                {row[color] for row in collected for color in ("white", "black")} - seeds
            )
            for name in rng.sample(opponents, min(args.opponents, len(opponents))):
                await take(http, name, "соперник")

            low = sorted(
                {
                    row[color]
                    for row in collected
                    for color in ("white", "black")
                    if row[f"{color}_rating"] < LOW_RATING
                }
                - seeds
            )
            for name in rng.sample(low, min(args.low, len(low))):
                await take(http, name, "слабый")

            for title in TITLES:
                players: list[str] = (await get(http, f"{API}/titled/{title}") or {}).get(
                    "players", []
                )
                for name in rng.sample(players, min(args.titled, len(players))):
                    await take(http, name, title)


if __name__ == "__main__":
    asyncio.run(main())
