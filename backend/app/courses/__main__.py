"""CLI: собрать курс против настоящих Lichess Masters и Stockfish и показать дерево.

`python -m app.courses "Sicilian Defense: Najdorf Variation" --color black`
`python -m app.courses e2e4 c7c5 g1f3 b8c6 f1b5 --color white --max-nodes 40`

Без БД: Explorer — прямой клиент Lichess (вежливый: пауза между запросами), оценки — кэш в
памяти. `--json файл` сохраняет дерево (`CourseTree`) как его пишет воркер."""

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

import chess

from app.core.config import get_settings
from app.courses.builder import BuildLimits, CourseBuilder, parse_line
from app.courses.catalog import build_catalog
from app.courses.types import CourseNode, CourseTree
from app.engine.cache import MemoryEvalCache
from app.engine.pool import EnginePool
from app.explorer.client import LichessExplorer
from app.explorer.types import ExplorerPosition, ExplorerSource, MasterGamePgn
from app.importers.http import make_http_client
from app.plans.templates import render


def _line(args: Sequence[str]) -> list[str]:
    """Линия: ходы UCI или точное имя линии каталога."""
    if not args[0][:1].islower():
        name = " ".join(args)
        for family in build_catalog().families:
            for variation in family.variations:
                for line in variation.lines:
                    if line.name == name:
                        return line.uci
        raise SystemExit(f"Нет линии «{name}» в каталоге")
    return list(args)


def _move(node: CourseNode) -> str:
    number = (node.ply + 1) // 2
    return f"{number}. {node.san}" if node.ply % 2 == 1 else f"{number}… {node.san}"


def print_tree(tree: CourseTree, out: TextIO = sys.stdout) -> None:
    by_id = {n.id: n for n in tree.nodes}
    leaves = [n for n in tree.nodes if not n.children]
    out.write(
        f"Узлов: {len(tree.nodes)}, линий (листьев): {len(leaves)}, "
        f"глубина: {max(n.ply for n in tree.nodes)} полуходов, "
        f"ключевых: {sum(1 for n in tree.nodes if n.key_moment)}, "
        f"партий мастеров: {len(tree.model_games)}\n\n"
    )

    def walk(node: CourseNode, depth: int) -> None:
        for kid_id in node.children:
            kid = by_id[kid_id]
            marks = []
            if kid.mover == "opponent" and kid.weight < 1:
                marks.append(f"{kid.weight:.0%}")
            if kid.stats is not None:
                marks.append(f"{kid.stats.games} парт.")
            else:
                marks.append("движок")
            if kid.eval is not None and kid.eval.cp is not None:
                marks.append(f"{kid.eval.cp / 100:+.2f}")
            if kid.key_moment:
                marks.append(f"[{kid.key_moment}]")
            if not kid.book:
                marks.append("вне книги")
            branch = len(node.children) > 1
            if branch or depth == 0 or kid.key_moment or not kid.children:
                indent = "  " * depth
                out.write(f"{indent}{_move(kid)}  ({', '.join(marks)})\n")
            walk(kid, depth + 1 if branch else depth)

    walk(by_id[tree.line_end], 0)

    out.write("\nИдеи в ключевых узлах:\n")
    for node in tree.nodes:
        if node.ideas is None:
            continue
        text = render(node.ideas, "ru")
        title = text.structure_title or "—"
        first = text.ideas[0].text if text.ideas else ""
        out.write(f"  #{node.id} {_move(node) if node.san else 'старт'} [{node.key_moment}]: ")
        out.write(f"{title}. {first}\n")
    out.write("\nОбразцовые партии:\n")
    for game in tree.model_games:
        node = by_id[game.node_id]
        out.write(
            f"  {game.white} – {game.black} {game.result} ({game.year}), через #{node.id} "
            f"{_move(node)}\n"
        )


async def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.courses")
    parser.add_argument("line", nargs="+", help="ходы UCI или имя линии из каталога")
    parser.add_argument("--color", choices=["white", "black"], required=True)
    parser.add_argument("--target", type=int, help="полуходов (course_target_plies)")
    parser.add_argument("--max-nodes", type=int, help="узлов (course_max_nodes)")
    parser.add_argument("--depth", type=int, help="глубина движка (course_engine_depth)")
    parser.add_argument("--json", type=Path, help="сохранить дерево в файл")
    args = parser.parse_args(argv)

    settings = get_settings()
    update = {
        key: value
        for key, value in {
            "course_target_plies": args.target,
            "course_max_nodes": args.max_nodes,
            "course_engine_depth": args.depth,
        }.items()
        if value is not None
    }
    settings = settings.model_copy(update=update)
    line = parse_line(_line(args.line))
    color = chess.WHITE if args.color == "white" else chess.BLACK

    started = time.monotonic()
    async with make_http_client(settings) as http, EnginePool.from_settings(settings) as pool:
        explorer = CountingExplorer(LichessExplorer.from_settings(settings, http))

        async def progress(percent: int) -> None:
            sys.stderr.write(f"\r{percent:3d}%  запросов к Lichess: {explorer.calls}")

        builder = CourseBuilder(
            explorer,
            pool,
            limits=BuildLimits.from_settings(settings),
            cache=MemoryEvalCache(),
            progress=progress,
        )
        tree = await builder.build(line, color)
    sys.stderr.write(f"\nГотово за {time.monotonic() - started:.0f} с\n\n")
    print_tree(tree)
    if args.json:
        args.json.write_text(tree.model_dump_json(indent=1), encoding="utf-8")
    return 0


class CountingExplorer:
    """Обёртка Explorer со счётчиком запросов (для вывода CLI)."""

    def __init__(self, inner: LichessExplorer) -> None:
        self._inner = inner
        self.calls = 0

    async def position(
        self, board: chess.Board, *, source: ExplorerSource = ExplorerSource.MASTERS
    ) -> ExplorerPosition:
        self.calls += 1
        return await self._inner.position(board, source=source)

    async def master_game(self, game_id: str) -> MasterGamePgn:
        self.calls += 1
        return await self._inner.master_game(game_id)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
