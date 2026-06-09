"""Proposal 模型 - 合作方案。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin


class Proposal(Base, TimestampMixin, SoftDeleteMixin):
    """合作方案表。"""

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    invitation_id: Mapped[int] = mapped_column(
        ForeignKey("invitations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 一对一
        index=True,
    )

    # 方案内容
    content: Mapped[str] = mapped_column(Text, nullable=False)  # 完整方案
    fit_points: Mapped[str | None] = mapped_column(Text)  # 契合点
    viewing_suggestion: Mapped[str | None] = mapped_column(String(256))  # 看房建议
    owner_situation: Mapped[str | None] = mapped_column(Text)  # 业主情况

    # AI 辅助
    ai_generated: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_template_id: Mapped[str | None] = mapped_column(String(64))

    # 状态流转
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decline_reason: Mapped[str | None] = mapped_column(String(256))

    def __repr__(self) -> str:
        return f"<Proposal id={self.id} invitation={self.invitation_id}>"
