"""Property 模型 - 房源。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
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


class PropertyStatus(str, Enum):
    """房源状态。"""

    ACTIVE = "active"  # 有效
    INACTIVE = "inactive"  # 主动下架
    FROZEN = "frozen"  # 平台冻结（虚假房源等）


class Property(Base, TimestampMixin, SoftDeleteMixin):
    """房源表。"""

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 卖方
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 基础信息
    community: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    layout: Mapped[str] = mapped_column(String(32), nullable=False)  # "3室1厅"
    area: Mapped[float] = mapped_column(Float, nullable=False)  # m²
    total_price: Mapped[float] = mapped_column(Float, nullable=False, index=True)  # 元

    # 标签和图片
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    images: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # 来源
    source_url: Mapped[str | None] = mapped_column(String(512))

    # 可看时间
    viewing_time: Mapped[str] = mapped_column(String(64), nullable=False)

    # 真实性
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 状态
    status: Mapped[PropertyStatus] = mapped_column(
        SQLEnum(PropertyStatus, name="property_status", values_callable=lambda e: [m.value for m in e]),
        default=PropertyStatus.ACTIVE,
        nullable=False,
    )

    # 元数据
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invite_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index("ix_properties_district_price", "community", "total_price"),
        Index("ix_properties_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Property id={self.id} community={self.community!r} price={self.total_price}>"
