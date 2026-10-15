"""CLI: `python -m app.cli analyze game.pgn` — таблица ходов с оценкой, точностью и классом."""

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

import chess
import chess.pgn
import structlog

from app.core.config import get_settings
from app.engine.analyzer import Analyzer
from app.engine.cache import MemoryEvalCache
from app.engine.pool import EnginePool
from app.review.classify import MoveClassification, classify_game
from app.review.evaluate import GameEval, MoveEval, evaluate_game, replay
from app.review.openings import Opening, default_openings
from app.review.types import MoveClass, Phase
from app.review.winprob import format_score

PHASE_LABELS = {Phase.OPENING: "дебют", Phase.MIDDLEGAME: "миттельшпиль", Phase.ENDGAME: "эндшпиль"}
COLOR_LABELS = {chess.WHITE: "Белые", chess.BLACK: "Чёрные"}
CLASS_LABELS = {
    MoveClass.BOOK: "книга",
    MoveClass.FORCED: "вынужд.",
    MoveClass.BRILLIANT: "!! блестящий",
    MoveClass.GREAT: "! отличный",
    MoveClass.BEST: "лучший",
    MoveClass.EXCELLENT: "точный",
    MoveClass.GOOD: "хороший",
    MoveClass.INACCURACY: "?! неточность",
    MoveClass.MISTAKE: "? ошибка",
    MoveClass.BLUNDER: "?? зевок",
}


def read_game(path: Path, index: int) -> chess.pgn.Game:
    with path.open(encoding="utf-8-sig") as fh:
        for _ in range(index):
            if chess.pgn.skip_game(fh) is False:
                break
        game = chess.pgn.read_game(fh)
    if game is None:
        raise SystemExit(f"В {path} нет партии с номером {index + 1}")
    if game.errors:
        raise SystemExit(f"Ошибка в PGN: {game.errors[0]}")
    return game


def _move_label(move: MoveEval) -> str:
    dots = "." if move.color == chess.WHITE else "..."
    return f"{move.fullmove}{dots} {move.san}"


def _white_pov(move: MoveEval) -> str:
    return format_score(move.eval_after if move.color == chess.WHITE else -move.eval_after)


def _best_san(move: MoveEval) -> str:
    best = move.best_move
    if best is None or best == move.move:
        return ""
    return chess.Board(move.fen_before).san(best)


def _fmt_acc(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def _class_label(classification: MoveClassification) -> str:
    label = CLASS_LABELS[classification.move_class]
    return f"{label}, упущено" if classification.is_miss else label


def print_report(
    game: chess.pgn.Game,
    result: GameEval,
    classes: Sequence[MoveClassification],
    opening: Opening | None,
    out: TextIO,
) -> None:
    headers = game.headers
    out.write(
        f"{headers.get('White', '?')} — {headers.get('Black', '?')}  {headers.get('Result')}\n"
    )
    out.write(f"Дебют: {f'{opening.eco} {opening.name}' if opening else '—'}\n\n")
    out.write(
        f"{'Ход':<14}{'Оценка':>8}  {'Win% до→после':>15}{'Δ':>7}{'Точн.':>7}  "
        f"{'Фаза':<13}{'Класс':<22}{'Лучше':<8}\n"
    )
    for move, classification in zip(result.moves, classes, strict=True):
        delta = max(0.0, move.win_before - move.win_after)
        out.write(
            f"{_move_label(move):<14}{_white_pov(move):>8}  "
            f"{move.win_before:>6.1f} → {move.win_after:>5.1f}{delta:>7.1f}{move.accuracy:>7.1f}  "
            f"{PHASE_LABELS[move.phase]:<13}{_class_label(classification):<22}"
            f"{_best_san(move):<8}\n"
        )
    out.write("\nТочность:\n")
    for color in chess.COLORS[::-1]:
        phases = ", ".join(
            f"{PHASE_LABELS[phase]} {_fmt_acc(result.phase_accuracy[color][phase])}"
            for phase in Phase
        )
        out.write(
            f"  {COLOR_LABELS[color]:<7} {_fmt_acc(result.accuracy[color]):>5}   ({phases})\n"
        )


async def analyze(args: argparse.Namespace, out: TextIO) -> None:
    settings = get_settings()
    game = read_game(args.pgn, args.game - 1)
    moves = list(game.mainline_moves())
    positions = replay(game.board(), moves)

    pool = EnginePool(
        args.engine or settings.stockfish_path,
        args.pool or settings.engine_pool_size,
        threads=settings.engine_threads,
        hash_mb=settings.engine_hash_mb,
        timeout=settings.engine_timeout_s,
    )
    started = time.perf_counter()
    async with pool:
        analyzer = Analyzer(pool, MemoryEvalCache())

        def progress(done: int, total: int) -> None:
            if not args.quiet:
                sys.stderr.write(f"\rАнализ: {done}/{total}")
                sys.stderr.flush()

        evals = await analyzer.analyse_game(
            positions, moves, depth=args.depth, multipv=args.multipv, on_progress=progress
        )
    elapsed = time.perf_counter() - started
    if not args.quiet:
        sys.stderr.write("\n")

    book = default_openings()
    result = evaluate_game(game.board(), moves, evals, book_plies=book.book_plies(positions))
    print_report(game, result, classify_game(result.moves, book), book.identify(positions), out)
    out.write(
        f"\n{pool.version}, глубина {args.depth}, MultiPV {args.multipv}, "
        f"процессов {pool.size}: {elapsed:.1f} с\n"
    )


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Chess Review CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="разобрать партию из PGN")
    p.add_argument("pgn", type=Path, help="файл PGN")
    p.add_argument("--game", type=int, default=1, help="номер партии в файле (с 1)")
    p.add_argument("--depth", type=int, default=settings.analysis_depth)
    p.add_argument("--multipv", type=int, default=settings.analysis_multipv)
    p.add_argument("--pool", type=int, default=None, help="число процессов движка")
    p.add_argument("--engine", default=None, help="путь к Stockfish")
    p.add_argument("-q", "--quiet", action="store_true", help="без прогресса в stderr")
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> None:
    args = build_parser().parse_args(argv)
    # Служебные логи — только предупреждения и в stderr, чтобы не мешать таблице.
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=structlog.PrintLoggerFactory(sys.stderr),
    )
    if args.command == "analyze":
        asyncio.run(analyze(args, out))


if __name__ == "__main__":
    main()
