"""games source accuracy

Revision ID: 8722fc9c4a55
Revises: b92109cfbc29
Create Date: 2026-10-16 00:18:09.758121

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8722fc9c4a55"
down_revision: str | Sequence[str] | None = "b92109cfbc29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("games", sa.Column("source_white_accuracy", sa.Double(), nullable=True))
    op.add_column("games", sa.Column("source_black_accuracy", sa.Double(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("games", "source_black_accuracy")
    op.drop_column("games", "source_white_accuracy")
