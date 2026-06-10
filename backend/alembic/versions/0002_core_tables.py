"""init core business tables: properties, demands, invitations, proposals, cooperations, reviews

Revision ID: 0002_core
Revises: 0001_init
Create Date: 2026-06-04

"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_core"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============ properties ============
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("community", sa.String(128), nullable=False),
        sa.Column("layout", sa.String(32), nullable=False),
        sa.Column("area", sa.Float(), nullable=False),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("tags", JSON(), nullable=False, server_default="[]"),
        sa.Column("images", JSON(), nullable=False, server_default="[]"),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column("viewing_time", sa.String(64), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "frozen", name="property_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invite_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_properties_seller_id", "properties", ["seller_id"])
    op.create_index("ix_properties_community", "properties", ["community"])
    op.create_index("ix_properties_total_price", "properties", ["total_price"])
    op.create_index("ix_properties_district_price", "properties", ["community", "total_price"])
    op.create_index("ix_properties_status_created", "properties", ["status", "created_at"])

    # ============ demands ============
    op.create_table(
        "demands",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("district", sa.String(64), nullable=False),
        sa.Column("price_min", sa.Float(), nullable=False),
        sa.Column("price_max", sa.Float(), nullable=False),
        sa.Column("layouts", JSON(), nullable=False, server_default="[]"),
        sa.Column("qualification", sa.String(16), nullable=False, server_default="不限"),
        sa.Column("viewing_time", JSON(), nullable=False, server_default="[]"),
        sa.Column("source_url", sa.String(512), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "matched", "closed", name="demand_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("summary", sa.String(512), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invite_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_demands_buyer_id", "demands", ["buyer_id"])
    op.create_index("ix_demands_district", "demands", ["district"])
    op.create_index("ix_demands_status_created", "demands", ["status", "created_at"])
    op.create_index("ix_demands_price_range", "demands", ["price_min", "price_max"])

    # ============ invitations ============
    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("demand_id", sa.Integer(), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "accepted", "rejected", "expired",
                "proposal_review", "handshaked", "closed",
                name="invitation_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposal_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.String(256), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["demand_id"], ["demands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_invitations_demand_id", "invitations", ["demand_id"])
    op.create_index("ix_invitations_buyer_id", "invitations", ["buyer_id"])
    op.create_index("ix_invitations_seller_id", "invitations", ["seller_id"])
    op.create_index("ix_invitations_status_expired", "invitations", ["status", "expired_at"])
    op.create_index("ix_invitations_seller_status", "invitations", ["seller_id", "status"])
    op.create_index("ix_invitations_buyer_status", "invitations", ["buyer_id", "status"])

    # ============ proposals ============
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invitation_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fit_points", sa.Text(), nullable=True),
        sa.Column("viewing_suggestion", sa.String(256), nullable=True),
        sa.Column("owner_situation", sa.Text(), nullable=True),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ai_template_id", sa.String(64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_id", name="uq_proposals_invitation_id"),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"], ondelete="CASCADE"),
    )

    # ============ cooperations ============
    op.create_table(
        "cooperations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invitation_id", sa.Integer(), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("handshaked", "in_progress", "completed", "terminated", name="cooperation_status"),
            nullable=False,
            server_default="handshaked",
        ),
        sa.Column("memo_content", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("buyer_reviewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("seller_reviewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_id", name="uq_cooperations_invitation_id"),
        sa.ForeignKeyConstraint(["invitation_id"], ["invitations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_cooperations_buyer_id", "cooperations", ["buyer_id"])
    op.create_index("ix_cooperations_seller_id", "cooperations", ["seller_id"])
    op.create_index("ix_cooperations_buyer_status", "cooperations", ["buyer_id", "status"])
    op.create_index("ix_cooperations_seller_status", "cooperations", ["seller_id", "status"])

    # ============ reviews ============
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cooperation_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("reviewee_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("flag_reason", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cooperation_id"], ["cooperations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewee_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("cooperation_id", "reviewer_id", name="uq_reviews_cooperation_reviewer"),
    )
    op.create_index("ix_reviews_cooperation_id", "reviews", ["cooperation_id"])
    op.create_index("ix_reviews_reviewer_id", "reviews", ["reviewer_id"])
    op.create_index("ix_reviews_reviewee_id", "reviews", ["reviewee_id"])


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("cooperations")
    op.drop_table("proposals")
    op.drop_table("invitations")
    op.drop_table("demands")
    op.drop_table("properties")
    op.execute("DROP TYPE IF EXISTS review_status")  # in case
    op.execute("DROP TYPE IF EXISTS cooperation_status")
    op.execute("DROP TYPE IF EXISTS invitation_status")
    op.execute("DROP TYPE IF EXISTS demand_status")
    op.execute("DROP TYPE IF EXISTS property_status")
