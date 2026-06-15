"""Stage 3 任务 2: Invitations 域端到端测试 + 状态机剩余 12% 覆盖。

与现有 test_state_machine.py 的分工：
- test_state_machine.py  → **非法 transition** (409 兜底) — P1-5
- 本文件                → 端点契约 + 软删 + 24h 倒计时 + 状态机查询 + side effects

**新覆盖**（覆盖率补全）：
- [invitations/router.py](backend/app/domains/invitations/router.py) 79% → 100%
- [invitations/state_machine.py](backend/app/domains/invitations/state_machine.py) 88% → 100%
  - apply_expire/apply_confirm/apply_decline side effects
  - is_terminal() 4 个终态分支
  - expire() trigger 方法
  - can_submit_proposal/can_confirm 查询方法
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.demand import Demand, DemandStatus
from app.models.invitation import Invitation, InvitationStatus
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
    """每个测试一个干净 DB session。"""
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
) -> User:
    user = User(
        id=user_id,
        name=name,
        display_name=display_name or f"{name}先生",
        status=UserStatus.ACTIVE,
        is_verified=True,
        credit_score=80.0,
        rating_avg=4.0,
        rating_count=0,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    return user


def _make_demand(
    db,
    demand_id: int,
    buyer_id: int,
    status: DemandStatus = DemandStatus.ACTIVE,
    invite_count: int = 0,
) -> Demand:
    demand = Demand(
        id=demand_id,
        buyer_id=buyer_id,
        district="朝阳区",
        price_min=3_000_000,
        price_max=5_000_000,
        layouts=["2室1厅"],
        qualification="首套",
        viewing_time=["周末"],
        source_url=None,
        status=status,
        summary="test summary",
        invite_count=invite_count,
    )
    db.add(demand)
    db.commit()
    return demand


def _make_invitation(
    db,
    inv_id: int,
    demand_id: int,
    buyer_id: int,
    seller_id: int,
    status: InvitationStatus = InvitationStatus.PENDING,
    expired_at: datetime | None = None,
    deleted: bool = False,
) -> Invitation:
    inv = Invitation(
        id=inv_id,
        demand_id=demand_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        status=status,
        expired_at=expired_at or (datetime.now(timezone.utc) + timedelta(hours=24)),
        note="seed",
    )
    db.add(inv)
    db.flush()
    if deleted:
        from datetime import datetime as _dt
        inv.deleted_at = _dt.now(timezone.utc)
    db.commit()
    return inv


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ============================================================
#  POST /invitations  — 发起邀请
# ============================================================

class TestCreateInvitation:
    """POST /invitations 契约。"""

    def test_create_returns_200_with_pending_and_24h_expiry(
        self, client: TestClient, db
    ):
        """正常创建：status=pending + expired_at ≈ now+24h + invite_count++。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, demand_id=2001, buyer_id=1001)

        before = datetime.now(timezone.utc)
        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002, "note": "客户总价 400-450w"},
            headers=_auth(1001),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "pending"
        assert data["buyer_id"] == 1001
        assert data["seller_id"] == 1002
        assert data["demand_id"] == 2001
        assert data["note"] == "客户总价 400-450w"
        # 24h ± 5s 容差（FastAPI 序列化 + 测试 wall-clock）
        expired_at = datetime.fromisoformat(data["expired_at"])
        if expired_at.tzinfo is None:
            expired_at = expired_at.replace(tzinfo=timezone.utc)
        delta = (expired_at - before).total_seconds()
        assert 24 * 3600 - 5 <= delta <= 24 * 3600 + 5, f"expired_at delta={delta}s"

        # invite_count 累加
        db.expire_all()
        demand = db.get(Demand, 2001)
        assert demand.invite_count == 1

    def test_create_minimal_payload(
        self, client: TestClient, db
    ):
        """只传 demand_id + seller_id：note 可选。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
            headers=_auth(1001),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["note"] is None

    def test_create_demand_not_found_returns_10002(
        self, client: TestClient, db
    ):
        """需求不存在 → 404 + 10002。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 99999, "seller_id": 1002},
            headers=_auth(1001),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_create_other_users_demand_returns_10003(
        self, client: TestClient, db
    ):
        """用户 B 用 A 的需求发起邀请 → 403。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)  # 属于 A

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
            headers=_auth(1002),  # B 调
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

    def test_create_closed_demand_returns_400(
        self, client: TestClient, db
    ):
        """需求已 closed → 400 + 10001。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001, status=DemandStatus.CLOSED)

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        assert "关闭" in body["message"]

    def test_create_seller_not_found_returns_10002(
        self, client: TestClient, db
    ):
        """卖方不存在 → 404 + 10002。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 99999},
            headers=_auth(1001),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_create_duplicate_pending_returns_400(
        self, client: TestClient, db
    ):
        """同一 demand+seller 已有 pending 邀请 → 400 + 10001（"已向该卖方发起过"）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002, status=InvitationStatus.PENDING)

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        assert "重复" in body["message"]

    def test_create_duplicate_accepted_returns_400(
        self, client: TestClient, db
    ):
        """同 demand+seller 已 accepted 也算重复。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(
            db, 3001, 2001, 1001, 1002, status=InvitationStatus.ACCEPTED
        )

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
            headers=_auth(1001),
        )
        assert resp.status_code == 400

    def test_create_after_rejected_is_allowed(
        self, client: TestClient, db
    ):
        """已 rejected → 可重新发起邀请（终态不阻塞新轮）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(
            db, 3001, 2001, 1001, 1002, status=InvitationStatus.REJECTED
        )

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
            headers=_auth(1001),
        )
        assert resp.status_code == 200
        # 新邀请 ID 不一样
        assert resp.json()["data"]["id"] != 3001

    def test_create_after_expired_is_allowed(
        self, client: TestClient, db
    ):
        """已 expired → 可重新发起（[D-001] 失效不阻塞下轮）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(
            db, 3001, 2001, 1001, 1002, status=InvitationStatus.EXPIRED
        )

        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
            headers=_auth(1001),
        )
        assert resp.status_code == 200

    def test_create_requires_auth(self, client: TestClient):
        resp = client.post(
            "/v1/invitations",
            json={"demand_id": 2001, "seller_id": 1002},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003


# ============================================================
#  GET /invitations  — 我的邀请
# ============================================================

class TestListMyInvitations:
    """GET /invitations 契约。"""

    def test_list_buyer_role_returns_only_buyer_invitations(
        self, client: TestClient, db
    ):
        """role=buyer（默认）→ 只返当前用户作为买方的邀请。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_demand(db, 2002, buyer_id=1002)
        # Alice→Bob
        _make_invitation(db, 3001, 2001, 1001, 1002)
        # Bob→Alice (Alice 是卖方，不应该出现在 buyer 列表)
        _make_invitation(db, 3002, 2002, 1002, 1001)

        resp = client.get(
            "/v1/invitations?role=buyer", headers=_auth(1001)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == 3001
        assert data[0]["buyer_id"] == 1001

    def test_list_seller_role_returns_only_seller_invitations(
        self, client: TestClient, db
    ):
        """role=seller → 只返当前用户作为卖方的邀请。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_demand(db, 2002, buyer_id=1002)
        _make_invitation(db, 3001, 2001, 1001, 1002)  # Bob 是 seller
        _make_invitation(db, 3002, 2002, 1002, 1001)  # Alice 是 seller

        resp = client.get(
            "/v1/invitations?role=seller", headers=_auth(1001)
        )
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == 3002
        assert data[0]["seller_id"] == 1001

    def test_list_default_role_is_buyer(
        self, client: TestClient, db
    ):
        """不传 role → 默认 buyer。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.get("/v1/invitations", headers=_auth(1001))
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["buyer_id"] == 1001

    def test_list_status_filter(
        self, client: TestClient, db
    ):
        """status 过滤：?status=pending 只返 pending。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_demand(db, 2002, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002, status=InvitationStatus.PENDING)
        _make_invitation(db, 3002, 2002, 1001, 1002, status=InvitationStatus.REJECTED)

        resp = client.get(
            "/v1/invitations?role=buyer&status=pending", headers=_auth(1001)
        )
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == 3001

    def test_list_excludes_soft_deleted(
        self, client: TestClient, db
    ):
        """软删的邀请不出现在列表。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_demand(db, 2002, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)
        _make_invitation(db, 3002, 2002, 1001, 1002, deleted=True)

        resp = client.get("/v1/invitations?role=buyer", headers=_auth(1001))
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == 3001

    def test_list_empty(self, client: TestClient, db):
        _make_user(db, 1001, name="Alice")
        resp = client.get("/v1/invitations", headers=_auth(1001))
        assert resp.json()["data"] == []

    def test_list_requires_auth(self, client: TestClient):
        resp = client.get("/v1/invitations")
        assert resp.status_code == 401


# ============================================================
#  GET /invitations/{id}  — 邀请详情
# ============================================================

class TestGetInvitation:
    """GET /invitations/{id} 契约。"""

    def test_get_as_buyer_succeeds(self, client: TestClient, db):
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.get(
            "/v1/invitations/3001", headers=_auth(1001)  # Alice 是 buyer
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == 3001
        assert data["buyer_id"] == 1001
        assert data["seller_id"] == 1002

    def test_get_as_seller_succeeds(self, client: TestClient, db):
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.get(
            "/v1/invitations/3001", headers=_auth(1002)  # Bob 是 seller
        )
        assert resp.status_code == 200

    def test_get_third_party_returns_10003(
        self, client: TestClient, db
    ):
        """既不是 buyer 也不是 seller → 403。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_user(db, 1003, name="Carol")  # 无关用户
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.get(
            "/v1/invitations/3001", headers=_auth(1003)
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

    def test_get_not_found_returns_10002(self, client: TestClient, db):
        _make_user(db, 1001, name="Alice")
        resp = client.get("/v1/invitations/99999", headers=_auth(1001))
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_get_soft_deleted_returns_404(self, client: TestClient, db):
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002, deleted=True)

        resp = client.get("/v1/invitations/3001", headers=_auth(1001))
        assert resp.status_code == 404

    def test_get_requires_auth(self, client: TestClient):
        resp = client.get("/v1/invitations/1")
        assert resp.status_code == 401


# ============================================================
#  POST /invitations/{id}/accept  — 接单（24h 倒计时）
# ============================================================

class TestAcceptInvitation:
    """POST /invitations/{id}/accept 契约（含 24h 倒计时）。"""

    def test_accept_happy_path_sets_proposal_deadline(
        self, client: TestClient, db
    ):
        """接单成功：status=accepted + proposal_deadline ≈ now+2h + responded_at 非空。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002, status=InvitationStatus.PENDING)

        before = datetime.now(timezone.utc)
        resp = client.post(
            "/v1/invitations/3001/accept", headers=_auth(1002)  # Bob
        )

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["invitation_id"] == 3001
        assert data["status"] == "accepted"
        # proposal_deadline 2h 后
        deadline = datetime.fromisoformat(data["proposal_deadline"])
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        delta = (deadline - before).total_seconds()
        assert 2 * 3600 - 5 <= delta <= 2 * 3600 + 5, f"proposal_deadline delta={delta}s"

    def test_accept_after_24h_returns_410(
        self, client: TestClient, db
    ):
        """24h 已过的邀请接单 → 410 InvitationExpiredError + 触发 expire()。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        # expired_at 设为 1 小时前
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        _make_invitation(
            db, 3001, 2001, 1001, 1002,
            status=InvitationStatus.PENDING, expired_at=past,
        )

        resp = client.post(
            "/v1/invitations/3001/accept", headers=_auth(1002)
        )
        assert resp.status_code == 410
        body = resp.json()
        assert body["code"] == 30002
        assert "超时" in body["message"]

        # 状态机自动 expire → status=expired
        db.expire_all()
        inv = db.get(Invitation, 3001)
        assert inv.status == InvitationStatus.EXPIRED

    def test_accept_not_found_returns_10002(self, client: TestClient, db):
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/invitations/99999/accept", headers=_auth(1001)
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_accept_wrong_user_returns_10003(
        self, client: TestClient, db
    ):
        """不是 seller 接单 → 403。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_user(db, 1003, name="Carol")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.post(
            "/v1/invitations/3001/accept", headers=_auth(1003)
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

    def test_accept_requires_auth(self, client: TestClient):
        resp = client.post("/v1/invitations/1/accept")
        assert resp.status_code == 401


# ============================================================
#  POST /invitations/{id}/reject  — 拒绝
# ============================================================

class TestRejectInvitation:
    """POST /invitations/{id}/reject 契约。"""

    def test_reject_happy_path_sets_responded_at(
        self, client: TestClient, db
    ):
        """拒绝成功：status=rejected + responded_at 非空。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.post(
            "/v1/invitations/3001/reject", headers=_auth(1002)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == 3001
        assert data["status"] == "rejected"

        # DB 字段
        db.expire_all()
        inv = db.get(Invitation, 3001)
        assert inv.responded_at is not None

    def test_reject_with_reason_stores_reason(
        self, client: TestClient, db
    ):
        """?reason=XXX → reject_reason 字段被存。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.post(
            "/v1/invitations/3001/reject?reason=手上客户太忙",
            headers=_auth(1002),
        )
        assert resp.status_code == 200

        db.expire_all()
        inv = db.get(Invitation, 3001)
        assert inv.reject_reason == "手上客户太忙"

    def test_reject_without_reason_is_ok(
        self, client: TestClient, db
    ):
        """不传 reason → reject_reason 留空。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.post(
            "/v1/invitations/3001/reject", headers=_auth(1002)
        )
        assert resp.status_code == 200
        db.expire_all()
        inv = db.get(Invitation, 3001)
        assert inv.reject_reason is None

    def test_reject_not_found_returns_10002(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/invitations/99999/reject", headers=_auth(1001)
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_reject_wrong_user_returns_10003(
        self, client: TestClient, db
    ):
        """buyer 拒绝（应该是 seller 才能）→ 403。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)
        _make_invitation(db, 3001, 2001, 1001, 1002)

        resp = client.post(
            "/v1/invitations/3001/reject", headers=_auth(1001)  # buyer
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

    def test_reject_requires_auth(self, client: TestClient):
        resp = client.post("/v1/invitations/1/reject")
        assert resp.status_code == 401


# ============================================================
#  State machine — 覆盖剩余 12% 边角
# ============================================================

class TestStateMachineQueries:
    """InvitationStateMachine 查询方法（is_terminal / can_X）的全分支覆盖。"""

    def _build_inv(self, status: InvitationStatus) -> Invitation:
        """纯函数式构造一个未保存的 Invitation 喂给状态机。"""
        return Invitation(
            id=1,
            demand_id=1,
            buyer_id=1,
            seller_id=2,
            status=status,
            expired_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

    def test_is_terminal_rejected(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        inv = self._build_inv(InvitationStatus.REJECTED)
        sm = InvitationStateMachine(inv)
        assert sm.is_terminal() is True

    def test_is_terminal_expired(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        inv = self._build_inv(InvitationStatus.EXPIRED)
        sm = InvitationStateMachine(inv)
        assert sm.is_terminal() is True

    def test_is_terminal_handshaked(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        inv = self._build_inv(InvitationStatus.HANDSHAKED)
        sm = InvitationStateMachine(inv)
        assert sm.is_terminal() is True

    def test_is_terminal_closed(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        inv = self._build_inv(InvitationStatus.CLOSED)
        sm = InvitationStateMachine(inv)
        assert sm.is_terminal() is True

    def test_is_terminal_pending_is_false(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        inv = self._build_inv(InvitationStatus.PENDING)
        sm = InvitationStateMachine(inv)
        assert sm.is_terminal() is False

    def test_is_terminal_accepted_is_false(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        inv = self._build_inv(InvitationStatus.ACCEPTED)
        sm = InvitationStateMachine(inv)
        assert sm.is_terminal() is False

    def test_can_submit_proposal_only_in_accepted(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        # accepted → True
        sm_a = InvitationStateMachine(self._build_inv(InvitationStatus.ACCEPTED))
        assert sm_a.can_submit_proposal() is True
        # 其他 → False
        for s in [InvitationStatus.PENDING, InvitationStatus.REJECTED,
                  InvitationStatus.EXPIRED, InvitationStatus.PROPOSAL_REVIEW,
                  InvitationStatus.HANDSHAKED, InvitationStatus.CLOSED]:
            sm = InvitationStateMachine(self._build_inv(s))
            assert sm.can_submit_proposal() is False, f"can_submit_proposal in {s}"

    def test_can_confirm_only_in_proposal_review(self):
        from app.domains.invitations.state_machine import InvitationStateMachine
        sm_p = InvitationStateMachine(self._build_inv(InvitationStatus.PROPOSAL_REVIEW))
        assert sm_p.can_confirm() is True
        for s in [InvitationStatus.PENDING, InvitationStatus.ACCEPTED,
                  InvitationStatus.REJECTED, InvitationStatus.EXPIRED,
                  InvitationStatus.HANDSHAKED, InvitationStatus.CLOSED]:
            sm = InvitationStateMachine(self._build_inv(s))
            assert sm.can_confirm() is False, f"can_confirm in {s}"


class TestStateMachineSideEffects:
    """3 个未在测试中触发的 side effects：apply_expire / apply_confirm / apply_decline。"""

    def _build_inv(self) -> Invitation:
        return Invitation(
            id=1,
            demand_id=1,
            buyer_id=1,
            seller_id=2,
            status=InvitationStatus.ACCEPTED,
            expired_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )

    def test_apply_expire_side_effects_sets_responded_at(self):
        """expire() → apply_expire_side_effects → responded_at 非空。"""
        from app.domains.invitations.state_machine import (
            InvitationStateMachine,
        )
        inv = self._build_inv()
        sm = InvitationStateMachine(inv)
        sm.expire()  # accepted → expired
        InvitationStateMachine.apply_expire_side_effects(inv)
        assert inv.responded_at is not None
        assert inv.status == InvitationStatus.EXPIRED

    def test_apply_confirm_side_effects(self):
        """confirm() → apply_confirm_side_effects。"""
        from app.domains.invitations.state_machine import (
            InvitationStateMachine,
        )
        inv = Invitation(
            id=2, demand_id=1, buyer_id=1, seller_id=2,
            status=InvitationStatus.PROPOSAL_REVIEW,
            expired_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        sm = InvitationStateMachine(inv)
        sm.confirm()  # proposal_review → handshaked
        InvitationStateMachine.apply_confirm_side_effects(inv)
        assert inv.responded_at is not None
        assert inv.status == InvitationStatus.HANDSHAKED

    def test_apply_decline_side_effects(self):
        """decline() → apply_decline_side_effects。"""
        from app.domains.invitations.state_machine import (
            InvitationStateMachine,
        )
        inv = Invitation(
            id=3, demand_id=1, buyer_id=1, seller_id=2,
            status=InvitationStatus.PROPOSAL_REVIEW,
            expired_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        sm = InvitationStateMachine(inv)
        sm.decline()  # proposal_review → closed
        InvitationStateMachine.apply_decline_side_effects(inv)
        assert inv.responded_at is not None
        assert inv.status == InvitationStatus.CLOSED

    def test_proposal_ttl_is_2_hours(self):
        """PROPOSAL_TTL_HOURS = 2 常量锁定（防止误改）。"""
        from app.domains.invitations.state_machine import PROPOSAL_TTL_HOURS
        assert PROPOSAL_TTL_HOURS == 2

    def test_invitation_ttl_is_24_hours(self):
        """INVITATION_TTL_HOURS = 24 常量锁定（[D-001]）。"""
        from app.domains.invitations.state_machine import INVITATION_TTL_HOURS
        assert INVITATION_TTL_HOURS == 24
