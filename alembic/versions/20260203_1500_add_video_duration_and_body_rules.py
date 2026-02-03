"""Add video_duration_seconds to video_tasks and body_rules to provider_endpoints

Revision ID: b3c4d5e6f7a8
Revises: a2f1b3c4d5e6
Create Date: 2026-02-03 15:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

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
    # 1. Add video_duration_seconds to video_tasks
    if not _column_exists("video_tasks", "video_duration_seconds"):
        op.add_column(
            "video_tasks",
            sa.Column("video_duration_seconds", sa.Float(), nullable=True),
        )

    # 2. Add body_rules to provider_endpoints
    # 请求体规则支持三种操作：
    # - set: 设置/覆盖字段 {"action": "set", "path": "metadata", "value": {"custom": "val"}}
    # - drop: 删除字段 {"action": "drop", "path": "unwanted_field"}
    # - rename: 重命名字段 {"action": "rename", "from": "old_key", "to": "new_key"}
    if not _column_exists("provider_endpoints", "body_rules"):
        op.add_column(
            "provider_endpoints",
            sa.Column("body_rules", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    # Remove body_rules from provider_endpoints
    if _column_exists("provider_endpoints", "body_rules"):
        op.drop_column("provider_endpoints", "body_rules")

    # Remove video_duration_seconds from video_tasks
    if _column_exists("video_tasks", "video_duration_seconds"):
        op.drop_column("video_tasks", "video_duration_seconds")
