"""session 15: game clocks

Часы партии по полуходам из `%clk` (`app/review/clock.py`); уже сохранённые партии
заполняются по своему PGN.

Revision ID: c1a5e0d7f3b2
Revises: 520dc51dba80
Create Date: 2026-11-26 12:00:00.000000

"""

import io
from collections.abc import Sequence

import chess.pgn
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

from app.review.clock import game_clock

# revision identifiers, used by Alembic.
revision: str = "c1a5e0d7f3b2"
down_revision: str | Sequence[str] | None = "520dc51dba80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BATCH = 500


def _backfill() -> None:
    bind = op.get_bind()
    games = sa.table(
        "games",
        sa.column("id"),
        sa.column("pgn", sa.Text),
        sa.column("time_control", sa.String),
        sa.column("clocks", ARRAY(sa.Integer)),
        sa.column("move_times", ARRAY(sa.Integer)),
    )
    last = None
    while True:
        stmt = (
            sa.select(games.c.id, games.c.pgn, games.c.time_control)
            .where(games.c.pgn.like("%[%clk%"), games.c.time_control.is_not(None))
            .order_by(games.c.id)
            .limit(_BATCH)
        )
        if last is not None:
            stmt = stmt.where(games.c.id > last)
        rows = bind.execute(stmt).all()
        if not rows:
            return
        for row in rows:
            parsed = chess.pgn.read_game(io.StringIO(row.pgn))
            clock = game_clock(parsed, row.time_control) if parsed is not None else None
            if clock is not None:
                bind.execute(
                    games.update()
                    .where(games.c.id == row.id)
                    .values(clocks=clock.clocks, move_times=clock.spent)
                )
        last = rows[-1].id


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("games", sa.Column("clocks", ARRAY(sa.Integer()), nullable=True))
    op.add_column("games", sa.Column("move_times", ARRAY(sa.Integer()), nullable=True))
    _backfill()


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "move_times")
    op.drop_column("games", "clocks")
