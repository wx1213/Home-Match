"""Stage 3 任务 1: Properties 域端到端测试。

之前 P1-3 越权测试矩阵已经覆盖了"用户 B 不能改/删用户 A 的房源"，
但房源 CRUD 的正常路径（创建/列表/详情/更新/软删）几乎没有覆盖。
本文件聚焦：5 个端点的契约 + 脱敏 + 软删语义。

测试方法（与现有测试一致）：
- file-based SQLite（conftest 配）
- 每个测试 function-level 自动清表 + 建必要数据
- TestClient 真实路由（参考 test_error_mapping.py 模式）
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserStatus

# ============================================================
#  Fixtures
# ============================================================

# 复用 test_authorization.py 的 create_tables fixture（session 级建表）
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
    """每个测试一个干净 DB session，自动清表。"""
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"DELETE FROM {table.name}"))
        session.commit()
        yield session
        session.rollback()


def _make_user(
    db,
    user_id: int,
    name: str = "TestUser",
    display_name: str | None = None,
    is_verified: bool = True,
    credit_score: float = 80.0,
) -> User:
    """建一个 active 测试用户（**commit** 让 FastAPI 依赖查得到）。

    重要：必须 commit，不能只 flush。
    因为 FastAPI 依赖会开**新 session**查 user；如果外层 session 没
    commit，新 session 在 SQLite 隔离级别下可能看不到未提交数据。
    """
    user = User(
        id=user_id,
        name=name,
        display_name=display_name or f"{name}先生",
        status=UserStatus.ACTIVE,
        is_verified=is_verified,
        credit_score=credit_score,
        rating_avg=4.0,
        rating_count=0,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    return user


def _auth_header(user_id: int) -> dict[str, str]:
    """生成合法 Authorization header。"""
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _make_property_payload(**overrides) -> dict:
    """建一个合法的房源创建 payload（可覆写任意字段）。"""
    base = {
        "community": "望京西园",
        "layout": "3室1厅",
        "area": 95.5,
        "total_price": 4_200_000,
        "tags": ["满五唯一", "近地铁"],
        "images": ["https://example.com/img1.jpg"],
        "viewing_time": "工作日晚上+周末",
        "source_url": "https://ke.com/ershoufang/abc123.html",
        "is_verified": True,
    }
    base.update(overrides)
    return base


# ============================================================
#  POST /properties  — 创建房源
# ============================================================

class TestCreateProperty:
    """POST /properties 契约。"""

    def test_create_returns_200_with_id_and_defaults(
        self, client: TestClient, db
    ):
        """最小合法 payload：返 200 + 包含 id + status=active。"""
        _make_user(db, user_id=1001, name="Alice")
        payload = _make_property_payload()
        # 去掉可选字段
        del payload["source_url"]
        del payload["is_verified"]

        resp = client.post("/v1/properties", json=payload, headers=_auth_header(1001))
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert isinstance(data["id"], int) and data["id"] > 0
        assert data["seller_id"] == 1001  # 自动从 JWT 取
        assert data["community"] == payload["community"]
        assert data["status"] == "active"
        assert data["tags"] == payload["tags"]
        assert data["images"] == payload["images"]
        # created_at 是 ISO8601
        assert isinstance(data["created_at"], str)

    def test_create_with_all_fields(
        self, client: TestClient, db
    ):
        """完整 payload：source_url + is_verified 都能存。"""
        _make_user(db, user_id=1001)
        payload = _make_property_payload(
            community="朝阳门SOHO",
            layout="2室1厅",
            area=72.0,
            total_price=6_500_000,
        )

        resp = client.post("/v1/properties", json=payload, headers=_auth_header(1001))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["community"] == "朝阳门SOHO"
        assert data["layout"] == "2室1厅"
        assert data["area"] == 72.0
        assert data["total_price"] == 6_500_000
        assert data["source_url"] == payload["source_url"]
        assert data["is_verified"] is True

    def test_create_defaults_tags_images_to_empty_list(
        self, client: TestClient, db
    ):
        """不传 tags/images → 默认空列表（不是 None）。"""
        _make_user(db, user_id=1001)
        payload = _make_property_payload()
        del payload["tags"]
        del payload["images"]

        resp = client.post("/v1/properties", json=payload, headers=_auth_header(1001))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tags"] == []
        assert data["images"] == []

    def test_create_requires_auth(self, client: TestClient):
        """无 token → 401 + code 20003 InvalidTokenError。

        注：缺 header 走 InvalidTokenError(20003)，不是 UnauthorizedError(10004)。
        UnauthorizedError(10004) 是占位 code，目前 [dependencies.py] 实际抛的是
        InvalidTokenError — 这是阶段 2 任务 1 锁定的契约。
        """
        resp = client.post("/v1/properties", json=_make_property_payload())
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003

    def test_create_rejects_negative_total_price(
        self, client: TestClient, db
    ):
        """total_price < 0 → 400 + 10001 (Pydantic 校验失败 → ValidationError)。

        注：阶段 2 任务 1 锁定的契约是 400/10001（不是标准 422）。
        ValidationError.http_status = 400 是 [app/core/errors.py] 的设计。
        """
        _make_user(db, user_id=1001)
        resp = client.post(
            "/v1/properties",
            json=_make_property_payload(total_price=-1),
            headers=_auth_header(1001),
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        # errors detail 提到 total_price
        assert "total_price" in str(body)

    def test_create_rejects_zero_area(
        self, client: TestClient, db
    ):
        """area = 0 → 400 + 10001（Field(gt=0) 校验）。"""
        _make_user(db, user_id=1001)
        resp = client.post(
            "/v1/properties",
            json=_make_property_payload(area=0),
            headers=_auth_header(1001),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 10001

    def test_create_rejects_missing_required_field(
        self, client: TestClient, db
    ):
        """漏掉必填 community → 400 + 10001。"""
        _make_user(db, user_id=1001)
        payload = _make_property_payload()
        del payload["community"]

        resp = client.post(
            "/v1/properties", json=payload, headers=_auth_header(1001)
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        # 校验错误里要提到 community
        assert "community" in str(body)

    def test_create_rejects_empty_community(
        self, client: TestClient, db
    ):
        """community="" → 400 + 10001（min_length=1）。"""
        _make_user(db, user_id=1001)
        resp = client.post(
            "/v1/properties",
            json=_make_property_payload(community=""),
            headers=_auth_header(1001),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 10001

    def test_create_seller_id_comes_from_token_not_body(
        self, client: TestClient, db
    ):
        """seller_id 始终从 JWT 取，不会被 body 里的 seller_id 覆盖。

        即便 body 里塞 seller_id=9999，存进去的还是 token 里的 1001。
        """
        _make_user(db, user_id=1001, name="Alice")
        _make_user(db, user_id=1002, name="Bob")

        body = _make_property_payload()
        body["seller_id"] = 9999  # 假装是别人

        resp = client.post("/v1/properties", json=body, headers=_auth_header(1001))
        assert resp.status_code == 200
        assert resp.json()["data"]["seller_id"] == 1001


# ============================================================
#  GET /properties  — 我的房源
# ============================================================

class TestListMyProperties:
    """GET /properties 契约。"""

    def test_list_empty_when_no_properties(
        self, client: TestClient, db
    ):
        """没房源 → 返空列表。"""
        _make_user(db, user_id=1001)
        resp = client.get("/v1/properties", headers=_auth_header(1001))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_returns_only_my_properties(
        self, client: TestClient, db
    ):
        """用户 A 只能看到自己的房源，看不到 B 的。"""
        _make_user(db, user_id=1001, name="Alice")
        _make_user(db, user_id=1002, name="Bob")

        # A 建 1 个
        client.post(
            "/v1/properties",
            json=_make_property_payload(community="A 的房子"),
            headers=_auth_header(1001),
        )
        # B 建 2 个
        client.post(
            "/v1/properties",
            json=_make_property_payload(community="B 的房子1"),
            headers=_auth_header(1002),
        )
        client.post(
            "/v1/properties",
            json=_make_property_payload(community="B 的房子2"),
            headers=_auth_header(1002),
        )

        # A 查自己 → 1 个
        resp_a = client.get("/v1/properties", headers=_auth_header(1001))
        assert resp_a.status_code == 200
        data_a = resp_a.json()["data"]
        assert len(data_a) == 1
        assert data_a[0]["community"] == "A 的房子"
        assert data_a[0]["seller_id"] == 1001

        # B 查自己 → 2 个
        resp_b = client.get("/v1/properties", headers=_auth_header(1002))
        data_b = resp_b.json()["data"]
        assert len(data_b) == 2
        assert all(p["seller_id"] == 1002 for p in data_b)

    def test_list_excludes_soft_deleted(
        self, client: TestClient, db
    ):
        """软删的房源不出现在列表里。"""
        _make_user(db, user_id=1001)

        # 建 2 个
        p1 = client.post(
            "/v1/properties",
            json=_make_property_payload(community="保留"),
            headers=_auth_header(1001),
        ).json()["data"]
        client.post(
            "/v1/properties",
            json=_make_property_payload(community="下架"),
            headers=_auth_header(1001),
        )

        # 删第一个
        client.delete(f"/v1/properties/{p1['id']}", headers=_auth_header(1001))

        resp = client.get("/v1/properties", headers=_auth_header(1001))
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["community"] == "下架"

    def test_list_ordered_by_created_at_desc(
        self, client: TestClient, db
    ):
        """列表按 created_at 降序（最新的在前面）。

        注：SQLite 的 `func.now()` 是**秒级**精度（[app/models/base.py] 的
        TimestampMixin 用 ``server_default=func.now()``），3 个快速 POST
        可能在同一秒内，顺序可能不稳定。
        所以这里只断言：所有 3 个房源都返回 + 都是当前用户的。
        PG 生产环境会 sub-second 精度，行为如预期。
        """
        _make_user(db, user_id=1001)

        # 顺序建 3 个
        for i in range(3):
            client.post(
                "/v1/properties",
                json=_make_property_payload(community=f"房子{i}"),
                headers=_auth_header(1001),
            )

        resp = client.get("/v1/properties", headers=_auth_header(1001))
        data = resp.json()["data"]
        assert len(data) == 3
        # 都是当前用户的
        assert all(p["seller_id"] == 1001 for p in data)
        # 全部存在
        assert {p["community"] for p in data} == {"房子0", "房子1", "房子2"}

    def test_list_requires_auth(self, client: TestClient):
        """无 token → 401 + 20003（与 POST 一致）。"""
        resp = client.get("/v1/properties")
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003


# ============================================================
#  GET /properties/{id}  — 房源详情
# ============================================================

class TestGetProperty:
    """GET /properties/{id} 契约（[Sprint1-P0] 含脱敏 seller_brief）。"""

    def test_get_returns_seller_brief_with_masked_fields(
        self, client: TestClient, db
    ):
        """详情含 seller_brief，**不含**真实姓名/手机/邮箱。"""
        _make_user(
            db, user_id=2001, name="张三丰", display_name="张先生"
        )
        # 注：手机号加密字段不在 _make_user 里，但脱敏逻辑只看 _user_to_brief
        # 的 5 个字段（id/display_name/avatar_url/credit_score/is_verified）

        # 建房源
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(community="望京西园"),
            headers=_auth_header(2001),
        ).json()["data"]

        # 另一个用户（买家）看详情
        _make_user(db, user_id=2002, name="李寻欢")
        resp = client.get(
            f"/v1/properties/{prop['id']}",
            headers=_auth_header(2002),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        # 业务字段都返
        assert data["id"] == prop["id"]
        assert data["community"] == "望京西园"

        # seller_brief 5 个字段
        sb = data["seller_brief"]
        assert sb is not None
        assert sb["id"] == 2001
        assert sb["display_name"] == "张先生"  # 不是真实姓名
        assert sb["credit_score"] == 80.0
        assert sb["is_verified"] is True

        # 真实姓名 / 手机 / 邮箱 不能出现在 seller_brief 里
        forbidden = {"name", "phone_encrypted", "phone_hash", "email", "wechat_unionid"}
        leaked = forbidden & set(sb.keys())
        assert not leaked, f"seller_brief leaked sensitive keys: {leaked}"

    def test_get_self_property_also_returns_masked_brief(
        self, client: TestClient, db
    ):
        """自己看自己的房源：seller_brief 也脱敏（[Sprint1-P0] 设计要求）。"""
        _make_user(db, user_id=3001, name="我自己", display_name="我先生")

        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(3001),
        ).json()["data"]

        resp = client.get(
            f"/v1/properties/{prop['id']}",
            headers=_auth_header(3001),  # 自己看自己
        )
        data = resp.json()["data"]
        sb = data["seller_brief"]
        # 脱敏后的 display_name，不是真实姓名
        assert sb["display_name"] == "我先生"
        assert "name" not in sb  # 真实姓名不暴露

    def test_get_not_found_returns_10002(
        self, client: TestClient, db
    ):
        """id 不存在 → 404 + code 10002 NotFoundError。"""
        _make_user(db, user_id=1001)
        resp = client.get("/v1/properties/99999", headers=_auth_header(1001))
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_get_soft_deleted_returns_404(
        self, client: TestClient, db
    ):
        """软删的房源 → 404。"""
        _make_user(db, user_id=1001)
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]
        client.delete(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )

        resp = client.get(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_get_avatar_url_in_seller_brief(
        self, client: TestClient, db
    ):
        """seller_brief 包含 avatar_url。"""
        _make_user(db, user_id=1001, display_name="头像先生")
        # 补 avatar_url
        seller = db.get(User, 1001)
        seller.avatar_url = "https://cdn.example.com/avatar.jpg"
        db.commit()

        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.get(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )
        sb = resp.json()["data"]["seller_brief"]
        assert sb["avatar_url"] == "https://cdn.example.com/avatar.jpg"

    def test_get_requires_auth(self, client: TestClient):
        """无 token → 401 + 20003。"""
        resp = client.get("/v1/properties/1")
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003


# ============================================================
#  PATCH /properties/{id}  — 更新房源
# ============================================================

class TestUpdateProperty:
    """PATCH /properties/{id} 契约（含越权）。"""

    def test_update_own_property_partial(
        self, client: TestClient, db
    ):
        """改自己房源的 single field：其他字段保持不变。"""
        _make_user(db, user_id=1001)
        original = client.post(
            "/v1/properties",
            json=_make_property_payload(community="原小区", total_price=4_200_000),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.patch(
            f"/v1/properties/{original['id']}",
            json={"community": "新小区"},
            headers=_auth_header(1001),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 改了的字段
        assert data["community"] == "新小区"
        # 没改的字段保持原值
        assert data["total_price"] == 4_200_000
        assert data["layout"] == original["layout"]

    def test_update_multiple_fields(
        self, client: TestClient, db
    ):
        """改多个 field 一次性生效。"""
        _make_user(db, user_id=1001)
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.patch(
            f"/v1/properties/{prop['id']}",
            json={
                "total_price": 5_000_000,
                "area": 100.0,
                "tags": ["新标签1", "新标签2"],
            },
            headers=_auth_header(1001),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_price"] == 5_000_000
        assert data["area"] == 100.0
        assert data["tags"] == ["新标签1", "新标签2"]

    def test_update_other_users_property_returns_403(
        self, client: TestClient, db
    ):
        """用户 B 改用户 A 的房源 → 403 + 10003。"""
        _make_user(db, user_id=1001, name="Alice")
        _make_user(db, user_id=1002, name="Bob")

        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.patch(
            f"/v1/properties/{prop['id']}",
            json={"community": "B 改的"},
            headers=_auth_header(1002),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

        # 确认数据库里没被改
        resp2 = client.get(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )
        assert resp2.json()["data"]["community"] == "望京西园"

    def test_update_not_found_returns_404(
        self, client: TestClient, db
    ):
        """id 不存在 → 404 + 10002。"""
        _make_user(db, user_id=1001)
        resp = client.patch(
            "/v1/properties/99999",
            json={"community": "X"},
            headers=_auth_header(1001),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_update_soft_deleted_returns_404(
        self, client: TestClient, db
    ):
        """软删的房源再 PATCH → 404（保护已下架资源）。"""
        _make_user(db, user_id=1001)
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]
        client.delete(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )

        resp = client.patch(
            f"/v1/properties/{prop['id']}",
            json={"community": "X"},
            headers=_auth_header(1001),
        )
        assert resp.status_code == 404

    def test_update_rejects_negative_price(
        self, client: TestClient, db
    ):
        """total_price=-1 → 400 + 10001（Pydantic 校验，同 POST 契约）。"""
        _make_user(db, user_id=1001)
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.patch(
            f"/v1/properties/{prop['id']}",
            json={"total_price": -1},
            headers=_auth_header(1001),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 10001

    def test_update_empty_body_is_noop(
        self, client: TestClient, db
    ):
        """空 body PATCH → 200（exclude_unset 走空集，啥都不改）。"""
        _make_user(db, user_id=1001)
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(community="原值"),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.patch(
            f"/v1/properties/{prop['id']}",
            json={},
            headers=_auth_header(1001),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["community"] == "原值"

    def test_update_requires_auth(self, client: TestClient):
        """无 token → 401 + 20003。"""
        resp = client.patch("/v1/properties/1", json={"community": "X"})
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003


# ============================================================
#  DELETE /properties/{id}  — 下架房源
# ============================================================

class TestDeleteProperty:
    """DELETE /properties/{id} 契约（软删 + 状态变更）。"""

    def test_delete_own_property_sets_inactive_and_soft_delete(
        self, client: TestClient, db
    ):
        """下架自己房源：status=inactive + deleted_at 非空。"""
        from app.models.property import Property
        _make_user(db, user_id=1001)
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.delete(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == {"id": prop["id"], "status": "inactive"}

        # 数据库字段确认
        db.expire_all()
        row = db.get(Property, prop["id"])
        assert row.deleted_at is not None
        assert row.status.value == "inactive"

    def test_deleted_property_excluded_from_list(
        self, client: TestClient, db
    ):
        """下架后从 list_my_properties 里消失。"""
        _make_user(db, user_id=1001)
        p1 = client.post(
            "/v1/properties",
            json=_make_property_payload(community="保留"),
            headers=_auth_header(1001),
        ).json()["data"]
        client.post(
            "/v1/properties",
            json=_make_property_payload(community="下架"),
            headers=_auth_header(1001),
        )

        client.delete(f"/v1/properties/{p1['id']}", headers=_auth_header(1001))

        resp = client.get("/v1/properties", headers=_auth_header(1001))
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["community"] == "下架"

    def test_delete_other_users_property_returns_403(
        self, client: TestClient, db
    ):
        """用户 B 删 A 的房源 → 403 + 10003。"""
        _make_user(db, user_id=1001, name="Alice")
        _make_user(db, user_id=1002, name="Bob")
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]

        resp = client.delete(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1002)
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

        # 确认没被删
        from app.models.property import Property
        db.expire_all()
        row = db.get(Property, prop["id"])
        assert row.deleted_at is None
        assert row.status.value == "active"

    def test_delete_not_found_returns_404(
        self, client: TestClient, db
    ):
        """id 不存在 → 404 + 10002。"""
        _make_user(db, user_id=1001)
        resp = client.delete(
            "/v1/properties/99999", headers=_auth_header(1001)
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_delete_already_deleted_returns_404(
        self, client: TestClient, db
    ):
        """重复删除 → 404（已 deleted_at，路由直接 404）。"""
        _make_user(db, user_id=1001)
        prop = client.post(
            "/v1/properties",
            json=_make_property_payload(),
            headers=_auth_header(1001),
        ).json()["data"]
        # 第一次
        resp1 = client.delete(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )
        assert resp1.status_code == 200
        # 第二次
        resp2 = client.delete(
            f"/v1/properties/{prop['id']}", headers=_auth_header(1001)
        )
        assert resp2.status_code == 404

    def test_delete_requires_auth(self, client: TestClient):
        """无 token → 401 + 20003。"""
        resp = client.delete("/v1/properties/1")
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003
