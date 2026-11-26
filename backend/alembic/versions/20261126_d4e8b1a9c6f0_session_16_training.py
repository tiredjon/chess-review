"""session 16: training

Режим попытки пазла (`puzzle_attempts.mode`), забеги «Пазлы на время», попытки тренажёра
эндшпиля и кэш таблиц Syzygy.

Revision ID: d4e8b1a9c6f0
Revises: c1a5e0d7f3b2
Create Date: 2026-11-26 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e8b1a9c6f0"
down_revision: str | Sequence[str] | None = "c1a5e0d7f3b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "puzzle_attempts",
        sa.Column("mode", sa.String(length=16), server_default="srs", nullable=False),
    )
    op.create_table(
        "puzzle_rush_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("mistakes", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_puzzle_rush_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_puzzle_rush_runs")),
    )
    op.create_index(
        "ix_puzzle_rush_runs_user_id_created_at",
        "puzzle_rush_runs",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "endgame_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("goal", sa.String(length=8), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("plies", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_endgame_attempts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_endgame_attempts")),
    )
    op.create_index(
        "ix_endgame_attempts_user_id_key",
        "endgame_attempts",
        ["user_id", "source", "key"],
        unique=False,
    )
    op.create_table(
        "tablebase_cache",
        sa.Column("epd", sa.String(length=100), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("epd", name=op.f("pk_tablebase_cache")),
    )


def downgrade() -> None:
    op.drop_table("tablebase_cache")
    op.drop_index("ix_endgame_attempts_user_id_key", table_name="endgame_attempts")
    op.drop_table("endgame_attempts")
    op.drop_index("ix_puzzle_rush_runs_user_id_created_at", table_name="puzzle_rush_runs")
    op.drop_table("puzzle_rush_runs")
    op.drop_column("puzzle_attempts", "mode")
