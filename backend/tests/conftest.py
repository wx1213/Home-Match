from __future__ import annotations

"""pytest 配置和共享 fixture。

MVP 阶段：测试不依赖真实 PG/Redis，只做单元测试和路由 smoke test。
后续接入 PG 后，加 integration test fixture。
"""

import os

# 强制使用 mock 配置（不依赖真实 DB/Redis/SMS）
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-32-chars-minimum-please-ok")
os.environ.setdefault("SMS_PROVIDER", "mock")
os.environ.setdefault("PHONE_ENCRYPTION_KEY", "base64:dGVzdC1rZXktMzItYnl0ZXMtZm9yLXRlc3Q=")
os.environ.setdefault("PHONE_HASH_KEY", "test-hash-key-for-unit-tests")

import pytest
from fastapi.testclient import TestClient

from app.domains.auth.router import get_sms_service
from app.domains.auth.schemas import SmsCodeResponse
from app.main import create_app
from app.core.errors import (
    InvalidSmsCodeError,
    SmsCodeExpiredError,
    SmsSendError,
)


class _InMemorySmsService:
    """测试用 SmsService 替身 — 不依赖 Redis，纯内存存储。

    P1-1 修复：让 sms-code 相关测试不再依赖真实 Redis 可用性，
    避免「环境有时 Redis 在跑就过，没跑就 fail」的不稳定状态。
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._last_sent: dict[str, float] = {}
        self._counts: dict[str, int] = {}

    def generate_code(self) -> str:
        import secrets
        return f"{secrets.randbelow(10000):04d}"

    async def send_code(self, phone: str, purpose: str = "login") -> SmsCodeResponse:
        from app.core.crypto import hash_phone
        from app.core.redis_client import sms_code_key, sms_rate_limit_key
        import time as _t

        phone_h = hash_phone(phone)
        rate_key = sms_rate_limit_key(phone_h)

        # 限流：60s 重发限制（简化：用 last_sent 字典代替 redis.get）
        if rate_key + ":last" in self._last_sent:
            if _t.time() - self._last_sent[rate_key + ":last"] < 60:
                raise SmsSendError("请 60 秒后再试")

        # 限流：每小时最多 5 次
        count = self._counts.get(rate_key, 0) + 1
        self._counts[rate_key] = count
        if count > 5:
            raise SmsSendError("发送过于频繁，请稍后再试")

        # 存验证码
        code = self.generate_code()
        code_key = sms_code_key(phone_h, purpose)
        self._store[code_key] = code
        self._last_sent[rate_key + ":last"] = _t.time()
        return SmsCodeResponse(expire_in=300)

    def verify_code(self, phone: str, code: str, purpose: str = "login") -> bool:
        from app.core.crypto import hash_phone
        from app.core.redis_client import sms_code_key

        phone_h = hash_phone(phone)
        code_key = sms_code_key(phone_h, purpose)
        stored = self._store.get(code_key)
        if not stored:
            raise SmsCodeExpiredError("验证码已过期")
        if stored != code:
            raise InvalidSmsCodeError("验证码错误")
        del self._store[code_key]
        return True


@pytest.fixture(scope="session")
def app():
    """FastAPI app 实例。"""
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """同步 TestClient（P1-1 修复：override SmsService 避免 Redis 依赖）。"""
    fake_sms = _InMemorySmsService()
    app.dependency_overrides[get_sms_service] = lambda: fake_sms
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
