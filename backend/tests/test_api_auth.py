"""Auth: регистрация, вход, refresh с ротацией и отзывом, выход, токены, профиль,
передача данных dev-пользователя первому зарегистрированному."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import delete, func, select, update

from app.api.auth import REFRESH_COOKIE
from app.auth.tokens import create_token
from app.core.config import Settings
from app.db.models import Game, GameSource, RefreshToken, User
from app.db.session import Database
from tests.conftest import api_client

pytestmark = pytest.mark.integration

PASSWORD = "correct horse battery"


def new_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
async def anon(settings: Settings, migrated_db: str) -> AsyncIterator[AsyncClient]:
    """Клиент без токена (как браузер до входа); cookie хранит сам."""
    async with api_client(settings, anonymous=True) as client:
        yield client


async def register(
    client: AsyncClient, email: str | None = None, password: str = PASSWORD, **extra: object
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email or new_email(), "password": password, **extra},
    )
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def bearer(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def refresh_cookie(client: AsyncClient) -> str | None:
    return client.cookies.get(REFRESH_COOKIE)


async def refresh_with(client: AsyncClient, token: str | None) -> Response:
    """Обновление с заданным cookie (как будто его предъявил другой браузер)."""
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, token or "")
    return await client.post("/api/v1/auth/refresh")


async def test_register_login_and_me(anon: AsyncClient) -> None:
    email = new_email()

    registered = await register(anon, email.upper(), lang="en")
    me = await anon.get("/api/v1/auth/me", headers=bearer(registered["access_token"]))

    assert registered["token_type"] == "bearer"
    assert registered["expires_in"] == 15 * 60
    user = registered["user"]
    assert isinstance(user, dict)
    # Email хранится в нижнем регистре, язык гостя переходит в профиль.
    assert user["email"] == email
    assert user["lang"] == "en"
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]
    assert refresh_cookie(anon)

    login = await anon.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["user"]["id"] == user["id"]
    assert login.headers["cache-control"] == "no-store"
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "path=/api/v1/auth" in cookie
    assert "samesite=lax" in cookie


async def test_password_is_hashed_with_argon2(anon: AsyncClient, db: Database) -> None:
    email = new_email()
    await register(anon, email)

    async with db.sessionmaker() as session:
        stored = await session.scalar(select(User.password_hash).where(User.email == email))

    assert stored is not None
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


async def test_register_rejects_taken_email_and_bad_input(anon: AsyncClient) -> None:
    email = new_email()
    await register(anon, email)

    taken = await anon.post(
        "/api/v1/auth/register", json={"email": email.upper(), "password": PASSWORD}
    )
    short = await anon.post(
        "/api/v1/auth/register", json={"email": new_email(), "password": "short"}
    )
    not_email = await anon.post(
        "/api/v1/auth/register", json={"email": "nobody", "password": PASSWORD}
    )

    assert taken.status_code == 409
    assert taken.json()["code"] == "email_taken"
    assert short.status_code == 422
    assert short.json()["code"] == "validation_error"
    assert not_email.status_code == 422


async def test_login_rejects_wrong_password_and_unknown_email(anon: AsyncClient) -> None:
    email = new_email()
    await register(anon, email)

    wrong = await anon.post("/api/v1/auth/login", json={"email": email, "password": "x" * 10})
    unknown = await anon.post(
        "/api/v1/auth/login", json={"email": new_email(), "password": PASSWORD}
    )

    assert wrong.status_code == unknown.status_code == 401
    # Одинаковый ответ: по нему не узнать, зарегистрирован ли email.
    assert wrong.json() == unknown.json()
    assert wrong.json()["code"] == "invalid_credentials"


async def test_dev_user_without_password_cannot_login(
    anon: AsyncClient, settings: Settings
) -> None:
    response = await anon.post(
        "/api/v1/auth/login", json={"email": settings.default_user_email, "password": PASSWORD}
    )

    assert response.status_code == 401


async def test_refresh_rotates_token(anon: AsyncClient) -> None:
    await register(anon)
    first = refresh_cookie(anon)

    response = await anon.post("/api/v1/auth/refresh")

    assert response.status_code == 200, response.text
    second = refresh_cookie(anon)
    assert second
    assert second != first
    me = await anon.get("/api/v1/auth/me", headers=bearer(response.json()["access_token"]))
    assert me.status_code == 200


async def test_reused_refresh_token_revokes_session(
    anon: AsyncClient, db: Database, settings: Settings
) -> None:
    """Повтор заменённого токена после окна — кража: отзывается вся цепочка, и новый
    токен (у вора или у владельца) тоже перестаёт работать."""
    await register(anon)
    stolen = refresh_cookie(anon)
    assert stolen
    assert (await anon.post("/api/v1/auth/refresh")).status_code == 200
    current = refresh_cookie(anon)
    # Окно параллельного обновления прошло.
    async with db.sessionmaker() as session:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.replaced_at.is_not(None))
            .values(replaced_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await session.commit()

    reuse = await refresh_with(anon, stolen)
    after = await refresh_with(anon, current)

    assert reuse.status_code == 401
    assert reuse.json()["code"] == "refresh_invalid"
    assert after.status_code == 401


async def test_parallel_refresh_within_grace_keeps_session(anon: AsyncClient) -> None:
    """Две вкладки обновились одним токеном: вторая получает refresh_rotated и повторяет
    с новым cookie, сессия не отзывается."""
    await register(anon)
    old = refresh_cookie(anon)
    assert (await anon.post("/api/v1/auth/refresh")).status_code == 200
    new = refresh_cookie(anon)

    raced = await refresh_with(anon, old)
    retry = await refresh_with(anon, new)

    assert raced.status_code == 401
    assert raced.json()["code"] == "refresh_rotated"
    assert retry.status_code == 200


async def test_refresh_without_cookie_or_with_garbage(anon: AsyncClient) -> None:
    missing = await anon.post("/api/v1/auth/refresh")
    garbage = await refresh_with(anon, "nope")

    assert missing.status_code == garbage.status_code == 401
    assert garbage.json()["code"] == "refresh_invalid"
    # Негодный cookie удаляется.
    assert f'{REFRESH_COOKIE}=""' in garbage.headers["set-cookie"]


async def test_expired_refresh_token_is_rejected(anon: AsyncClient, db: Database) -> None:
    body = await register(anon)
    user = body["user"]
    assert isinstance(user, dict)
    async with db.sessionmaker() as session:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == uuid.UUID(user["id"]))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    response = await anon.post("/api/v1/auth/refresh")

    assert response.status_code == 401


async def test_logout_revokes_refresh_token(anon: AsyncClient) -> None:
    await register(anon)
    token = refresh_cookie(anon)

    logout = await anon.post("/api/v1/auth/logout")
    cookie_after_logout = refresh_cookie(anon)
    reuse = await refresh_with(anon, token)

    assert logout.status_code == 204
    assert cookie_after_logout is None
    assert reuse.status_code == 401
    assert reuse.json()["code"] == "refresh_invalid"


async def test_logout_keeps_other_sessions(anon: AsyncClient, settings: Settings) -> None:
    email = new_email()
    await register(anon, email)
    async with api_client(settings, anonymous=True) as other_device:
        login = await other_device.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert login.status_code == 200

        await anon.post("/api/v1/auth/logout")

        assert (await other_device.post("/api/v1/auth/refresh")).status_code == 200


async def test_refresh_rejects_foreign_origin(anon: AsyncClient) -> None:
    await register(anon)

    foreign = await anon.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example"})
    own = await anon.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost:3000"})

    assert foreign.status_code == 403
    assert foreign.json()["code"] == "origin_forbidden"
    assert own.status_code == 200


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({}, "not_authenticated"),
        ({"Authorization": "Bearer not-a-jwt"}, "token_invalid"),
        ({"Authorization": "Basic dXNlcjpwYXNz"}, "not_authenticated"),
    ],
)
async def test_protected_routes_require_token(
    anon: AsyncClient, headers: dict[str, str], code: str
) -> None:
    response = await anon.get("/api/v1/games", headers=headers)

    assert response.status_code == 401
    assert response.json()["code"] == code
    assert response.headers["www-authenticate"] == "Bearer"


async def test_expired_access_token(anon: AsyncClient, settings: Settings) -> None:
    long_ago = datetime.now(UTC) - timedelta(hours=1)
    token = create_token(settings, settings.default_user_id, now=long_ago)

    response = await anon.get("/api/v1/games", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"


async def test_forged_access_tokens(anon: AsyncClient, settings: Settings) -> None:
    now = int(datetime.now(UTC).timestamp())
    claims = {"sub": str(settings.default_user_id), "typ": "access", "iat": now, "exp": now + 60}
    wrong_key = jwt.encode(claims, "not the server secret, but long enough", algorithm="HS256")
    unsigned = jwt.encode(claims, "", algorithm="none")
    valid = create_token(settings, settings.default_user_id)
    header, payload, signature = valid.split(".")
    tampered = ".".join(
        [header, payload[:-2] + ("AA" if payload[-2:] != "AA" else "BB"), signature]
    )
    stream = create_token(settings, settings.default_user_id, "stream", analysis_id=uuid.uuid4())
    unknown_user = create_token(settings, uuid.uuid4())

    for token in (wrong_key, unsigned, tampered, stream, unknown_user):
        response = await anon.get("/api/v1/games", headers=bearer(token))
        assert response.status_code == 401, token
        assert response.json()["code"] == "token_invalid"


async def test_update_profile(anon: AsyncClient) -> None:
    body = await register(anon)
    headers = bearer(body["access_token"])

    updated = await anon.patch(
        "/api/v1/auth/me",
        headers=headers,
        json={"lang": "en", "lichess_username": "Magnus", "chesscom_username": "hikaru"},
    )
    lang_only = await anon.patch("/api/v1/auth/me", headers=headers, json={"lang": "ru"})
    cleared = await anon.patch(
        "/api/v1/auth/me", headers=headers, json={"lichess_username": "", "chesscom_username": None}
    )
    invalid = await anon.patch(
        "/api/v1/auth/me", headers=headers, json={"lang": "de", "lichess_username": "bad name!"}
    )

    assert updated.status_code == 200
    assert updated.json()["lichess_username"] == "Magnus"
    # Не переданные поля не меняются.
    assert lang_only.json()["lichess_username"] == "Magnus"
    assert lang_only.json()["lang"] == "ru"
    assert cleared.json()["lichess_username"] is None
    assert cleared.json()["chesscom_username"] is None
    assert invalid.status_code == 422


@pytest.fixture
async def unclaimed_dev_user(db: Database, settings: Settings) -> AsyncIterator[None]:
    """Dev-пользователь как после миграции; после теста — снова без пароля."""
    yield
    async with db.sessionmaker() as session:
        await session.execute(
            update(User)
            .where(User.id == settings.default_user_id)
            .values(email=settings.default_user_email, password_hash=None, lang="ru")
        )
        await session.execute(delete(RefreshToken))
        await session.commit()


@pytest.mark.usefixtures("unclaimed_dev_user")
async def test_first_registered_user_gets_dev_user_data(settings: Settings, db: Database) -> None:
    async with db.sessionmaker() as session:
        session.add(
            Game(
                user_id=settings.default_user_id,
                source=GameSource.PGN,
                external_id="dev-game",
                pgn="",
                white="Me",
                black="Opponent",
                result="1-0",
            )
        )
        await session.commit()
    claiming = settings.model_copy(update={"auth_claim_dev_user": True})
    email = new_email()

    async with api_client(claiming, anonymous=True) as client:
        first = await register(client, email, lang="en")
        second = await register(client)
        games = await client.get("/api/v1/games", headers=bearer(first["access_token"]))
        other_games = await client.get("/api/v1/games", headers=bearer(second["access_token"]))

    first_user, second_user = first["user"], second["user"]
    assert isinstance(first_user, dict)
    assert isinstance(second_user, dict)
    assert first_user["id"] == str(settings.default_user_id)
    assert first_user["email"] == email
    assert first_user["lang"] == "en"
    # Ник с площадки (из импорта) и партии остались у той же записи.
    assert [g["white"] for g in games.json()["items"]] == ["Me"]
    assert second_user["id"] != str(settings.default_user_id)
    assert other_games.json()["items"] == []
    async with db.sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(User))
    assert count is not None
    assert count >= 2
