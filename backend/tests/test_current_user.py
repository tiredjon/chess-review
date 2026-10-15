import uuid
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings
from app.db.session import Database

pytestmark = pytest.mark.integration


@pytest.fixture
async def session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    db = Database(migrated_db)
    async with db.sessionmaker() as s:
        yield s
    await db.dispose()


async def test_default_user_is_seeded_by_migration(
    session: AsyncSession, settings: Settings
) -> None:
    user = await get_current_user(session, settings)

    assert user.id == settings.default_user_id
    assert user.email == settings.default_user_email
    assert user.lang == "ru"


async def test_unknown_user_is_unauthorized(session: AsyncSession, settings: Settings) -> None:
    other = settings.model_copy(update={"default_user_id": uuid.uuid4()})

    with pytest.raises(HTTPException) as exc:
        await get_current_user(session, other)

    assert exc.value.status_code == 401
