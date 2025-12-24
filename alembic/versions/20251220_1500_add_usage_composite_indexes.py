"""add usage table composite indexes for query optimization

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-20 15:00:00.000000+00:00

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为 usage 表添加复合索引以优化常见查询

    注意：这些索引已经在 baseline 迁移中创建。
    此迁移仅用于从旧版本升级的场景，新安装会跳过。
    """
    conn = op.get_bind()

    # 检查 usage 表是否存在
    result = conn.execute(text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'usage')"
    ))
    if not result.scalar():
        # 表不存在，跳过
        return

    # 定义需要创建的索引
    indexes = [
        ("idx_usage_user_created", "ON usage (user_id, created_at)"),
        ("idx_usage_apikey_created", "ON usage (api_key_id, created_at)"),
        ("idx_usage_provider_model_created", "ON usage (provider, model, created_at)"),
    ]

    # 分别检查并创建每个索引
    for index_name, index_def in indexes:
        result = conn.execute(text(
            f"SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}')"
        ))
        if result.scalar():
            continue  # 索引已存在，跳过

        conn.execute(text(f"CREATE INDEX {index_name} {index_def}"))


def downgrade() -> None:
    """删除复合索引"""
    conn = op.get_bind()

    # 使用 IF EXISTS 避免索引不存在时报错
    conn.execute(text(
        "DROP INDEX IF EXISTS idx_usage_provider_model_created"
    ))
    conn.execute(text(
        "DROP INDEX IF EXISTS idx_usage_apikey_created"
    ))
    conn.execute(text(
        "DROP INDEX IF EXISTS idx_usage_user_created"
    ))
