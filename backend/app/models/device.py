"""Device 模型 - 推送设备。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class Device(Base, TimestampMixin):
    """推送设备。"""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fcm_token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)  # ios | android
    app_version: Mapped[str] = mapped_column(String(32), default="0.1.0", nullable=False)
    device_model: Mapped[str | None] = mapped_column(String(64))
    os_version: Mapped[str | None] = mapped_column(String(32))
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
