from __future__ import annotations

"""Auth 域 - 业务服务层。"""

import secrets
import time
from datetime import datetime, timezone

import redis

from app.core.config import settings
from app.core.crypto import encrypt_phone, hash_phone
from app.core.errors import (
    InvalidSmsCodeError,
    SmsCodeExpiredError,
    SmsSendError,
)
from app.core.logging import get_logger
from app.core.redis_client import sms_code_key, sms_rate_limit_key
from app.core.security import create_access_token, create_refresh_token
from app.domains.auth.schemas import (
    LoginResponse,
    SmsCodeResponse,
    UserInfo,
)
from app.models.user import User, UserStatus

logger = get_logger(__name__)

# 短信验证码有效期（秒）
SMS_CODE_EXPIRE = 300  # 5 分钟
# 短信发送最小间隔（秒）
SMS_RESEND_INTERVAL = 60
# 短信发送次数限制
SMS_SEND_LIMIT_PER_HOUR = 5


class SmsService:
    """短信服务。"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def generate_code(self) -> str:
        """生成 4 位数字验证码。"""
        return f"{secrets.randbelow(10000):04d}"

    async def send_code(self, phone: str, purpose: str = "login") -> SmsCodeResponse:
        """发送短信验证码。"""
        phone_h = hash_phone(phone)
        rate_key = sms_rate_limit_key(phone_h)

        # 1. 限流：60s 重发限制
        last_sent = self.redis.get(f"{rate_key}:last")
        if last_sent:
            raise SmsSendError(
                f"请 {SMS_RESEND_INTERVAL} 秒后再试",
                detail={"retry_after": SMS_RESEND_INTERVAL},
            )

        # 2. 限流：每小时最多 5 次
        count = self.redis.incr(f"{rate_key}:count")
        if count == 1:
            self.redis.expire(f"{rate_key}:count", 3600)
        if count > SMS_SEND_LIMIT_PER_HOUR:
            raise SmsSendError("发送过于频繁，请稍后再试", detail={"code": 429})

        # 3. 生成验证码
        code = self.generate_code()

        # 4. 存储到 Redis（5 分钟有效）
        code_key = sms_code_key(phone_h, purpose)
        self.redis.setex(code_key, SMS_CODE_EXPIRE, code)

        # 5. 记录发送时间
        self.redis.setex(f"{rate_key}:last", SMS_RESEND_INTERVAL, str(int(time.time())))

        # 6. 发送短信
        if settings.sms_provider == "mock":
            # 开发模式：直接 log 出来
            logger.info(
                "[MOCK SMS] 验证码已生成",
                extra={"phone": phone, "code": code, "purpose": purpose},
            )
        else:
            # TODO: 接入阿里云短信 SDK
            # self._send_aliyun(phone, code)
            logger.info("SMS sent", extra={"phone": phone, "purpose": purpose})

        return SmsCodeResponse(expire_in=SMS_CODE_EXPIRE)

    def verify_code(self, phone: str, code: str, purpose: str = "login") -> bool:
        """校验短信验证码。校验后立即删除（防重放）。"""
        phone_h = hash_phone(phone)
        code_key = sms_code_key(phone_h, purpose)
        stored_code = self.redis.get(code_key)

        if not stored_code:
            raise SmsCodeExpiredError("验证码已过期，请重新获取")

        if stored_code != code:
            raise InvalidSmsCodeError("验证码错误")

        # 验证成功，删除
        self.redis.delete(code_key)
        return True


class UserService:
    """用户服务 - 登录、注册、信息查询。"""

    def __init__(self, db_session, sms_service: SmsService):
        self.db = db_session
        self.sms = sms_service

    def find_or_create_by_phone(self, phone: str, name: str = "微信用户") -> tuple[User, bool]:
        """通过手机号查找或创建用户。

        Returns:
            (user, is_new)
        """
        from sqlalchemy import select

        phone_h = hash_phone(phone)
        user = self.db.scalar(select(User).where(User.phone_hash == phone_h))

        if user:
            user.last_login_at = datetime.now(timezone.utc)
            self.db.commit()
            return user, False

        # 新建
        user = User(
            phone_encrypted=encrypt_phone(phone),
            phone_hash=phone_h,
            name=name,
            display_name=_mask_name(name),
            status=UserStatus.ACTIVE,
            last_login_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("New user created", extra={"user_id": user.id})
        return user, True

    def find_or_create_by_wechat(
        self, unionid: str, openid: str, nickname: str | None, avatar_url: str | None
    ) -> tuple[User, bool]:
        """通过微信 unionid 查找或创建用户。"""
        from sqlalchemy import select

        user = self.db.scalar(select(User).where(User.wechat_unionid == unionid))

        if user:
            user.wechat_openid = openid  # 更新 openid（可能换 app）
            user.last_login_at = datetime.now(timezone.utc)
            if nickname:
                user.wechat_nickname = nickname
                # 只有在还是默认名（"微信用户" / "微先生" / "Apple 用户"）时才覆盖
                if not user.name or user.name in ("微信用户", "Apple 用户"):
                    user.name = nickname
                if not user.display_name or user.display_name in ("微先生", "Apple 用户", "用户"):
                    user.display_name = _mask_name(nickname)
            if avatar_url:
                user.wechat_avatar_url = avatar_url
                if not user.avatar_url:
                    user.avatar_url = avatar_url
            self.db.commit()
            return user, False

        # 新建
        name = nickname or "微信用户"
        user = User(
            wechat_unionid=unionid,
            wechat_openid=openid,
            wechat_nickname=nickname,
            wechat_avatar_url=avatar_url,
            name=name,
            display_name=_mask_name(name),
            avatar_url=avatar_url,
            status=UserStatus.ACTIVE,
            last_login_at=datetime.now(timezone.utc),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("New WeChat user created", extra={"user_id": user.id})
        return user, True

    def build_login_response(self, user: User, is_new: bool = False) -> LoginResponse:
        """构造登录响应（含 token + 用户信息）。"""
        from app.core.crypto import mask_phone

        access = create_access_token(user.id, extra_claims={"name": user.name})
        refresh = create_refresh_token(user.id)
        user_info = UserInfo(
            id=user.id,
            name=user.name,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            phone_mask=mask_phone(_safe_decrypt_phone(user)) if user.phone_encrypted else None,
            credit_score=user.credit_score,
            is_new=is_new,
            is_verified=user.is_verified,
            is_admin=user.is_admin,
        )
        return LoginResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=user_info,
        )


def _mask_name(name: str) -> str:
    """姓名脱敏：张三 → 张先生/女士。"""
    if not name:
        return "用户"
    # 简化：取第一个字 + 先生/女士
    # 实际产品可按性别判断
    if any(c in name for c in ["女士", "小姐"]):
        return name
    return f"{name[0]}先生"


def _safe_decrypt_phone(user: User) -> str:
    """安全解密（用于 mask 显示）。失败则返回空。"""
    from app.core.crypto import decrypt_phone

    if not user.phone_encrypted:
        return ""
    try:
        return decrypt_phone(user.phone_encrypted)
    except Exception:
        return ""
