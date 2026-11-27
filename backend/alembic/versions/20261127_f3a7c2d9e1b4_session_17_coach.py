"""session 17: coach

Тренер: цель (`coach_goals`), недельный план (`coach_plans`), задания дня (`coach_tasks`)
и прочитанные уроки (`coach_lesson_reads`).

Revision ID: f3a7c2d9e1b4
Revises: d4e8b1a9c6f0
Create Date: 2026-11-27 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3a7c2d9e1b4"
down_revision: str | Sequence[str] | None = "d4e8b1a9c6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _now() -> sa.Column[datetime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "coach_goals",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "lichess",
                "chesscom",
                "pgn",
                name="game_source",
                native_enum=False,
                create_constraint=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("time_class", sa.String(length=8), nullable=False),
        sa.Column("start_rating", sa.Integer(), nullable=False),
        sa.Column("target_rating", sa.Integer(), nullable=False),
        sa.Column("minutes_per_day", sa.Integer(), nullable=False),
        sa.Column("days_per_week", sa.Integer(), nullable=False),
        sa.Column("tz", sa.String(length=64), nullable=False),
        _now(),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_coach_goals_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coach_goals")),
        sa.CheckConstraint(
            "source IN ('lichess', 'chesscom', 'pgn')", name=op.f("ck_coach_goals_game_source")
        ),
    )
    op.create_index(
        "uq_coach_goals_user_id_active",
        "coach_goals",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_table(
        "coach_plans",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("goal_id", sa.BigInteger(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("diagnosis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("allocation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("forecast", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _now(),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["coach_goals.id"],
            name=op.f("fk_coach_plans_goal_id_coach_goals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coach_plans")),
        sa.UniqueConstraint(
            "goal_id", "week_start", name=op.f("uq_coach_plans_goal_id_week_start")
        ),
    )
    op.create_table(
        "coach_tasks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["coach_plans.id"],
            name=op.f("fk_coach_tasks_plan_id_coach_plans"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_coach_tasks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coach_tasks")),
    )
    op.create_index("ix_coach_tasks_user_id_day", "coach_tasks", ["user_id", "day"], unique=False)
    op.create_table(
        "coach_lesson_reads",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column(
            "read_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_coach_lesson_reads_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "key", name=op.f("pk_coach_lesson_reads")),
    )


def downgrade() -> None:
    op.drop_table("coach_lesson_reads")
    op.drop_index("ix_coach_tasks_user_id_day", table_name="coach_tasks")
    op.drop_table("coach_tasks")
    op.drop_table("coach_plans")
    op.drop_index("uq_coach_goals_user_id_active", table_name="coach_goals")
    op.drop_table("coach_goals")
