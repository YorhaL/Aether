"""add video_duration_seconds to video_tasks

Revision ID: b3c4d5e6f7a8
Revises: a2f1b3c4d5e6
Create Date: 2026-02-03 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2f1b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Add video_duration_seconds column to video_tasks table."""
    if not _column_exists("video_tasks", "video_duration_seconds"):
        op.add_column(
            "video_tasks",
            sa.Column("video_duration_seconds", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    """Remove video_duration_seconds column from video_tasks table."""
    if _column_exists("video_tasks", "video_duration_seconds"):
        op.drop_column("video_tasks", "video_duration_seconds")
