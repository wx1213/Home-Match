from __future__ import annotations

"""User 模型 - 经纪人用户。

参考 D-011 + D-013：
- 手机号 AES-256 加密 + HMAC 索引
- 微信 unionid 为主登录
- Apple 登录（iOS 必选）
- 信用分缓存
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin


class UserStatus(str, Enum):
    """用户状态。"""

    ACTIVE = "active"  # 正常
    FROZEN = "frozen"  # 冻结（虚假房源、违规）
    BANNED = "banned"  # 永久封禁


class User(Base, TimestampMixin, SoftDeleteMixin):
    """经纪人用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # === 认证相关（v0.4：微信为主） ===
    # 微信
    # P1-3 修复：去掉 column 自带的 `index=True`（避免与 __table_args__ 同名 Index 冲突）
    wechat_unionid: Mapped[str | None] = mapped_column(String(64), unique=True)
    wechat_openid: Mapped[str | None] = mapped_column(String(64), unique=True)
    wechat_nickname: Mapped[str | None] = mapped_column(String(64))
    wechat_avatar_url: Mapped[str | None] = mapped_column(String(512))

    # Apple
    apple_user_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)

    # 手机号（加密存储，[D-011]）
    phone_encrypted: Mapped[str | None] = mapped_column(String(512))
    phone_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)

    # 密码（兜底用，MVP 阶段未启用）
    password_hash: Mapped[str | None] = mapped_column(String(256))

    # === 基础信息 ===
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # 真实姓名
    display_name: Mapped[str | None] = mapped_column(String(64))  # 脱敏用（"张先生"）
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    gender: Mapped[str | None] = mapped_column(String(8))  # male / female / unknown

    # === 信用相关（[D-002]） ===
    credit_score: Mapped[float] = mapped_column(Float, default=60.0, nullable=False)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activity_count_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credit_score_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # === 状态 ===
    status: Mapped[UserStatus] = mapped_column(
        SQLEnum(UserStatus, name="user_status", values_callable=lambda e: [m.value for m in e]),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # === 元数据 ===
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_users_status_credit", "status", "credit_score"),
        Index("ix_users_wechat_unionid", "wechat_unionid"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r} credit={self.credit_score}>"
