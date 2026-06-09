"""Review 模型 - 评价。"""

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin


class Review(Base, TimestampMixin, SoftDeleteMixin):
    """评价表。"""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    cooperation_id: Mapped[int] = mapped_column(
        ForeignKey("cooperations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reviewee_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 评价内容
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[str | None] = mapped_column(Text)

    # 快速标签（可选，list[str]） - 区分买卖方不同标签集
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default="[]")

    # 可见性（[D-004]）
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 异常标记
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    flag_reason: Mapped[str | None] = mapped_column(String(256))

    __table_args__ = (
        Index("ix_reviews_reviewee", "reviewee_id"),
        Index("ix_reviews_cooperation_reviewer", "cooperation_id", "reviewer_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Review id={self.id} rating={self.rating}>"
