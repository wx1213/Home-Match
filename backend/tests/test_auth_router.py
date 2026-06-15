"""Stage 3 任务 5: Auth 域端到端测试。

[auth/router.py](backend/app/domains/auth/router.py) 63% → 100% 覆盖。

已有覆盖（不再重复）：
- test_auth_hardening.py: Apple 登录 RSA/JWT 验签 (12 测试)
- test_authorization.py: P1-3 越权矩阵（含 InvalidTokenError 401）

本文件聚焦：
- SMS 验证码发送 + 限流（60s/5次/小时）
- SMS 登录：新用户创建 + 已有用户登录
- Refresh token：有效/无效/类型错
- /me 端点当前行为锁定（TODO 占位）
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User, UserStatus

# ============================================================
#  Fixtures
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    from app.models import (  # noqa: F401
        cooperation,
        demand,
        invitation,
        property,
        proposal,
        review,
        user,
    )
    from app.models.device import Device  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db():
    """每个测试一个干净 DB — drop + recreate。"""
    from app.models import (  # noqa: F401
        cooperation,
        demand,
        invitation,
        property,
        proposal,
        review,
        user,
    )
    from app.models.device import Device  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield None


@pytest.fixture(autouse=True)
def _override_user_service(client, monkeypatch):
    """autouse：把 `get_user_service` 也 override 复用同一个 fake_sms + 修 AES key。

    [conftest.py] 的 client fixture 只 override 了 `get_sms_service`（lambda 返回
    单例 fake_sms），没动 `get_user_service`（后者内部 new 一个真实 SmsService
    用真 Redis）。后果：send_code 存到 fake._store，verify_code 走真 Redis → 20002。

    同时：conftest 里的 `PHONE_ENCRYPTION_KEY` 是 26 字节（base64 解码后），
    AES-GCM 需要 32 字节。fix 替换为合法 32 字节 base64 key。

    副作用：清空 fake_sms 内部 store + 计数（**autouse 范围只在本文件**，
    但 conftest 的 fake_sms 是 session-scoped 共享，状态会污染其他文件测试
    如 test_health.py 的 13800138000 → 60s 限流）。
    """
    import base64

    from app.core.config import settings
    from app.domains.auth.router import get_sms_service, get_user_service
    from app.domains.auth.service import UserService

    # 1. 修 AES key（26 字节 → 32 字节，合法 AES-256）
    valid_key = base64.b64encode(b"x" * 32).decode("ascii")
    monkeypatch.setattr(settings, "phone_encryption_key", f"base64:{valid_key}")

    # 2. 取 conftest 已设的同一个 fake_sms（lambda 返回的实例）
    fake = client.app.dependency_overrides[get_sms_service]()

    # 3. 清空 fake_sms 状态（store / counts / last_sent）—— 防本文件测试污染后续 test_health
    fake._store.clear()
    fake._last_sent.clear()
    fake._counts.clear()

    from app.core.database import get_db

    def _user_service_override(
        request: Request,
        db: Session = Depends(get_db),  # 必须用 Depends，否则 FastAPI 把它当 query param
    ):
        return UserService(db, fake)

    client.app.dependency_overrides[get_user_service] = _user_service_override
    yield
    # 不清 — conftest 的 finally 会清整个 dict


def _make_user(
    _db,
    user_id: int,
    name: str = "TestUser",
    phone_encrypted: str | None = None,
    phone_hash: str | None = None,
) -> User:
    user = User(
        id=user_id,
        name=name,
        display_name=f"{name}先生",
        status=UserStatus.ACTIVE,
        is_verified=True,
        credit_score=80.0,
        rating_avg=4.0,
        rating_count=0,
        phone_encrypted=phone_encrypted,
        phone_hash=phone_hash,
        last_login_at=datetime.now(timezone.utc),
    )
    with SessionLocal() as session:
        session.add(user)
        session.commit()
    return user


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ============================================================
#  POST /auth/sms-code  — 发送短信验证码
# ============================================================

class TestSendSmsCode:
    """POST /auth/sms-code 契约。"""

    def test_send_sms_code_returns_expire_in(
        self, client: TestClient, db
    ):
        """正常发送：返 200 + expire_in=300（5min 有效期）。

        测试用 InMemorySmsService（[conftest.py](backend/tests/conftest.py)），
        **验证码**不返回（安全要求）。
        """
        resp = client.post(
            "/v1/auth/sms-code",
            json={"phone": "13800138000", "purpose": "login"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["expire_in"] == 300
        # 响应里**不能**有验证码
        assert "code" not in data
        assert "sms_code" not in data

    def test_send_sms_code_rejects_invalid_phone(
        self, client: TestClient, db
    ):
        """手机号格式不对 → 400/10001。"""
        resp = client.post(
            "/v1/auth/sms-code",
            json={"phone": "12345"},  # 不是 11 位
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 10001

    def test_send_sms_code_rejects_non_chinese_phone(
        self, client: TestClient, db
    ):
        """非中国大陆号段 → 400（regex `^1[3-9]\\d{9}$`）。"""
        resp = client.post(
            "/v1/auth/sms-code",
            json={"phone": "22345678901"},
        )
        assert resp.status_code == 400

    def test_send_sms_code_60s_rate_limit(
        self, client: TestClient, db
    ):
        """60s 内重复发同号 → 40001 SmsSendError。"""
        phone = "13800138001"
        # 第一次成功
        r1 = client.post(
            "/v1/auth/sms-code",
            json={"phone": phone},
        )
        assert r1.status_code == 200
        # 第二次立即 → 限流
        r2 = client.post(
            "/v1/auth/sms-code",
            json={"phone": phone},
        )
        assert r2.status_code == 502
        body = r2.json()
        assert body["code"] == 40001
        assert "60 秒" in body["message"]

    def test_send_sms_code_5_per_hour_rate_limit(
        self, client: TestClient, db, monkeypatch
    ):
        """每小时最多 5 次（同号第 6 次 → 40001）。

        绕过 60s 限流（mock 60s 时间差）→ 触发 5/h 限流。
        """
        phone = "13800138002"

        def fake_time():
            # 返回递增的时间戳让 60s 限流通过
            fake_time.t += 120
            return fake_time.t

        fake_time.t = 0
        monkeypatch.setattr("time.time", fake_time)

        # 前 5 次都成功
        for i in range(5):
            r = client.post(
                "/v1/auth/sms-code",
                json={"phone": phone},
            )
            assert r.status_code == 200, f"第 {i+1} 次失败: {r.text}"
        # 第 6 次 → 5/h 限流
        r6 = client.post(
            "/v1/auth/sms-code",
            json={"phone": phone},
        )
        assert r6.status_code == 502
        assert r6.json()["code"] == 40001
        assert "过于频繁" in r6.json()["message"]


# ============================================================
#  POST /auth/login  — 短信登录
# ============================================================

class TestSmsLogin:
    """POST /auth/login 契约。"""

    def test_login_with_valid_code_creates_new_user(
        self, client: TestClient, db
    ):
        """新手机号 + 正确验证码 → 创建用户 + 返 access+refresh token。"""
        phone = "13800138003"
        # 1. 发送验证码
        r1 = client.post(
            "/v1/auth/sms-code",
            json={"phone": phone},
        )
        assert r1.status_code == 200

        # 2. 从 InMemorySmsService 拿到验证码（hack：通过 dependency override）
        from app.core.crypto import hash_phone
        from app.core.redis_client import sms_code_key
        from app.domains.auth.router import get_sms_service

        # 直接读 conftest 里的 _InMemorySmsService 实例
        from tests.conftest import _InMemorySmsService

        sms = client.app.dependency_overrides[get_sms_service]()
        assert isinstance(sms, _InMemorySmsService)
        phone_h = hash_phone(phone)
        code = sms._store[sms_code_key(phone_h, "login")]

        # 3. 用验证码登录
        r2 = client.post(
            "/v1/auth/login",
            json={"phone": phone, "sms_code": code},
        )
        assert r2.status_code == 200, r2.text
        data = r2.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        user_info = data["user"]
        assert user_info["id"] is not None
        assert user_info["name"] is not None
        # 新用户标记（在 user 对象内，不在顶层）
        assert user_info["is_new"] is True

        # 4. DB 里应有一个用户，phone_hash 唯一
        with SessionLocal() as session:
            users = session.query(User).all()
            assert len([u for u in users if u.phone_hash == phone_h]) == 1

    def test_login_with_existing_phone_returns_existing_user(
        self, client: TestClient, db
    ):
        """已有用户的手机号再登录 → 返同一 user.id + is_new=False。"""
        phone = "13800138004"
        from app.core.crypto import hash_phone

        # 1. 预创建用户（phone_hash 与 mock service 一致）
        existing = _make_user(
            db, 7777, name="已有用户", phone_hash=hash_phone(phone),
        )

        # 2. 发送验证码
        r1 = client.post("/v1/auth/sms-code", json={"phone": phone})
        assert r1.status_code == 200

        # 3. 拿验证码
        from app.core.redis_client import sms_code_key
        from app.domains.auth.router import get_sms_service
        from tests.conftest import _InMemorySmsService

        sms = client.app.dependency_overrides[get_sms_service]()
        phone_h = hash_phone(phone)
        code = sms._store[sms_code_key(phone_h, "login")]

        # 4. 登录
        r2 = client.post(
            "/v1/auth/login",
            json={"phone": phone, "sms_code": code},
        )
        assert r2.status_code == 200
        data = r2.json()["data"]
        # 返的 user.id = 已有用户
        assert data["user"]["id"] == existing.id
        assert data["user"]["is_new"] is False

    def test_login_with_wrong_code_returns_20001(
        self, client: TestClient, db
    ):
        """错误验证码 → 401/20001。"""
        phone = "13800138005"
        client.post("/v1/auth/sms-code", json={"phone": phone})

        r = client.post(
            "/v1/auth/login",
            json={"phone": phone, "sms_code": "9999"},  # 错的
        )
        assert r.status_code == 401
        assert r.json()["code"] == 20001

    def test_login_with_no_code_sent_returns_20002(
        self, client: TestClient, db
    ):
        """没发过验证码直接登录 → 401/20002 SmsCodeExpiredError。"""
        r = client.post(
            "/v1/auth/login",
            json={"phone": "13800138006", "sms_code": "1234"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == 20002

    def test_login_rejects_invalid_phone(
        self, client: TestClient, db
    ):
        """手机号格式错 → 400/10001。"""
        r = client.post(
            "/v1/auth/login",
            json={"phone": "abc", "sms_code": "1234"},
        )
        assert r.status_code == 400
        assert r.json()["code"] == 10001

    def test_login_code_is_one_time_use(
        self, client: TestClient, db
    ):
        """同一验证码只能用一次：第二次用 → 20002 SmsCodeExpiredError。"""
        phone = "13800138007"
        from app.core.crypto import hash_phone

        client.post("/v1/auth/sms-code", json={"phone": phone})
        from app.core.redis_client import sms_code_key
        from app.domains.auth.router import get_sms_service

        sms = client.app.dependency_overrides[get_sms_service]()
        phone_h = hash_phone(phone)
        code = sms._store[sms_code_key(phone_h, "login")]

        # 第一次成功
        r1 = client.post(
            "/v1/auth/login",
            json={"phone": phone, "sms_code": code},
        )
        assert r1.status_code == 200
        # 第二次（用同 code）→ 已过期
        r2 = client.post(
            "/v1/auth/login",
            json={"phone": phone, "sms_code": code},
        )
        assert r2.status_code == 401
        assert r2.json()["code"] == 20002


# ============================================================
#  POST /auth/refresh  — 刷新 token
# ============================================================

class TestRefreshToken:
    """POST /auth/refresh 契约。"""

    def test_refresh_with_valid_token_returns_new_pair(
        self, client: TestClient, db
    ):
        """有效 refresh token → 新 access + refresh token。"""
        _make_user(db, 1001, name="Alice")
        refresh = create_refresh_token(1001)

        resp = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data
        assert data["expires_in"] > 0
        # access_token 是新的（不同）
        assert data["access_token"] != refresh

    def test_refresh_with_access_token_returns_20003(
        self, client: TestClient, db
    ):
        """access token 当 refresh 用 → 20003（type 校验）。"""
        _make_user(db, 1001, name="Alice")
        access = create_access_token(1001)  # type=access

        resp = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": access},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == 20003
        assert "类型" in body["message"]

    def test_refresh_with_invalid_token_returns_20003(
        self, client: TestClient, db
    ):
        """无效/伪造 token → 20003。"""
        resp = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": "not-a-real-token"},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003

    def test_refresh_with_token_for_nonexistent_user_returns_20003(
        self, client: TestClient, db
    ):
        """token 有效但用户被删除 → 20003 '用户不存在'。"""
        # 用户 9999 不存在
        refresh = create_refresh_token(9999)
        resp = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == 20003
        assert "用户不存在" in body["message"]


# ============================================================
#  GET /auth/me  — 当前用户信息（[P1-3] TODO 占位）
# ============================================================

class TestGetMe:
    """GET /auth/me 当前行为锁定（TODO 未实现，返静态消息）。"""

    def test_me_returns_todo_placeholder(
        self, client: TestClient, db
    ):
        """[P1-3 已知缺口] /me 端点当前是 TODO，未用 current_user 依赖。

        锁定这个行为：返 {"message": "TODO: 实现 current_user 依赖"} 而非当前用户。
        防止有人无意中改了语义。
        """
        resp = client.get("/v1/auth/me", headers=_auth(1001))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "message" in data
        assert "TODO" in data["message"]

    def test_me_does_not_require_auth(
        self, client: TestClient, db
    ):
        """[锁定] /me 当前**不**鉴权（无 current_user 依赖）。"""
        resp = client.get("/v1/auth/me")
        assert resp.status_code == 200
