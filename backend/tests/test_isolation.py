"""Изоляция данных: чужие партии, анализы, ходы, объяснения, импорты, статистика и пазлы
не видны и не изменяются — на каждом роуте, где есть данные пользователя."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.auth.tokens import create_token
from app.core.config import Settings
from app.db.models import Game, GameSource, ImportJob, ImportStatus, Puzzle, User
from app.db.session import Database
from tests.conftest import api_client
from tests.test_api_explain import insert_review

pytestmark = pytest.mark.integration

PGN = '[White "A"]\n[Black "B"]\n[Result "1-0"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0\n'


@dataclass
class OwnerData:
    game_id: uuid.UUID
    analysis_id: uuid.UUID
    move_id: int
    import_id: uuid.UUID
    puzzle_id: uuid.UUID


@pytest.fixture
async def owner_data(db: Database, settings: Settings) -> OwnerData:
    """Данные dev-пользователя: партия с готовым анализом, импорт, пазл."""
    owner = settings.default_user_id
    analysis_id, moves = await insert_review(db, owner)
    async with db.sessionmaker() as session:
        game_id = await session.scalar(select(Game.id).where(Game.user_id == owner))
        job = ImportJob(
            user_id=owner, source=GameSource.LICHESS, username="owner", status=ImportStatus.DONE
        )
        puzzle = Puzzle(
            user_id=owner,
            move_id=moves["Nf6"],
            fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            solution_uci=["e7e5"],
        )
        session.add_all([job, puzzle])
        await session.commit()
        assert game_id is not None
        return OwnerData(game_id, analysis_id, moves["Nf6"], job.id, puzzle.id)


@pytest.fixture
async def intruder(
    db: Database, settings: Settings, owner_data: OwnerData
) -> AsyncIterator[AsyncClient]:
    """Другой зарегистрированный пользователь."""
    async with db.sessionmaker() as session:
        user = User(email=f"intruder-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
        session.add(user)
        await session.commit()
    async with api_client(settings, user.id) as client:
        client.headers["X-User"] = str(user.id)
        yield client


def foreign_requests(data: OwnerData) -> list[tuple[str, str, dict[str, object] | None]]:
    """Все роуты с id чужих данных."""
    return [
        ("GET", f"/api/v1/games/{data.game_id}", None),
        ("POST", f"/api/v1/games/{data.game_id}/analyze", {"depth": 6}),
        ("GET", f"/api/v1/analyses/{data.analysis_id}", None),
        ("GET", f"/api/v1/analyses/{data.analysis_id}/events", None),
        ("POST", f"/api/v1/analyses/{data.analysis_id}/events/token", None),
        ("POST", f"/api/v1/analyses/{data.analysis_id}/explanations", {}),
        ("GET", f"/api/v1/analyses/{data.analysis_id}/summary", None),
        ("POST", f"/api/v1/moves/{data.move_id}/explain", {}),
        ("GET", f"/api/v1/imports/{data.import_id}", None),
        ("POST", f"/api/v1/puzzles/{data.puzzle_id}/attempt", {"moves_uci": ["e7e5"]}),
        # Публичная ссылка: включить, посмотреть, отозвать — только владелец.
        ("POST", f"/api/v1/games/{data.game_id}/share", None),
        ("GET", f"/api/v1/games/{data.game_id}/share", None),
        ("DELETE", f"/api/v1/games/{data.game_id}/share", None),
    ]


async def test_owner_reaches_own_data(client: AsyncClient, owner_data: OwnerData) -> None:
    """Контроль: те же запросы от владельца проходят (иначе 404 ниже ничего не значат)."""
    for method, url, body in foreign_requests(owner_data):
        response = await client.request(method, url, json=body)
        assert response.status_code < 400, (method, url, response.text)


async def test_foreign_resources_are_not_found(
    intruder: AsyncClient, owner_data: OwnerData, db: Database
) -> None:
    for method, url, body in foreign_requests(owner_data):
        response = await intruder.request(method, url, json=body)
        assert response.status_code == 404, (method, url, response.text)
        assert response.json()["code"].endswith("_not_found"), url

    # Ничего не изменилось: пазл не решён, новый анализ не создан, ссылки нет.
    async with db.sessionmaker() as session:
        puzzle = await session.get(Puzzle, owner_data.puzzle_id)
        games = list(await session.scalars(select(Game)))
    assert puzzle is not None
    assert puzzle.attempts == 0
    assert len(games) == 1
    assert games[0].share_token is None


async def test_foreign_data_absent_from_lists_and_stats(
    intruder: AsyncClient, client: AsyncClient, owner_data: OwnerData
) -> None:
    games = await intruder.get("/api/v1/games")
    stats = await intruder.get("/api/v1/stats/me")
    puzzle = await intruder.get("/api/v1/puzzles/next")
    own_games = await client.get("/api/v1/games")
    own_puzzle = await client.get("/api/v1/puzzles/next")

    assert games.json() == {"items": [], "next_cursor": None}
    totals = stats.json()["totals"]
    assert totals["games"] == totals["games_without_color"] == totals["analyzed"] == 0
    assert stats.json()["motifs"] == []
    assert puzzle.json()["puzzle"] is None
    assert puzzle.json()["counts"]["total"] == 0
    # У владельца всё на месте.
    assert len(own_games.json()["items"]) == 1
    assert own_puzzle.json()["puzzle"]["id"] == str(owner_data.puzzle_id)


async def test_same_pgn_is_a_separate_game_per_user(
    intruder: AsyncClient, client: AsyncClient, db: Database
) -> None:
    (own,) = (await client.post("/api/v1/games/pgn", json={"pgn": PGN})).json()
    (theirs,) = (await intruder.post("/api/v1/games/pgn", json={"pgn": PGN})).json()

    assert own["id"] != theirs["id"]
    assert (await intruder.get(f"/api/v1/games/{own['id']}")).status_code == 404


async def test_stream_token_is_bound_to_user_and_analysis(
    intruder: AsyncClient, client: AsyncClient, owner_data: OwnerData, settings: Settings
) -> None:
    intruder_id = uuid.UUID(intruder.headers["X-User"])
    url = f"/api/v1/analyses/{owner_data.analysis_id}/events"
    # Токен со своим id на чужой анализ.
    forged = create_token(settings, intruder_id, "stream", analysis_id=owner_data.analysis_id)
    # Настоящий токен владельца, но на другой анализ.
    other = create_token(settings, settings.default_user_id, "stream", analysis_id=uuid.uuid4())
    access = create_token(settings, settings.default_user_id)

    forged_response = await intruder.get(url, params={"token": forged})
    other_response = await client.get(url, params={"token": other})
    # Access-токен в query не принимается: в query — только короткие stream-токены.
    access_response = await client.get(url, params={"token": access})

    assert forged_response.status_code == 404
    assert other_response.status_code == 401
    assert access_response.status_code == 401


async def test_stream_token_opens_events_without_header(
    client: AsyncClient, owner_data: OwnerData, settings: Settings
) -> None:
    """EventSource не шлёт заголовки: поток открывается по `?token=` из events/token."""
    url = f"/api/v1/analyses/{owner_data.analysis_id}/events"
    issued = await client.post(f"{url}/token")
    token = issued.json()["token"]
    expired = create_token(
        settings,
        settings.default_user_id,
        "stream",
        analysis_id=owner_data.analysis_id,
        now=datetime.now(UTC) - timedelta(minutes=5),
    )

    async with api_client(settings, anonymous=True) as browser:
        stream = await browser.get(url, params={"token": token})
        no_token = await browser.get(url)
        late = await browser.get(url, params={"token": expired})

    assert issued.json()["expires_in"] == settings.stream_token_ttl_s
    assert stream.status_code == 200
    assert '"status":"done"' in stream.text
    assert no_token.status_code == 401
    assert late.status_code == 401
    assert late.json()["code"] == "token_expired"
