"""add tags column to reviews

Revision ID: 0004_review_tags
Revises: 0003_devices
Create Date: 2026-06-09

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = "0004_review_tags"
down_revision: Union[str, None] = "0003_devices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给 reviews 表加 tags JSON 列（默认空数组）。"""
    op.add_column(
        "reviews",
        sa.Column("tags", JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    """回滚：删除 tags 列。"""
    op.drop_column("reviews", "tags")
