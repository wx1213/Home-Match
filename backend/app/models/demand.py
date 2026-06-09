"""Demand 模型 - 需求。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin


class DemandStatus(str, Enum):
    """需求状态。"""

    ACTIVE = "active"  # 匹配中
    MATCHED = "matched"  # 已匹配到合作方
    CLOSED = "closed"  # 主动关闭


class Demand(Base, TimestampMixin, SoftDeleteMixin):
    """需求表。"""

    __tablename__ = "demands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 买方
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 基础信息
    district: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    price_min: Mapped[float] = mapped_column(Float, nullable=False)
    price_max: Mapped[float] = mapped_column(Float, nullable=False)
    layouts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # ["2室1厅", "3室1厅"]
    qualification: Mapped[str] = mapped_column(String(16), default="不限", nullable=False)  # 首套/二套/不限
    viewing_time: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # ["工作日晚上", "周末"]

    # 来源
    source_url: Mapped[str | None] = mapped_column(String(512))

    # 状态
    status: Mapped[DemandStatus] = mapped_column(
        SQLEnum(DemandStatus, name="demand_status", values_callable=lambda e: [m.value for m in e]),
        default=DemandStatus.ACTIVE,
        nullable=False,
    )

    # 摘要（脱敏后用于匹配展示，AI 生成）
    summary: Mapped[str | None] = mapped_column(String(512))

    # 元数据
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_demands_status_created", "status", "created_at"),
        Index("ix_demands_price_range", "price_min", "price_max"),
    )

    def __repr__(self) -> str:
        return f"<Demand id={self.id} district={self.district!r} price={self.price_min}-{self.price_max}>"
