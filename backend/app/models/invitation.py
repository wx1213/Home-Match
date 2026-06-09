"""Invitation 模型 - 邀请。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin


class InvitationStatus(str, Enum):
    """邀请状态（[D-001] 状态机）。"""

    PENDING = "pending"  # 待响应
    ACCEPTED = "accepted"  # 已接单
    REJECTED = "rejected"  # 已拒绝
    EXPIRED = "expired"  # 已超时失效
    PROPOSAL_REVIEW = "proposal_review"  # 方案待审
    HANDSHAKED = "handshaked"  # 已握手
    CLOSED = "closed"  # 已关闭（方案被拒）

    @classmethod
    def terminal_states(cls) -> list[str]:
        """终态。"""
        return [cls.EXPIRED.value, cls.REJECTED.value, cls.HANDSHAKED.value, cls.CLOSED.value]


class Invitation(Base, TimestampMixin, SoftDeleteMixin):
    """邀请表。"""

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 关联
    demand_id: Mapped[int] = mapped_column(
        ForeignKey("demands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 状态
    status: Mapped[InvitationStatus] = mapped_column(
        SQLEnum(InvitationStatus, name="invitation_status", values_callable=lambda e: [m.value for m in e]),
        default=InvitationStatus.PENDING,
        nullable=False,
    )

    # 时间
    expired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proposal_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 拒绝原因（可选）
    reject_reason: Mapped[str | None] = mapped_column(String(256))

    # 备注
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_invitations_status_expired", "status", "expired_at"),
        Index("ix_invitations_seller_status", "seller_id", "status"),
        Index("ix_invitations_buyer_status", "buyer_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Invitation id={self.id} {self.buyer_id}->{self.seller_id} status={self.status.value}>"
