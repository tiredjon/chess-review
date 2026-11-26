"""Собирает пары (рейтинг, точность Chess.com) из публичных архивов Chess.com — данные для
модели рейтинга партии (`app/review/game_rating.py`, `scripts/fit_game_rating.py`).

Источники игроков: архив `--user` целиком, его соперники (середина рейтингов) и
титулованные игроки из `/pub/titled/{title}` (верх). Берутся только рейтинговые партии в
классические шахматы, у которых есть `accuracies` (партию разбирали на Chess.com).

    uv run python scripts/collect_chesscom_accuracy.py --user tiredavalanche --user other \\
        --out data.jsonl
"""

import argparse
import asyncio
import io
import json
import random
from pathlib import Path
from typing import Any

import chess.pgn
import httpx

from app.core.config import Settings

API = "https://api.chess.com/pub"
TITLES = ("GM", "IM", "FM", "CM", "NM", "WGM", "WIM", "WFM")


async def get(http: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
    for attempt in range(4):
        try:
            response = await http.get(url)
        except httpx.TransportError:
            # Таймаут или обрыв: подождать и повторить, а не терять весь сбор.
            await asyncio.sleep(2**attempt * 5)
            continue
        if response.status_code == 429:
            await asyncio.sleep(2**attempt * 5)
            continue
        if response.status_code != 200:
            return None
        data: dict[str, Any] = response.json()
        return data
    return None


def move_counts(pgn: str | None) -> tuple[int, int] | None:
    """Ходов белых и чёрных в партии (по PGN архива)."""
    if not pgn:
        return None
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        return None
    plies = sum(1 for _ in game.mainline_moves())
    return (plies + 1) // 2, plies // 2


def rows(games: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for game in games:
        accuracies = game.get("accuracies")
        if (
            not isinstance(accuracies, dict)
            or game.get("rules") != "chess"
            or not game.get("rated")
        ):
            continue
        counts = move_counts(game.get("pgn"))
        for side, color in enumerate(("white", "black")):
            accuracy, player = accuracies.get(color), game.get(color, {})
            opponent = game.get("black" if color == "white" else "white", {})
            if isinstance(accuracy, int | float) and isinstance(player.get("rating"), int):
                result.append(
                    {
                        "time_class": game.get("time_class"),
                        "rating": player["rating"],
                        "accuracy": float(accuracy),
                        "username": str(player.get("username", "")).lower(),
                        "opponent_rating": opponent.get("rating"),
                        "opponent_accuracy": accuracies.get(
                            "black" if color == "white" else "white"
                        ),
                        "moves": counts[side] if counts else None,
                        "result": player.get("result"),
                        "time_control": game.get("time_control"),
                        "url": game.get("url"),
                    }
                )
    return result


async def player_games(
    http: httpx.AsyncClient, username: str, months: int | None
) -> list[dict[str, Any]]:
    archives = await get(http, f"{API}/player/{username.lower()}/games/archives")
    urls: list[str] = (archives or {}).get("archives", [])
    if months is not None:
        urls = urls[-months:]
    games: list[dict[str, Any]] = []
    for url in urls:
        data = await get(http, url)
        games.extend((data or {}).get("games", []))
        await asyncio.sleep(0.15)
    return games


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True, action="append", help="можно несколько")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--opponents", type=int, default=120, help="сколько соперников взять")
    parser.add_argument("--titled", type=int, default=25, help="игроков на каждый титул")
    parser.add_argument("--months", type=int, default=2, help="месяцев у соперников и титулованных")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    rng = random.Random(args.seed)

    settings = Settings()
    headers = {"User-Agent": settings.import_user_agent}
    seen: set[tuple[str, str]] = set()
    with args.out.open("w") as out:

        def write(found: list[dict[str, Any]]) -> int:
            fresh = [row for row in found if (row["url"], row["username"]) not in seen]
            for row in fresh:
                seen.add((row["url"], row["username"]))
                out.write(json.dumps(row) + "\n")
            out.flush()
            return len(fresh)

        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as http:
            own: list[dict[str, Any]] = []
            for user in args.user:
                games = await player_games(http, user, None)
                own.extend(games)
                print(f"{user}: {write(rows(games))} точек")

            seeds = {user.lower() for user in args.user}
            opponents = sorted(
                {
                    game[color]["username"].lower()
                    for game in own
                    for color in ("white", "black")
                    if game[color]["username"].lower() not in seeds
                }
            )
            for name in rng.sample(opponents, min(args.opponents, len(opponents))):
                print(
                    f"соперник {name}: {write(rows(await player_games(http, name, args.months)))}"
                )

            for title in TITLES:
                players: list[str] = (await get(http, f"{API}/titled/{title}") or {}).get(
                    "players", []
                )
                for name in rng.sample(players, min(args.titled, len(players))):
                    found = rows(await player_games(http, name, args.months))
                    print(f"{title} {name}: {write(found)}")


if __name__ == "__main__":
    asyncio.run(main())
