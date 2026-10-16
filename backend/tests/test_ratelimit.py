"""Лимиты: разбор «N/период», окно в Redis, 429 с Retry-After на импорте, анализе, LLM
(но не на шаблонах), входе и регистрации."""

import uuid

import pytest
from fastapi import FastAPI
from httpx import Response
from redis.asyncio import Redis

from app.api.errors import ApiError
from app.api.ratelimit import hit
from app.core.config import Settings
from app.core.rates import Rate
from app.db.models import User
from app.db.session import Database
from tests.conftest import api_client
from tests.test_api_explain import insert_review
from tests.test_explain_service import FakeLLM


@pytest.mark.parametrize(
    ("value", "rate"),
    [
        ("30/hour", Rate(30, 3600)),
        ("10/minute", Rate(10, 60)),
        ("10/minutes", Rate(10, 60)),
        ("5/30s", Rate(5, 30)),
        ("100/d", Rate(100, 86400)),
        (" 2 / 10 min ", Rate(2, 600)),
    ],
)
def test_parse_rate(value: str, rate: Rate) -> None:
    assert Rate.parse(value) == rate


@pytest.mark.parametrize("value", ["", "10", "ten/hour", "10/week", "0/hour", "5/0s"])
def test_parse_rate_rejects_garbage(value: str) -> None:
    with pytest.raises(ValueError, match="Лимит"):
        Rate.parse(value)


def test_settings_parse_rates_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_IMPORT", "3/15m")

    assert Settings().rate_limit_import == Rate(3, 900)


integration = pytest.mark.integration


def limited(settings: Settings, **rates: str) -> Settings:
    return settings.model_copy(
        update={
            "rate_limit_enabled": True,
            **{f"rate_limit_{k}": Rate.parse(v) for k, v in rates.items()},
        }
    )


@integration
async def test_fixed_window_and_retry_after(redis: Redis, settings: Settings) -> None:
    rules = limited(settings, login="2/minute")
    start = 6000.0 + 15  # 15 с от начала минутного окна

    await hit(redis, rules, "login", "1.2.3.4", now=start)
    await hit(redis, rules, "login", "1.2.3.4", now=start + 1)
    with pytest.raises(ApiError) as exc:
        await hit(redis, rules, "login", "1.2.3.4", now=start + 2)
    # Другой IP и следующее окно — свои счётчики.
    await hit(redis, rules, "login", "5.6.7.8", now=start + 2)
    await hit(redis, rules, "login", "1.2.3.4", now=start + 60)

    assert exc.value.status_code == 429
    assert exc.value.headers == {"Retry-After": "43"}
    assert exc.value.params == {"scope": "login", "limit": 2, "period_s": 60, "retry_after": 43}


@integration
async def test_disabled_limits_do_nothing(redis: Redis, settings: Settings) -> None:
    rules = settings.model_copy(update={"rate_limit_login": Rate(1, 60)})

    for _ in range(5):
        await hit(redis, rules, "login", "1.2.3.4")


def assert_limited(response: Response, scope: str) -> None:
    assert response.status_code == 429, response.text
    body = response.json()
    assert body["code"] == "rate_limited"
    assert body["params"]["scope"] == scope
    assert int(response.headers["retry-after"]) == body["params"]["retry_after"] > 0


PGN = '[White "A"]\n[Black "B"]\n[Result "*"]\n\n1. e4 e5 *\n'


@integration
async def test_import_limit_is_per_user(redis: Redis, db: Database, settings: Settings) -> None:
    rules = limited(settings, **{"import": "2/hour"})
    async with db.sessionmaker() as session:
        other = User(email=f"other-{uuid.uuid4().hex[:8]}@example.com")
        session.add(other)
        await session.commit()

    async with api_client(rules) as me, api_client(rules, other.id) as them:
        ok = [await me.post("/api/v1/games/pgn", json={"pgn": PGN}) for _ in range(2)]
        blocked = await me.post("/api/v1/games/pgn", json={"pgn": PGN})
        # Импорт по нику — тот же лимит «import».
        blocked_lichess = await me.post("/api/v1/imports/lichess", json={"username": "someone"})
        theirs = await them.post("/api/v1/games/pgn", json={"pgn": PGN})

    assert [r.status_code for r in ok] == [200, 200]
    assert_limited(blocked, "import")
    assert_limited(blocked_lichess, "import")
    assert theirs.status_code == 200


@integration
async def test_analyze_limit_counts_only_new_analyses(
    redis: Redis, db: Database, settings: Settings
) -> None:
    rules = limited(settings, analyze="1/hour")
    async with api_client(rules) as client:
        (game,) = (await client.post("/api/v1/games/pgn", json={"pgn": PGN})).json()
        url = f"/api/v1/games/{game['id']}/analyze"
        first = await client.post(url, json={"depth": 6})
        # Тот же анализ возвращается без нового запуска — не считается.
        same = await client.post(url, json={"depth": 6})
        other_depth = await client.post(url, json={"depth": 7})

    assert first.status_code == 202
    assert same.status_code == 200
    assert_limited(other_depth, "analyze")


@integration
async def test_llm_limit_applies_only_with_llm(
    redis: Redis, db: Database, settings: Settings
) -> None:
    rules = limited(settings, llm="2/hour")
    analysis_id, moves = await insert_review(db, settings.default_user_id)
    explain = f"/api/v1/moves/{moves['Nf6']}/explain"

    # Шаблоны (LLM_PROVIDER=none) — без лимита.
    async with api_client(rules) as templates:
        responses = [await templates.post(explain, json={"lang": "en"}) for _ in range(4)]
    assert {r.status_code for r in responses} == {200}

    def with_llm(app: FastAPI) -> None:
        app.state.llm = FakeLLM()

    async with api_client(rules, setup=with_llm) as client:
        first = await client.post(explain, json={"lang": "ru"})
        summary = await client.get(f"/api/v1/analyses/{analysis_id}/summary")
        batch = await client.post(f"/api/v1/analyses/{analysis_id}/explanations")

    assert first.status_code == summary.status_code == 200
    assert_limited(batch, "llm")


@integration
async def test_login_and_register_are_limited_by_ip(redis: Redis, settings: Settings) -> None:
    rules = limited(settings, login="2/minute", register="1/hour")
    credentials = {"email": "nobody@example.com", "password": "wrong password"}

    async with api_client(rules, anonymous=True) as client:
        attempts = [await client.post("/api/v1/auth/login", json=credentials) for _ in range(3)]
        registered = await client.post(
            "/api/v1/auth/register",
            json={"email": f"ip-{uuid.uuid4().hex[:8]}@example.com", "password": "long password"},
        )
        second = await client.post(
            "/api/v1/auth/register",
            json={"email": f"ip-{uuid.uuid4().hex[:8]}@example.com", "password": "long password"},
        )
        # Другой IP за доверенным прокси — свой счётчик.
        trusted = rules.model_copy(update={"trust_forwarded_for": True})
    async with api_client(trusted, anonymous=True) as proxied:
        other_ip = await proxied.post(
            "/api/v1/auth/login", json=credentials, headers={"X-Forwarded-For": "203.0.113.7"}
        )

    assert [r.status_code for r in attempts[:2]] == [401, 401]
    assert_limited(attempts[2], "login")
    assert registered.status_code == 201
    assert_limited(second, "register")
    assert other_ip.status_code == 401


@integration
async def test_redis_failure_does_not_block(settings: Settings) -> None:
    broken = Redis.from_url("redis://127.0.0.1:1/0")
    try:
        await hit(broken, limited(settings, login="1/minute"), "login", "x")
        await hit(broken, limited(settings, login="1/minute"), "login", "x")
    finally:
        await broken.aclose()
