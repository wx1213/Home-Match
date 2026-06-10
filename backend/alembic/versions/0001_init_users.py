from __future__ import annotations

"""init users table

Revision ID: 0001_init
Revises:
Create Date: 2026-06-04

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # 认证字段
        sa.Column("wechat_unionid", sa.String(64), nullable=True),
        sa.Column("wechat_openid", sa.String(64), nullable=True),
        sa.Column("wechat_nickname", sa.String(64), nullable=True),
        sa.Column("wechat_avatar_url", sa.String(512), nullable=True),
        sa.Column("apple_user_id", sa.String(128), nullable=True),
        sa.Column("phone_encrypted", sa.String(512), nullable=True),
        sa.Column("phone_hash", sa.String(64), nullable=True),
        sa.Column("password_hash", sa.String(256), nullable=True),
        # 基础信息
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("gender", sa.String(8), nullable=True),
        # 信用
        sa.Column("credit_score", sa.Float(), nullable=False, server_default="60.0"),
        sa.Column("rating_avg", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "activity_count_30d", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "completed_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("credit_score_updated_at", sa.DateTime(timezone=True), nullable=True),
        # 状态
        sa.Column(
            "status",
            sa.Enum("active", "frozen", "banned", name="user_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        # 元数据
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wechat_unionid", name="uq_users_wechat_unionid"),
        sa.UniqueConstraint("wechat_openid", name="uq_users_wechat_openid"),
        sa.UniqueConstraint("apple_user_id", name="uq_users_apple_user_id"),
        sa.UniqueConstraint("phone_hash", name="uq_users_phone_hash"),
    )
    op.create_index("ix_users_wechat_unionid", "users", ["wechat_unionid"])
    op.create_index("ix_users_status_credit", "users", ["status", "credit_score"])


def downgrade() -> None:
    op.drop_index("ix_users_status_credit", table_name="users")
    op.drop_index("ix_users_wechat_unionid", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_status")
