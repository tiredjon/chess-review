"""`python -m app.coach.norms crawl|analyze|build` — см. `app/coach/norms/__init__.py`."""

import argparse
import asyncio

from app.coach.norms.db import ensure_schema, norms_url
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import Database


async def _crawl(args: argparse.Namespace) -> None:
    from app.coach.norms.crawl import USER_AGENT, Fetcher, crawl  # noqa: PLC0415
    from app.importers.http import make_http_client  # noqa: PLC0415

    settings = get_settings()
    norms, work = Database(norms_url(settings)), Database(settings.database_url)
    http = make_http_client(settings)
    http.headers["User-Agent"] = USER_AGENT
    try:
        await crawl(
            norms.sessionmaker,
            work.sessionmaker,
            Fetcher(http, base_url=settings.chesscom_api_url),
            max_steps=args.max_steps,
            trajectories=not args.no_trajectories,
        )
    finally:
        await http.aclose()
        await norms.dispose()
        await work.dispose()


async def _analyze(args: argparse.Namespace) -> None:
    from app.coach.norms.analyze import analyze  # noqa: PLC0415
    from app.engine.pool import EnginePool  # noqa: PLC0415

    settings = get_settings()
    # Эталон считается фоном на занятой машине: позиция может ждать процессор дольше, чем
    # в воркере, а глубина та же — таймаут движка больше.
    update: dict[str, object] = {"engine_timeout_s": args.timeout, "engine_hash_mb": args.hash}
    if args.pool:
        update["engine_pool_size"] = args.pool
    settings = settings.model_copy(update=update)
    db = Database(norms_url(settings))
    async with db.sessionmaker() as session:
        await ensure_schema(session)
    pool = EnginePool.from_settings(settings)
    await pool.start()
    try:
        await analyze(
            db,
            pool,
            settings,
            parallel_games=args.parallel,
            max_games=args.max_games,
            follow=args.follow,
        )
    finally:
        await pool.close()
        await db.dispose()


async def _build(args: argparse.Namespace) -> None:
    from app.coach.norms.build import build  # noqa: PLC0415

    settings = get_settings()
    db = Database(norms_url(settings))
    try:
        async with db.sessionmaker() as session:
            await ensure_schema(session)
            await build(session, out_dir=args.out)
    finally:
        await db.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.coach.norms")
    sub = parser.add_subparsers(dest="command", required=True)
    crawl = sub.add_parser("crawl", help="выборка игроков и партий Chess.com")
    crawl.add_argument("--max-steps", type=int, default=None)
    crawl.add_argument("--no-trajectories", action="store_true")
    analyze = sub.add_parser("analyze", help="анализ партий выборки")
    analyze.add_argument("--pool", type=int, default=None, help="процессов Stockfish")
    analyze.add_argument("--parallel", type=int, default=2, help="партий одновременно")
    analyze.add_argument("--max-games", type=int, default=None)
    analyze.add_argument("--timeout", type=float, default=600.0, help="таймаут позиции, с")
    analyze.add_argument("--hash", type=int, default=64, help="хеш Stockfish, МБ")
    analyze.add_argument("--follow", action="store_true", help="ждать новых партий")
    build = sub.add_parser("build", help="агрегаты → app/coach/data/*.json")
    build.add_argument("--out", default=None, help="папка вместо app/coach/data")
    args = parser.parse_args()
    configure_logging(get_settings())
    handlers = {"crawl": _crawl, "analyze": _analyze, "build": _build}
    asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    main()
