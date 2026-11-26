"""Разбирает партии из `collect_chesscom_games.py` движком — данные для
`scripts/fit_position_rating.py`.

Для каждой позиции партии: оценка за ходящего (глубина `--depth`, MultiPV 1) и короткий
MultiPV (`app.review.difficulty`: те же глубина и число линий, что в разборе) — по нему
видно, насколько позиция трудная. Выборка уравновешена: не больше `--per-bin` партий на
(контроль, средний рейтинг с шагом 200), чтобы модель видела и новичков, и гроссмейстеров.

    uv run python scripts/analyze_rating_games.py games.jsonl --out moves.jsonl
"""

import argparse
import io
import json
import multiprocessing
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import chess
import chess.engine
import chess.pgn

from app.review.cc_accuracy import CP_CAP, score_cp
from app.review.difficulty import SHALLOW_DEPTH, SHALLOW_LINES

# Движок и глубина процесса-исполнителя (`multiprocessing.Pool`, initializer `_init`).
_worker: dict[str, Any] = {}


def _init(path: str, depth: int) -> None:
    engine = chess.engine.SimpleEngine.popen_uci(path)
    engine.configure({"Threads": 1, "Hash": 32})
    _worker.update(engine=engine, depth=depth)


def _cp(board: chess.Board) -> float | None:
    """Оценка позиции без движка: мат — проигрыш ходящего, ничья — 0; иначе None."""
    if board.is_checkmate():
        return -CP_CAP
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0
    return None


def analyse(row: dict[str, Any]) -> dict[str, Any] | None:
    engine: chess.engine.SimpleEngine = _worker["engine"]
    game = chess.pgn.read_game(io.StringIO(row["pgn"]))
    if game is None:
        return None
    board = game.board()
    moves = list(game.mainline_moves())
    if len(moves) < 10:
        return None
    plies = []
    # Один объект на партию: хэш движка переиспользуется между соседними позициями.
    token = object()
    for move in [*moves, None]:
        terminal = _cp(board)
        if terminal is not None:
            plies.append({"cp": terminal})
            break
        deep = engine.analyse(board, chess.engine.Limit(depth=_worker["depth"]), game=token)
        record: dict[str, Any] = {"cp": score_cp(deep["score"].relative)}
        if move is not None:
            shallow = engine.analyse(
                board,
                chess.engine.Limit(depth=SHALLOW_DEPTH),
                multipv=SHALLOW_LINES,
                game=token,
            )
            record["move"] = move.uci()
            record["lines"] = [
                [info["pv"][0].uci(), score_cp(info["score"].relative)]
                for info in shallow
                if info.get("pv")
            ]
            record["legal"] = board.legal_moves.count()
            board.push(move)
        plies.append(record)
        if move is None:
            break
    keep = {k: row[k] for k in row if k != "pgn"}
    return {**keep, "plies": plies}


def balanced(rows: list[dict[str, Any]], per_bin: int, seed: int) -> list[dict[str, Any]]:
    bins: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["time_class"] in ("bullet", "blitz", "rapid"):
            mean = (row["white_rating"] + row["black_rating"]) / 2
            bins[(row["time_class"], int(mean // 200))].append(row)
    rng = random.Random(seed)
    result = []
    for key in sorted(bins):
        rng.shuffle(bins[key])
        result.extend(bins[key][:per_bin])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("games", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--engine", default="stockfish")
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--per-bin", type=int, default=40)
    parser.add_argument("--include", action="append", default=[], help="URL партии — всегда")
    parser.add_argument("--workers", type=int, default=multiprocessing.cpu_count())
    parser.add_argument("--seed", type=int, default=3)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.games.open()]
    chosen = balanced(rows, args.per_bin, args.seed)
    urls = {row["url"] for row in chosen}
    chosen += [row for row in rows if row["url"] in set(args.include) - urls]
    print(f"партий: {len(chosen)}", flush=True)
    with (
        args.out.open("w") as out,
        multiprocessing.Pool(args.workers, _init, (args.engine, args.depth)) as pool,
    ):
        for done, result in enumerate(pool.imap_unordered(analyse, chosen), 1):
            if result is not None:
                out.write(json.dumps(result) + "\n")
                out.flush()
            if done % 50 == 0:
                print(f"{done}/{len(chosen)}", flush=True)


if __name__ == "__main__":
    main()
