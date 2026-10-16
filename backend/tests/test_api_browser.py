"""Анализ в браузере (сессия 11): оценки от клиента → тот же разбор, что у воркера;
проверка присланных оценок; пазлы по пробам; режим исследования через API."""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import chess
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select, update

from app.core.config import Settings
from app.db.models import Analysis, AnalysisRunner, Move, Puzzle, User
from app.db.models import PositionEval as PositionEvalRow
from app.db.session import Database
from app.engine.analyzer import Analyzer
from app.engine.cache import eval_to_data
from app.engine.external import ExternalEvalError, game_evals
from app.importers.pgn import parse_game
from app.puzzles.generate import collect_probes, generate_puzzles
from app.review.evaluate import replay
from app.workers.analysis import analyze_game
from tests.conftest import api_client
from tests.test_analyzer import FakeEngine
from tests.test_api_analysis import OPERA
from tests.test_api_puzzles import add_analysis, fork_analyser, fork_game, fork_moves
from tests.test_puzzles import FORK, after

pytestmark = pytest.mark.integration

__all__ = ["fork_game"]

ENGINE = "Stockfish 19 lite (WASM)"
# Поля хода, которые должны совпасть у разбора воркера и разбора по оценкам из браузера.
MOVE_FIELDS = (
    "ply",
    "san",
    "eval_before_cp",
    "eval_after_cp",
    "mate_before",
    "mate_after",
    "accuracy",
    "move_class",
    "is_miss",
    "best_uci",
    "pv",
    "multipv",
    "reply_pv",
    "motifs",
    "phase",
)


async def browser_positions(pgn: str, depth: int) -> list[dict[str, Any] | None]:
    """Что пришлёт браузер: та же схема `Analyzer` (здесь — на фейковом движке),
    оценки в формате кэша; у позиций без ходов — null."""
    game = parse_game(pgn)
    positions = replay(game.board(), list(game.mainline_moves()))
    evals = await Analyzer(FakeEngine()).analyse_game(
        positions, list(game.mainline_moves()), depth=depth, multipv=3
    )
    return [
        None if not board.legal_moves.count() else eval_to_data(value)
        for board, value in zip(positions, evals, strict=True)
    ]


@pytest.fixture
async def game_id(client: AsyncClient, db: Database) -> str:
    response = await client.post("/api/v1/games/pgn", json={"pgn": OPERA})
    game_id: str = response.json()[0]["id"]
    return game_id


async def submit(
    client: AsyncClient, game_id: str, positions: list[Any], depth: int = 12
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/games/{game_id}/browser-analysis",
        json={"depth": depth, "engine": ENGINE, "positions": positions},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def moves_of(db: Database, analysis_id: str) -> list[dict[str, Any]]:
    async with db.sessionmaker() as session:
        rows = await session.scalars(
            select(Move).where(Move.analysis_id == uuid.UUID(analysis_id)).order_by(Move.ply)
        )
        return [{name: getattr(row, name) for name in MOVE_FIELDS} for row in rows]


async def test_browser_analysis_matches_worker(
    client: AsyncClient, game_id: str, db: Database, redis: Redis, settings: Settings
) -> None:
    """Одни и те же оценки через воркер и через браузер дают один и тот же разбор."""
    server = (await client.post(f"/api/v1/games/{game_id}/analyze", json={"depth": 12})).json()
    ctx = {
        "settings": settings,
        "db": db,
        "redis": redis,
        "engine": FakeEngine(),
        "engine_version": "Fake 1.0",
    }
    assert await analyze_game(ctx, server["id"]) == "done"

    body = await submit(client, game_id, await browser_positions(OPERA, 12))
    browser = body["analysis"]

    assert browser["status"] == "done"
    assert browser["runner"] == "browser"
    assert browser["engine_version"] == ENGINE
    assert browser["depth"] == 12
    assert len(browser["moves"]) == 33
    assert await moves_of(db, browser["id"]) == await moves_of(db, server["id"])
    server_done = (await client.get(f"/api/v1/analyses/{server['id']}")).json()
    for field in ("white_accuracy", "black_accuracy", "cc_white_accuracy", "phase_accuracy"):
        assert browser[field] == server_done[field], field

    # Показывается последний анализ — из браузера.
    detail = (await client.get(f"/api/v1/games/{game_id}")).json()
    assert detail["analysis"]["id"] == browser["id"]
    assert detail["analysis"]["runner"] == "browser"
    listed = (await client.get("/api/v1/games")).json()["items"][0]
    assert listed["analysis"]["runner"] == "browser"


async def test_server_analysis_is_not_replaced_by_browser(
    client: AsyncClient, game_id: str
) -> None:
    """Анализ из браузера той же глубины не мешает запросить серверный."""
    await submit(client, game_id, await browser_positions(OPERA, 12))

    response = await client.post(f"/api/v1/games/{game_id}/analyze", json={"depth": 12})

    assert response.status_code == 202
    assert response.json()["runner"] == "server"


async def test_browser_analysis_validation(
    client: AsyncClient, game_id: str, settings: Settings
) -> None:
    positions = await browser_positions(OPERA, 12)
    url = f"/api/v1/games/{game_id}/browser-analysis"

    async def post(items: list[Any], depth: int = 12) -> tuple[int, dict[str, Any]]:
        response = await client.post(
            url, json={"depth": depth, "engine": ENGINE, "positions": items}
        )
        return response.status_code, response.json()

    illegal = [dict(item) if item else item for item in positions]
    assert illegal[5] is not None
    illegal[5] = {"depth": 12, "lines": [{"cp": 10, "pv": ["a1a8"]}]}
    status, body = await post(illegal)
    assert (status, body["code"], body["params"]["index"]) == (422, "engine_data_invalid", 5)

    status, body = await post(positions[:-1])
    assert (status, body["code"]) == (422, "engine_data_invalid")

    missing = [*positions]
    missing[3] = None
    status, body = await post(missing)
    assert (status, body["params"]["index"]) == (422, 3)

    both = [*positions]
    both[2] = {"depth": 12, "lines": [{"cp": 10, "mate": 2, "pv": ["e2e4"]}]}
    assert (await post(both))[0] == 422

    status, body = await post(positions, depth=settings.browser_min_depth - 1)
    assert (status, body["code"], body["params"]["min"]) == (
        422,
        "depth_too_low",
        settings.browser_min_depth,
    )

    other = await client.post(
        f"/api/v1/games/{uuid.uuid4()}/browser-analysis",
        json={"depth": 12, "engine": ENGINE, "positions": positions},
    )
    assert other.status_code == 404


def test_terminal_positions_are_evaluated_by_server() -> None:
    """Для мата на доске присланная оценка не нужна и не используется."""
    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    fake = {"depth": 5, "lines": [{"cp": 999, "pv": ["e2e4"]}]}

    (result,) = game_evals([mated], [fake])

    assert result.score.mate() == 0
    with pytest.raises(ExternalEvalError):
        game_evals([chess.Board()], [None])


async def test_browser_puzzles_from_probes(
    client: AsyncClient, db: Database, fork_game: uuid.UUID
) -> None:
    """Пробы — ровно те позиции, что генерация спросит у движка; ответы браузера дают
    те же пазлы, что движок воркера."""
    analysis_id = await add_analysis(db, fork_game, fork_moves())
    async with db.sessionmaker() as session:
        await session.execute(
            update(Analysis).where(Analysis.id == analysis_id).values(runner=AnalysisRunner.BROWSER)
        )
        await session.commit()

    probes = await collect_probes(db, analysis_id)
    server = fork_analyser()
    assert {(p.fen, p.move) for p in probes} == {
        (FORK, "d5c7"),
        (after(FORK, ["d5c7", "e8d7"]), "c7a8"),
    }
    answers = []
    for probe in probes:
        board = chess.Board(probe.fen)
        result = await server.analyse(
            board, depth=10, multipv=2, played=(chess.Move.from_uci(probe.move),)
        )
        answers.append({"fen": probe.fen, "move": probe.move, "eval": eval_to_data(result)})

    response = await client.post(
        f"/api/v1/analyses/{analysis_id}/browser-puzzles", json={"probes": answers}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"puzzles": 1}
    async with db.sessionmaker() as session:
        (puzzle,) = await session.scalars(select(Puzzle))
    assert puzzle.solution_uci == ["d5c7", "e8d7", "c7a8"]

    # Без ответа на пробу пазла нет; серверная генерация на тех же линиях — тот же пазл.
    again = await client.post(
        f"/api/v1/analyses/{analysis_id}/browser-puzzles", json={"probes": answers[:1]}
    )
    assert again.json() == {"puzzles": 0}
    assert await generate_puzzles(db, fork_analyser(), analysis_id) == 1


async def test_browser_puzzles_only_for_browser_analysis(
    client: AsyncClient, db: Database, fork_game: uuid.UUID
) -> None:
    analysis_id = await add_analysis(db, fork_game, fork_moves())

    server = await client.post(
        f"/api/v1/analyses/{analysis_id}/browser-puzzles", json={"probes": []}
    )
    missing = await client.post(
        f"/api/v1/analyses/{uuid.uuid4()}/browser-puzzles", json={"probes": []}
    )

    assert (server.status_code, server.json()["code"]) == (409, "analysis_not_ready")
    assert missing.status_code == 404


async def test_browser_analysis_returns_probes(client: AsyncClient, db: Database) -> None:
    """Сохранение анализа сразу отдаёт пробы для пазлов из ошибок пользователя."""
    pgn = OPERA.replace('[White "Paul Morphy"]', '[White "me"]')
    await client.patch("/api/v1/auth/me", json={"lichess_username": "me"})
    (game,) = (await client.post("/api/v1/games/pgn", json={"pgn": pgn})).json()
    assert game["user_color"] == "white"

    body = await submit(client, game["id"], await browser_positions(pgn, 12))

    # Фейковый движок: разница линий мала, ошибок нет — проб тоже (форма ответа важна).
    assert body["puzzle_probes"] == []
    assert body["analysis"]["moves"][0]["class"] in {"book", "best"}


# --- Режим исследования через API ---


@pytest.fixture
async def explore_client(settings: Settings, db: Database) -> AsyncIterator[AsyncClient]:
    def setup(app: FastAPI) -> None:
        app.state.explore_engine = FakeEngine()

    async with api_client(settings, setup=setup) as client:
        yield client


async def test_explore_position(explore_client: AsyncClient, db: Database) -> None:
    fen = chess.Board().fen()

    response = await explore_client.post("/api/v1/engine/analyse", json={"fen": fen})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fen"] == fen
    (line,) = body["lines"]
    assert line == {"cp": 30, "mate": None, "pv": [{"uci": "a2a3", "san": "a3"}]}
    # Оценка легла в общий кэш (серверная — ей можно доверять).
    async with db.sessionmaker() as session:
        cached = await session.scalar(select(PositionEvalRow))
    assert cached is not None
    assert cached.depth == body["depth"]


async def test_explore_terminal_and_invalid(explore_client: AsyncClient) -> None:
    mated = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"

    terminal = await explore_client.post("/api/v1/engine/analyse", json={"fen": mated})
    broken = await explore_client.post("/api/v1/engine/analyse", json={"fen": "nonsense"})
    impossible = await explore_client.post(
        "/api/v1/engine/analyse", json={"fen": "8/8/8/8/8/8/8/8 w - - 0 1"}
    )

    assert terminal.json()["lines"] == []
    assert (broken.status_code, broken.json()["code"]) == (422, "invalid_fen")
    assert (impossible.status_code, impossible.json()["code"]) == (422, "invalid_fen")


class BrokenEngine:
    async def analyse(self, *args: object, **kwargs: object) -> None:
        raise FileNotFoundError("stockfish")


async def test_explore_without_engine(settings: Settings, db: Database) -> None:
    def setup(app: FastAPI) -> None:
        app.state.explore_engine = BrokenEngine()

    async with api_client(settings, setup=setup) as client:
        response = await client.post("/api/v1/engine/analyse", json={"fen": chess.Board().fen()})

    assert (response.status_code, response.json()["code"]) == (503, "engine_unavailable")


async def test_engine_config(client: AsyncClient, settings: Settings) -> None:
    body = (await client.get("/api/v1/engine/config")).json()

    assert body == {
        "analysis_depth": settings.analysis_depth,
        "analysis_multipv": settings.analysis_multipv,
        "browser_min_depth": settings.browser_min_depth,
        "explore_depth": settings.explore_depth,
    }


async def test_foreign_game_and_analysis(
    client: AsyncClient, game_id: str, db: Database, settings: Settings, fork_game: uuid.UUID
) -> None:
    """Чужая партия и чужой анализ — 404, как несуществующие."""
    positions = await browser_positions(OPERA, 12)
    analysis_id = await add_analysis(db, fork_game, fork_moves())
    async with db.sessionmaker() as session:
        intruder = User(email=f"intruder-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(intruder)
        await session.commit()

    async with api_client(settings, intruder.id) as other:
        game = await other.post(
            f"/api/v1/games/{game_id}/browser-analysis",
            json={"depth": 12, "engine": ENGINE, "positions": positions},
        )
        puzzles = await other.post(
            f"/api/v1/analyses/{analysis_id}/browser-puzzles", json={"probes": []}
        )

    assert (game.status_code, game.json()["code"]) == (404, "game_not_found")
    assert (puzzles.status_code, puzzles.json()["code"]) == (404, "analysis_not_found")


async def test_mate_in_one_puzzle_without_probes(client: AsyncClient, db: Database) -> None:
    """Пропущенный мат в 1: решению не нужны линии движка — проб нет, пазл создаётся сразу."""
    pgn = (
        '[White "me"]\n[Black "Opponent"]\n[Result "0-1"]\n\n'
        "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. d3 Nxh5 0-1\n"
    )
    await client.patch("/api/v1/auth/me", json={"lichess_username": "me"})
    (game,) = (await client.post("/api/v1/games/pgn", json={"pgn": pgn})).json()
    positions = await browser_positions(pgn, 12)
    # 4. d3 (полуход 7) — зевок: был мат Qxf7#, а после хода чёрные забирают ферзя.
    positions[6] = {"depth": 12, "lines": [{"mate": 1, "pv": ["h5f7"]}]}
    positions[7] = {"depth": 12, "lines": [{"cp": 900, "pv": ["f6h5"]}]}

    body = await submit(client, game["id"], positions)

    assert body["puzzle_probes"] == []
    async with db.sessionmaker() as session:
        (puzzle,) = await session.scalars(select(Puzzle))
    assert puzzle.solution_uci == ["h5f7"]
