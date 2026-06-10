"""Cooperation 模型 - 合作主记录。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin


class CooperationStatus(str, Enum):
    """合作状态。"""

    HANDSHAKED = "handshaked"  # 已握手（合作开始）
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"  # 已完成（成交）
    TERMINATED = "terminated"  # 已终止（合作破裂）


class Cooperation(Base, TimestampMixin, SoftDeleteMixin):
    """合作主记录。"""

    __tablename__ = "cooperations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 关联
    invitation_id: Mapped[int] = mapped_column(
        ForeignKey("invitations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 状态
    status: Mapped[CooperationStatus] = mapped_column(
        SQLEnum(CooperationStatus, name="cooperation_status", values_callable=lambda e: [m.value for m in e]),
        default=CooperationStatus.HANDSHAKED,
        nullable=False,
    )

    # 备忘录
    memo_content: Mapped[str] = mapped_column(Text, nullable=False)

    # 时间戳
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(Text)

    # 评价
    buyer_reviewed: Mapped[bool] = mapped_column(default=False, nullable=False)
    seller_reviewed: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        Index("ix_cooperations_buyer_status", "buyer_id", "status"),
        Index("ix_cooperations_seller_status", "seller_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Cooperation id={self.id} {self.buyer_id}<->{self.seller_id} status={self.status.value}>"
