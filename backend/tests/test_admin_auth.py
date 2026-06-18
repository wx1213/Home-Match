"""Stage 3 任务 6: Admin 链路测试。

覆盖：
- require_admin Depends：普通用户 403 / admin 200 / 无 token 401 / refresh token 401
- 登录响应（UserInfo）：包含 is_admin 字段（普通用户 false / admin true）
- /v1/admin/me 占位端点：返回 {id, name, is_admin: true}

参考：test_auth_router.py 的 _make_user + _auth + drop_all/create_all 模式。
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
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


def _make_user(
    user_id: int,
    name: str = "TestUser",
    is_admin: bool = False,
) -> User:
    """构造测试 user 并写入 DB。"""
    user = User(
        id=user_id,
        name=name,
        display_name=f"{name}先生",
        status=UserStatus.ACTIVE,
        is_verified=True,
        is_admin=is_admin,
        credit_score=80.0,
        rating_avg=4.0,
        rating_count=0,
        last_login_at=datetime.now(timezone.utc),
    )
    with SessionLocal() as session:
        session.add(user)
        session.commit()
    return user


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ============================================================
#  /v1/admin/me — 端到端
# ============================================================

class TestAdminMeEndpoint:
    """GET /v1/admin/me 链路：JWT 解析 → get_current_user → require_admin → 端点。"""

    def test_normal_user_returns_403(self, client: TestClient):
        """普通用户（is_admin=False）调 admin 端点 → 403 PermissionDeniedError（code 10003）。"""
        user = _make_user(user_id=101, name="norm", is_admin=False)

        r = client.get("/v1/admin/me", headers=_auth(user.id))

        assert r.status_code == 403
        body = r.json()
        assert body["code"] == 10003
        assert "admin" in body.get("message", "").lower()

    def test_admin_user_returns_200(self, client: TestClient):
        """admin 用户（is_admin=True）调 admin 端点 → 200 + is_admin: true。"""
        user = _make_user(user_id=102, name="adm", is_admin=True)

        r = client.get("/v1/admin/me", headers=_auth(user.id))

        assert r.status_code == 200
        body = r.json()
        assert body["id"] == user.id
        assert body["name"] == user.name
        assert body["is_admin"] is True

    def test_no_token_returns_401(self, client: TestClient):
        """无 Authorization header → 401 InvalidTokenError（code 20003）。"""
        r = client.get("/v1/admin/me")
        assert r.status_code == 401
        assert r.json()["code"] == 20003  # InvalidTokenError

    def test_refresh_token_returns_401(self, client: TestClient):
        """refresh token 调 admin 端点 → 401（payload type 错）。"""
        user = _make_user(user_id=103, name="refresh", is_admin=True)
        refresh_token = create_refresh_token(user.id)
        r = client.get(
            "/v1/admin/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == 20003  # InvalidTokenError

    def test_deleted_user_returns_401(self, client: TestClient):
        """已软删 user 的 token → 401（get_current_user 过滤 deleted_at）。"""
        user = _make_user(user_id=104, name="del", is_admin=True)
        # 软删
        with SessionLocal() as session:
            u = session.get(User, user.id)
            u.deleted_at = datetime.now(timezone.utc)
            session.add(u)
            session.commit()

        r = client.get("/v1/admin/me", headers=_auth(user.id))
        assert r.status_code == 401


# ============================================================
#  UserInfo 登录响应 — 暴露 is_admin
# ============================================================

class TestUserInfoSchema:
    """UserInfo 登录响应应包含 is_admin 字段（APP 端用于显示 admin 入口）。"""

    def test_user_info_has_is_admin_field(self):
        """schema 字段声明：is_admin 默认 False。"""
        from app.domains.auth.schemas import UserInfo

        assert "is_admin" in UserInfo.model_fields
        # 默认值
        info = UserInfo(
            id=1, name="x", display_name=None, avatar_url=None,
            phone_mask=None, credit_score=80.0,
        )
        assert info.is_admin is False

    def test_build_login_response_includes_is_admin_normal_user(self, db):
        """build_login_response 构造的 UserInfo 包含 is_admin=False。"""
        from app.domains.auth.service import UserService
        from unittest.mock import MagicMock

        user = _make_user(user_id=201, name="norm", is_admin=False)
        with SessionLocal() as session:
            svc = UserService(session, MagicMock())
            resp = svc.build_login_response(user, is_new=False)
        assert resp.user.is_admin is False
        assert resp.user.is_verified is True

    def test_build_login_response_includes_is_admin_admin_user(self, db):
        """build_login_response 构造的 UserInfo 包含 is_admin=True（admin 链路暴露）。"""
        from app.domains.auth.service import UserService
        from unittest.mock import MagicMock

        user = _make_user(user_id=202, name="adm", is_admin=True)
        with SessionLocal() as session:
            svc = UserService(session, MagicMock())
            resp = svc.build_login_response(user, is_new=False)
        assert resp.user.is_admin is True


# ============================================================
#  UserResponse 完整用户信息 — 暴露 is_admin
# ============================================================

class TestUserResponseSchema:
    """UserResponse（含 /me 等）应包含 is_admin 字段。"""

    def test_user_response_exposes_is_admin(self, db):
        """UserResponse.from_attributes 路径下，is_admin 应被正确映射。"""
        from app.schemas.business import UserResponse

        user = _make_user(user_id=301, name="adm", is_admin=True)
        with SessionLocal() as session:
            db_user = session.get(User, user.id)
            resp = UserResponse.model_validate(db_user)
        assert resp.is_admin is True
        assert resp.id == user.id
        assert resp.name == user.name
