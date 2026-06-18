"""users.is_admin：预留 admin 权限位（MVP 阶段为 bool，二期可扩 role 枚举）。

Revision ID: 0005_users_is_admin
Revises: 0004_review_tags
Create Date: 2026-06-18

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_users_is_admin"
down_revision: str | None = "0004_review_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """给 users 表加 is_admin 布尔列（默认 false）+ 索引。"""
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_users_is_admin", "users", ["is_admin"])


def downgrade() -> None:
    """回滚：删索引 + 删列。"""
    op.drop_index("ix_users_is_admin", table_name="users")
    op.drop_column("users", "is_admin")
