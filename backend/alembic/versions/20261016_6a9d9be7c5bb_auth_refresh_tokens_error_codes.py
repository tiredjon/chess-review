"""auth: пароли, refresh-токены; коды ошибок анализа и импорта

Revision ID: 6a9d9be7c5bb
Revises: 3462d29dba10
Create Date: 2026-10-16 12:09:33.654391

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6a9d9be7c5bb"
down_revision: str | Sequence[str] | None = "3462d29dba10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.add_column("analyses", sa.Column("error_code", sa.String(length=32), nullable=True))
    op.add_column("import_jobs", sa.Column("error_code", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    # Коды для уже записанных ошибок: интерфейс переводит их, а текст — только подробности.
    op.execute(
        "UPDATE analyses SET error_code = CASE WHEN error = 'Анализ прерван' THEN 'interrupted'"
        " WHEN error = 'Не удалось поставить анализ в очередь' THEN 'enqueue_failed'"
        " ELSE 'internal' END WHERE status = 'failed'"
    )
    op.execute(
        "UPDATE import_jobs SET error_code = CASE WHEN error = 'Импорт прерван' THEN 'interrupted'"
        " WHEN error = 'Не удалось поставить импорт в очередь' THEN 'enqueue_failed'"
        " WHEN error LIKE 'Пользователь % не найден на %' THEN 'source_user_not_found'"
        " WHEN error LIKE '%превышен лимит запросов' THEN 'source_rate_limited'"
        " WHEN error LIKE '%недоступен (%' OR error LIKE '%ошибка сервера%'"
        " THEN 'source_unavailable'"
        " WHEN error LIKE '%некорректный ответ%' OR error LIKE '%: ответ %'"
        " THEN 'source_bad_response'"
        " ELSE 'internal' END WHERE status = 'failed'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "password_hash")
    op.drop_column("import_jobs", "error_code")
    op.drop_column("analyses", "error_code")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
