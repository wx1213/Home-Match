"""P1-3 越权测试矩阵。

验证：A 用户访问/操作 B 用户的资源时，API 应返回 403 PermissionDeniedError。

测试方法：
- 每个测试创建两个用户 A 和 B
- A 创建资源（property / demand / invitation / cooperation）
- B 拿着自己合法的 token 去操作 A 的资源
- 断言响应是 403 + code 10003

覆盖的端点（已有防护 + 应被拦截的）：
1. PATCH /properties/{id}       — 改别人房源
2. DELETE /properties/{id}      — 下架别人房源
3. DELETE /demands/{id}         — 关闭别人需求
4. POST   /invitations          — 用别人需求发起邀请
5. POST   /invitations/{id}/accept   — 别人接单
6. POST   /invitations/{id}/reject   — 别人拒绝
7. POST   /cooperations/.../confirm  — 别人确认方案
8. POST   /cooperations/.../decline  — 别人拒绝方案
9. POST   /proposals            — 别人提交方案
10. GET    /invitations/{id}    — 看别人参与的邀请
11. GET    /cooperations/{id}   — 看别人参与的合作
12. POST   /reviews             — 给别人的合作写评价
13. 不带 token → 401 (UnauthorizedError 10004)

⚠️ 已知越权缺口（不在 P1-3 修复范围，仅记录）：
- GET /properties/{id}     任意登录用户可查看任意房源
- GET /demands/{id}        任意登录用户可查看任意需求
- GET /demands/{id}/recommendations  任意登录用户可看任意需求的推荐
- GET /proposals           任意登录用户可查看任意方案
- GET /reviews             任意登录用户可查看任意合作的评价
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserStatus

# ============================================================
#  Fixtures
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Session 级：建表（SQLite in-memory 不持久，所以要显式建）。

    注：user.py 的 wechat_unionid 字段同时有 `unique=True, index=True` 和
    `__table_args__` 里的 `Index("ix_users_wechat_unionid", ...)`，会导致同名
    索引冲突。所以先 drop_all 再 create_all 保证干净状态。
    """
    # 导入所有 model 让 Base.metadata 知道它们
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
    # 不 drop，session 结束自动清理


@pytest.fixture()
def users():
    """创两个用户：A (id=101) 和 B (id=102)。每个测试独立（自动清表）。"""
    with SessionLocal() as db:
        # 清表
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(text(f"DELETE FROM {table.name}"))
        # 建 A 和 B
        for uid, name in [(101, "Alice"), (102, "Bob")]:
            db.add(User(
                id=uid,
                name=name,
                display_name=name + "先生",
                status=UserStatus.ACTIVE,
                is_verified=True,
                credit_score=80.0,
                rating_avg=4.0,
                rating_count=0,
                last_login_at=datetime.now(timezone.utc),
            ))
        db.commit()
    return {
        "A_id": 101,
        "B_id": 102,
        "A_h": _auth_header(101),
        "B_h": _auth_header(102),
    }


def _make_extra_user(name: str, user_id: int) -> None:
    """在独立 session 中创建额外用户（不持有 session 返回给测试）。"""
    with SessionLocal() as db:
        db.add(User(
            id=user_id,
            name=name,
            display_name=name + "先生",
            status=UserStatus.ACTIVE,
            is_verified=True,
            credit_score=80.0,
            rating_avg=4.0,
            rating_count=0,
            last_login_at=datetime.now(timezone.utc),
        ))
        db.commit()


def _auth_header(user_id: int) -> dict[str, str]:
    """生成合法 Authorization header。"""
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


# ============================================================
#  工具断言
# ============================================================

def assert_forbidden(resp, label: str) -> None:
    """断言响应是 403 PermissionDeniedError。"""
    assert resp.status_code == 403, (
        f"[{label}] expected 403, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("code") == 10003, (
        f"[{label}] expected code 10003, got {body.get('code')}: {body}"
    )


def assert_unauthorized(resp, label: str) -> None:
    """断言响应是 401 UnauthorizedError。"""
    assert resp.status_code == 401, (
        f"[{label}] expected 401, got {resp.status_code}: {resp.text}"
    )


# ============================================================
#  Test cases
# ============================================================

class TestUnauthenticatedRequests:
    """P1-3 #13: 不带 token 应 401。"""

    def test_property_update_without_token(self, client: TestClient):
        resp = client.patch("/v1/properties/1", json={"community": "X"})
        assert_unauthorized(resp, "PATCH /properties/1 no token")

    def test_demand_delete_without_token(self, client: TestClient):
        resp = client.delete("/v1/demands/1")
        assert_unauthorized(resp, "DELETE /demands/1 no token")

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.patch(
            "/v1/properties/1",
            json={"community": "X"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert_unauthorized(resp, "PATCH /properties/1 invalid token")


class TestPropertyAuth:
    """P1-3 #1-2: 房源越权。"""

    def test_B_cannot_update_A_property(self, client: TestClient, users):
        # A 创建房源
        prop = client.post(
            "/v1/properties",
            json={
                "community": "望京西园",
                "layout": "3室1厅",
                "area": 95.5,
                "total_price": 4_200_000,
                "tags": ["近地铁"],
                "images": [],
                "viewing_time": "工作日晚上",
            },
            headers=users["A_h"],
        ).json()["data"]

        # B 尝试改 A 的房源 → 403
        resp = client.patch(
            f"/v1/properties/{prop['id']}",
            json={"community": "改我试试"},
            headers=users["B_h"],
        )
        assert_forbidden(resp, "B updates A's property")

    def test_B_cannot_delete_A_property(self, client: TestClient, users):
        prop = client.post(
            "/v1/properties",
            json={
                "community": "X",
                "layout": "1室",
                "area": 50.0,
                "total_price": 1_000_000,
                "tags": [],
                "images": [],
                "viewing_time": "随时",
            },
            headers=users["A_h"],
        ).json()["data"]

        resp = client.delete(f"/v1/properties/{prop['id']}", headers=users["B_h"])
        assert_forbidden(resp, "B deletes A's property")


class TestDemandAuth:
    """P1-3 #3: 需求越权。"""

    def test_B_cannot_close_A_demand(self, client: TestClient, users):
        demand = client.post(
            "/v1/demands",
            json={
                "district": "朝阳区",
                "price_min": 3_000_000,
                "price_max": 5_000_000,
                "layouts": ["2室1厅"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        resp = client.delete(f"/v1/demands/{demand['id']}", headers=users["B_h"])
        assert_forbidden(resp, "B closes A's demand")


class TestInvitationAuth:
    """P1-3 #4-6, #10: 邀请越权。"""

    def test_B_cannot_invite_from_A_demand(self, client: TestClient, users):
        # A 创建需求
        demand = client.post(
            "/v1/demands",
            json={
                "district": "朝阳区",
                "price_min": 3_000_000,
                "price_max": 5_000_000,
                "layouts": ["2室1厅"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        # B 拿 A 的需求去邀请 C（=B 假装自己是 A 的需求方）→ 403
        resp = client.post(
            "/v1/invitations",
            json={
                "demand_id": demand["id"],
                "seller_id": users["B_id"],
                "note": "我偷你的需求",
            },
            headers=users["B_h"],
        )
        assert_forbidden(resp, "B invites from A's demand")

    def test_C_cannot_view_AB_invitation(self, client: TestClient, users):
        """第三方 C 看不到 A-B 之间的邀请。"""
        # 创建 C
        _make_extra_user("Carol", 103)
        c_h = _auth_header(103)

        # A 创建需求
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        # A 邀请 B
        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]

        # C 试图看 A→B 的邀请 → 403
        resp = client.get(f"/v1/invitations/{inv['id']}", headers=c_h)
        assert_forbidden(resp, "C views A-B invitation")

    def test_buyer_cannot_accept_own_invitation(self, client: TestClient, users):
        """A 创建邀请（buyer=A, seller=B），A 尝试自己接单 → 403。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]

        # A (buyer) 尝试接单 → 403（accept 是卖方权限）
        resp = client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["A_h"])
        assert_forbidden(resp, "A (buyer) accepts own invitation")

    def test_buyer_cannot_reject_own_invitation(self, client: TestClient, users):
        """A (buyer) 尝试 reject 自己的邀请 → 403。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]

        resp = client.post(f"/v1/invitations/{inv['id']}/reject", headers=users["A_h"])
        assert_forbidden(resp, "A (buyer) rejects own invitation")


class TestProposalAuth:
    """P1-3 #9: 方案越权。"""

    def test_buyer_cannot_submit_proposal(self, client: TestClient, users):
        """A (buyer) 试图为 A→B 的邀请提交方案 → 403。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]

        # B 先接单（才能提交方案）
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])

        # A (buyer) 试图提交方案 → 403
        resp = client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={
                "content": "A 假装自己是卖方提交方案，必须被拒 20+字符的方案内容。",
                "fit_points": "骗你",
            },
            headers=users["A_h"],
        )
        assert_forbidden(resp, "A (buyer) submits proposal")


class TestCooperationAuth:
    """P1-3 #7-8, #11: 合作越权。"""

    def _setup_handshaked_coop(self, client, users) -> dict[str, Any]:
        """建一个已握手的合作（buyer=A, seller=B）。返回 coop dict。"""
        # A 创建需求
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        # A 邀请 B
        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]

        # B 接单 + 提交方案
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])
        client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={
                "content": "B 提交的合作方案，详细描述客户的购房需求和匹配要点，超 20 字。",
                "fit_points": "总价匹配",
            },
            headers=users["B_h"],
        )

        # A 确认方案 → 握手
        coop = client.post(
            f"/v1/invitations/{inv['id']}/confirm",
            headers=users["A_h"],
        ).json()["data"]
        return coop

    def test_C_cannot_view_AB_cooperation(self, client: TestClient, users):
        """第三方 C 看不到 A-B 之间的合作。"""
        _make_extra_user("Carol", 103)
        c_h = _auth_header(103)

        coop = self._setup_handshaked_coop(client, users)
        resp = client.get(f"/v1/cooperations/{coop['id']}", headers=c_h)
        assert_forbidden(resp, "C views A-B cooperation")

    def test_seller_cannot_confirm_own_proposal(self, client: TestClient, users):
        """B (seller) 试图 confirm → 403（confirm 是 buyer 权限）。"""
        # 复用 setup 但只走到方案提交
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])
        client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={"content": "B 提交方案超 20 字符的方案内容描述详细。"},
            headers=users["B_h"],
        )

        # B 试图 confirm → 403
        resp = client.post(f"/v1/invitations/{inv['id']}/confirm", headers=users["B_h"])
        assert_forbidden(resp, "B (seller) confirms own proposal")

    def test_seller_cannot_decline_own_proposal(self, client: TestClient, users):
        """B (seller) 试图 decline → 403。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])
        client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={"content": "B 提交方案超 20 字符的方案内容描述详细。"},
            headers=users["B_h"],
        )

        resp = client.post(f"/v1/invitations/{inv['id']}/decline", headers=users["B_h"])
        assert_forbidden(resp, "B (seller) declines own proposal")


class TestReviewAuth:
    """P1-3 #12: 评价越权。"""

    def _setup_handshaked_coop(self, client, users) -> dict[str, Any]:
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X",
                "price_min": 1_000_000,
                "price_max": 2_000_000,
                "layouts": ["1室"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]

        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])
        client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={"content": "B 提交方案超 20 字符的方案内容描述详细。"},
            headers=users["B_h"],
        )
        return client.post(
            f"/v1/invitations/{inv['id']}/confirm",
            headers=users["A_h"],
        ).json()["data"]

    def test_C_cannot_review_AB_cooperation(self, client: TestClient, users):
        """第三方 C 不能给 A-B 的合作写评价。"""
        _make_extra_user("Carol", 103)
        c_h = _auth_header(103)

        coop = self._setup_handshaked_coop(client, users)
        resp = client.post(
            f"/v1/cooperations/{coop['id']}/review",
            json={"rating": 5, "comment": "我路过给个好评"},
            headers=c_h,
        )
        assert_forbidden(resp, "C reviews A-B cooperation")


# ============================================================
#  已知缺口文档（不在 P1-3 修复范围）
# ============================================================

class TestKnownGaps:
    """记录 P1-3 已发现的越权缺口（验收「不通过」= 提醒待 P2 修复）。

    这些测试故意不写断言 status_code==403，而是断言「当前是 200/404 等」
    来文档化「现在是没保护的」状态。等 P2 修复时改回 403 即可。
    """

    def test_GET_property_has_no_auth(self, client: TestClient, users):
        """GET /properties/{id} 任意登录用户可查看（应 200）— 缺口。"""
        prop = client.post(
            "/v1/properties",
            json={
                "community": "X",
                "layout": "1室",
                "area": 50.0,
                "total_price": 1_000_000,
                "tags": [],
                "images": [],
                "viewing_time": "随时",
            },
            headers=users["A_h"],
        ).json()["data"]

        resp = client.get(f"/v1/properties/{prop['id']}", headers=users["B_h"])
        # 缺口：B 能看 A 的房源
        assert resp.status_code == 200, (
            f"expected 200 (gap), got {resp.status_code}: {resp.text}"
        )


# ============================================================
#  字段级脱敏测试（Sprint1-P0 #7）
# ============================================================

class TestPropertyDetailMasking:
    """[Sprint1-P0] 房源详情字段级脱敏。"""

    def test_property_detail_has_seller_brief(self, client, users):
        """房源详情含 seller_brief 字段。"""
        prop = client.post(
            "/v1/properties",
            json={
                "community": "X", "layout": "1室", "area": 50.0,
                "total_price": 1_000_000, "tags": [], "images": [],
                "viewing_time": "随时",
            },
            headers=users["A_h"],
        ).json()["data"]
        resp = client.get(f"/v1/properties/{prop['id']}", headers=users["B_h"])
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "seller_brief" in data
        brief = data["seller_brief"]
        assert brief["id"] == users["A_id"]

    def test_seller_brief_does_not_leak_real_name(
        self, client, users
    ):
        """seller_brief 不含真实姓名（User.name）。"""
        prop = client.post(
            "/v1/properties",
            json={
                "community": "X", "layout": "1室", "area": 50.0,
                "total_price": 1_000_000, "tags": [], "images": [],
                "viewing_time": "随时",
            },
            headers=users["A_h"],
        ).json()["data"]
        resp = client.get(f"/v1/properties/{prop['id']}", headers=users["B_h"])
        data = resp.json()["data"]
        brief = data["seller_brief"]
        # 关键断言：'name' 字段不存在
        assert "name" not in brief, (
            f"seller_brief 暴露了真实姓名 'name' 字段: {brief}"
        )
        # display_name 应该是 "Alice先生" 形式（脱敏显示名）
        assert brief["display_name"] == "Alice先生"

    def test_seller_brief_does_not_leak_phone(
        self, client, users
    ):
        """seller_brief schema 不包含手机/邮箱字段（静态校验）。"""
        from app.domains.users.router import UserPublicBrief

        fields = UserPublicBrief.model_fields.keys()
        for forbidden in ("phone", "phone_encrypted", "phone_hash",
                          "email", "id_card"):
            assert forbidden not in fields, (
                f"UserPublicBrief 暴露了 {forbidden}"
            )

        prop = client.post(
            "/v1/properties",
            json={
                "community": "X", "layout": "1室", "area": 50.0,
                "total_price": 1_000_000, "tags": [], "images": [],
                "viewing_time": "随时",
            },
            headers=users["A_h"],
        ).json()["data"]
        resp = client.get(f"/v1/properties/{prop['id']}", headers=users["B_h"])
        data = resp.json()["data"]
        brief = data["seller_brief"]
        # 关键断言：手机相关字段不存在
        for forbidden in ("phone", "phone_encrypted", "phone_hash",
                          "email", "id_card"):
            assert forbidden not in brief, (
                f"seller_brief 泄漏了 {forbidden}: {brief}"
            )


class TestDemandDetailMasking:
    """[Sprint1-P0] 需求详情字段级脱敏。"""

    def test_demand_detail_has_buyer_brief(self, client, users):
        """需求详情含 buyer_brief 字段。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X", "price_min": 1_000_000, "price_max": 2_000_000,
                "layouts": ["1室"], "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]
        resp = client.get(f"/v1/demands/{demand['id']}", headers=users["B_h"])
        data = resp.json()["data"]
        assert "buyer_brief" in data
        assert data["buyer_brief"]["id"] == users["A_id"]

    def test_buyer_brief_does_not_leak_real_name(self, client, users):
        """buyer_brief 不含真实姓名。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X", "price_min": 1_000_000, "price_max": 2_000_000,
                "layouts": ["1室"], "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]
        resp = client.get(f"/v1/demands/{demand['id']}", headers=users["B_h"])
        brief = resp.json()["data"]["buyer_brief"]
        assert "name" not in brief
        assert "phone" not in brief


class TestReviewAnonymousMasking:
    """[Sprint1-P0] 评价匿名化字段处理。"""

    def _setup_completed_coop(self, client, users) -> int:
        """建一个已握手 + 双方都评完的合作（cooperation_id）。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X", "price_min": 1_000_000, "price_max": 2_000_000,
                "layouts": ["1室"], "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]
        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])
        client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={"content": "B 提交方案超 20 字符的方案内容描述详细。"},
            headers=users["B_h"],
        )
        coop = client.post(
            f"/v1/invitations/{inv['id']}/confirm",
            headers=users["A_h"],
        ).json()["data"]
        return coop["id"]

    def test_anonymous_review_hides_reviewer_id_for_others(
        self, client, users
    ):
        """匿名评价：别人看时 reviewer_id 抹成 None。"""
        # A 创建需求 + 邀请 + 双方都评 + B 匿名评
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X", "price_min": 1_000_000, "price_max": 2_000_000,
                "layouts": ["1室"], "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]
        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])
        client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={"content": "B 提交方案超 20 字符的方案内容描述详细。"},
            headers=users["B_h"],
        )
        coop = client.post(
            f"/v1/invitations/{inv['id']}/confirm",
            headers=users["A_h"],
        ).json()["data"]

        # A 先评（不匿名）
        client.post(
            f"/v1/cooperations/{coop['id']}/review",
            json={"rating": 5, "comment": "A 给 B 的好评", "is_anonymous": False},
            headers=users["A_h"],
        )
        # B 后评（匿名）
        client.post(
            f"/v1/cooperations/{coop['id']}/review",
            json={"rating": 4, "comment": "B 匿名评 A", "is_anonymous": True},
            headers=users["B_h"],
        )

        # A 看自己合作的评价列表
        resp = client.get(
            f"/v1/cooperations/{coop['id']}/review", headers=users["A_h"]
        )
        assert resp.status_code == 200
        reviews = resp.json()["data"]
        # 找到 B 那条匿名评价
        b_review = next(
            (r for r in reviews if r["comment"] == "B 匿名评 A"),
            None,
        )
        assert b_review is not None
        # 关键断言：匿名 + 别人看 → reviewer_id 抹 None
        assert b_review["reviewer_id"] is None
        assert b_review["reviewer_brief"] is None
        # reviewee 仍是 A 自己 → 应该展示
        assert b_review["reviewee_id"] == users["A_id"]
        assert b_review["reviewee_brief"] is not None
        # A 自己的实名评价
        a_review = next(
            (r for r in reviews if r["comment"] == "A 给 B 的好评"),
            None,
        )
        assert a_review["reviewer_id"] == users["A_id"]  # 不匿名 → 展示

    def test_anonymous_reviewer_self_view_sees_own_id(
        self, client, users
    ):
        """匿名评价：评价人自己看自己写的 → 仍能看到 reviewer_id（方便回看）。"""
        demand = client.post(
            "/v1/demands",
            json={
                "district": "X", "price_min": 1_000_000, "price_max": 2_000_000,
                "layouts": ["1室"], "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=users["A_h"],
        ).json()["data"]
        inv = client.post(
            "/v1/invitations",
            json={"demand_id": demand["id"], "seller_id": users["B_id"]},
            headers=users["A_h"],
        ).json()["data"]
        client.post(f"/v1/invitations/{inv['id']}/accept", headers=users["B_h"])
        client.post(
            f"/v1/invitations/{inv['id']}/proposal",
            json={"content": "B 提交方案超 20 字符的方案内容描述详细。"},
            headers=users["B_h"],
        )
        coop = client.post(
            f"/v1/invitations/{inv['id']}/confirm",
            headers=users["A_h"],
        ).json()["data"]

        # A 评 B（匿名）
        client.post(
            f"/v1/cooperations/{coop['id']}/review",
            json={"rating": 5, "comment": "我匿名评", "is_anonymous": True},
            headers=users["A_h"],
        )

        # A 看自己合作的评价（自己就是评价人）
        resp = client.get(
            f"/v1/cooperations/{coop['id']}/review", headers=users["A_h"]
        )
        reviews = resp.json()["data"]
        my_review = next(r for r in reviews if r["comment"] == "我匿名评")
        # 自己看自己写的 → 实名展示
        assert my_review["reviewer_id"] == users["A_id"]


class TestUserPublicBriefMasking:
    """[Sprint1-P0] UserPublicBrief 去掉真实姓名 + 联系方式。"""

    def test_user_public_brief_no_real_name(self):
        """UserPublicBrief schema 不再含 'name' 字段（真实姓名）。"""
        from app.domains.users.router import UserPublicBrief

        fields = UserPublicBrief.model_fields.keys()
        assert "name" not in fields, (
            f"UserPublicBrief 仍暴露 'name' 字段: {list(fields)}"
        )
        # 确认不含手机/邮箱
        for forbidden in ("phone", "phone_encrypted", "phone_hash", "email"):
            assert forbidden not in fields

    def test_user_public_brief_has_safe_fields(self):
        """UserPublicBrief 含展示名 + 信用分 + 头像 + 是否认证。"""
        from app.domains.users.router import UserPublicBrief

        fields = UserPublicBrief.model_fields.keys()
        for safe in ("id", "display_name", "avatar_url", "credit_score", "is_verified"):
            assert safe in fields, f"UserPublicBrief 缺 {safe} 字段"
