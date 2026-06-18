"""invitation_reminder_sent_at / proposal_reminder_sent_at 字段（C3 超时提醒）

Revision ID: 0006_invitation_reminders
Revises: 0005_users_is_admin
Create Date: 2026-06-18

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_invitation_reminders"
down_revision: str | None = "0005_users_is_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """给 invitations 表加两个提醒标记列（nullable，NULL = 未提醒）。"""
    op.add_column(
        "invitations",
        sa.Column(
            "invitation_reminder_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "invitations",
        sa.Column(
            "proposal_reminder_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """回滚：删两列。"""
    op.drop_column("invitations", "proposal_reminder_sent_at")
    op.drop_column("invitations", "invitation_reminder_sent_at")
