"""БД эталонов `chess_review_norms`: схема приложения (alembic) + служебные таблицы прогресса.

Партии выборки хранятся как обычные `games` служебного пользователя (`user_color` — цвет
игрока выборки), поэтому анализ и метрики идут тем же кодом, что у пользователя. Служебные
таблицы (`norms_*`) создаются здесь (`CREATE … IF NOT EXISTS`), а не миграцией: их нет
в рабочей БД.
"""

import os

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import User

NORMS_DB = "chess_review_norms"
SERVICE_EMAIL = "norms@chess-review.invalid"

DDL = (
    """
    CREATE TABLE IF NOT EXISTS norms_players (
        username text PRIMARY KEY,
        status text NOT NULL DEFAULT 'queued',
        hint_rapid int,
        hint_blitz int,
        depth int NOT NULL DEFAULT 0,
        archives date[],
        discovered_at timestamptz NOT NULL DEFAULT now(),
        sampled_at timestamptz,
        traj_status text NOT NULL DEFAULT 'pending',
        traj_at timestamptz
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_norms_players_status ON norms_players (status)",
    """
    CREATE TABLE IF NOT EXISTS norms_samples (
        game_id uuid PRIMARY KEY REFERENCES games (id) ON DELETE CASCADE,
        username text NOT NULL REFERENCES norms_players (username),
        time_class text NOT NULL,
        rating int NOT NULL,
        center int NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS norms_months (
        username text NOT NULL REFERENCES norms_players (username),
        month date NOT NULL,
        time_class text NOT NULL,
        games int NOT NULL,
        first_rating int,
        last_rating int,
        PRIMARY KEY (username, month, time_class)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS norms_fetched (
        username text NOT NULL REFERENCES norms_players (username),
        month date NOT NULL,
        PRIMARY KEY (username, month)
    )
    """,
)


def norms_url(settings: Settings) -> str:
    """URL БД эталонов: `NORMS_DATABASE_URL` или рабочий URL с другим именем базы. Любое
    другое имя базы — ошибка: рабочую и тестовые БД команды не трогают."""
    raw = os.environ.get("NORMS_DATABASE_URL")
    url = make_url(raw) if raw else make_url(settings.database_url).set(database=NORMS_DB)
    if url.database != NORMS_DB:
        raise SystemExit(f"БД эталонов должна называться {NORMS_DB}, а не {url.database}")
    return url.render_as_string(hide_password=False)


async def ensure_schema(session: AsyncSession) -> None:
    for statement in DDL:
        await session.execute(text(statement))
    await session.commit()


async def service_user(session: AsyncSession) -> User:
    user = await session.scalar(select(User).where(User.email == SERVICE_EMAIL))
    if user is None:
        user = User(email=SERVICE_EMAIL, password_hash=None)
        session.add(user)
        await session.commit()
    return user
