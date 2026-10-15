"""analyses cc accuracy

Revision ID: 61c8550f34f1
Revises: 8722fc9c4a55
Create Date: 2026-10-16 00:40:07.968841

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61c8550f34f1"
down_revision: str | Sequence[str] | None = "8722fc9c4a55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("analyses", sa.Column("cc_white_accuracy", sa.Double(), nullable=True))
    op.add_column("analyses", sa.Column("cc_black_accuracy", sa.Double(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("analyses", "cc_black_accuracy")
    op.drop_column("analyses", "cc_white_accuracy")
