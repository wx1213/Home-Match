"""P1-5 状态机非法 transition 兜底测试。

验证：当客户端试图触发状态机不允许的 transition 时，API 返回 409 + 10005
（InvalidStateTransitionError），而不是 500 或 400。

测试场景（5 类）：
1. 重复 accept（pending → accepted → accept）→ 409
2. accept 后 reject（pending → accepted → reject）→ 409
3. accept 后再 accept → 409
4. handshaked 后再 confirm → 409
5. handshaked 后再 decline → 409
6. 不在 pending 时 reject → 409
7. global handler 兜底：直接调 sm.accept()（绕过 can_X 检查）触发 MachineError → 409
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User, UserStatus

# ============================================================
#  Fixtures
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def create_tables():
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
def seeded():
    """建 A=buyer, B=seller + A 的需求 + A→B 的邀请。"""
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(text(f"DELETE FROM {table.name}"))
        # A = buyer
        db.add(User(
            id=101, name="Alice", display_name="Alice先生",
            status=UserStatus.ACTIVE, is_verified=True,
            credit_score=80.0, rating_avg=4.0, rating_count=0,
            last_login_at=datetime.now(timezone.utc),
        ))
        # B = seller
        db.add(User(
            id=102, name="Bob", display_name="Bob先生",
            status=UserStatus.ACTIVE, is_verified=True,
            credit_score=85.0, rating_avg=4.5, rating_count=3,
            last_login_at=datetime.now(timezone.utc),
        ))
        db.commit()

        from app.models.demand import Demand, DemandStatus
        db.add(Demand(
            id=301, buyer_id=101,
            district="朝阳区", price_min=3_000_000, price_max=5_000_000,
            layouts=["2室1厅"], qualification="首套",
            viewing_time=["周末"], source_url=None,
            status=DemandStatus.ACTIVE, summary="test", invite_count=0,
        ))
        db.commit()

        # A→B 的邀请（pending 状态）
        db.add(Invitation(
            id=401, demand_id=301, buyer_id=101, seller_id=102,
            status=InvitationStatus.PENDING,
            expired_at=datetime.now(timezone.utc) + timedelta(hours=24),
            note="test",
        ))
        db.commit()
    return {
        "A_id": 101, "B_id": 102,
        "demand_id": 301, "inv_id": 401,
    }


def _auth(user_id: int) -> dict[str, str]:
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def assert_invalid_state(resp, label: str) -> None:
    """断言 409 InvalidStateTransitionError。"""
    assert resp.status_code == 409, (
        f"[{label}] expected 409, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("code") == 30005, (
        f"[{label}] expected code 30005, got {body.get('code')}: {body}"
    )


# ============================================================
#  Tests
# ============================================================

class TestIllegalStateTransitions:
    """P1-5: 状态机非法 transition 应返 409，不 5xx。"""

    def test_double_accept_returns_409(
        self, client: TestClient, seeded
    ):
        """第一次 accept → 200，第二次 accept → 409。"""
        # 第一次 accept
        r1 = client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        assert r1.status_code == 200, f"first accept failed: {r1.text}"

        # 第二次 accept
        r2 = client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        assert_invalid_state(r2, "double accept")

    def test_accept_then_reject_returns_409(
        self, client: TestClient, seeded
    ):
        """accept 后再 reject → 409（reject 只在 pending 有效）。"""
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        r = client.post(
            f"/v1/invitations/{seeded['inv_id']}/reject",
            headers=_auth(seeded["B_id"]),
        )
        assert_invalid_state(r, "accept then reject")

    def test_double_reject_returns_409(
        self, client: TestClient, seeded
    ):
        """第一次 reject → 200，第二次 reject → 409。"""
        r1 = client.post(
            f"/v1/invitations/{seeded['inv_id']}/reject",
            headers=_auth(seeded["B_id"]),
        )
        assert r1.status_code == 200, f"first reject failed: {r1.text}"

        r2 = client.post(
            f"/v1/invitations/{seeded['inv_id']}/reject",
            headers=_auth(seeded["B_id"]),
        )
        assert_invalid_state(r2, "double reject")

    def test_reject_after_proposal_review_returns_409(
        self, client: TestClient, seeded
    ):
        """B 接单 + 提交方案后，A 已经走 confirm → handshaked，此时再 reject → 409。"""
        # B accept
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        # B 提交方案
        r_p = client.post(
            f"/v1/invitations/{seeded['inv_id']}/proposal",
            json={"content": "B 提交的合作方案，超 20 字符描述非常详细的内容。", "fit_points": "匹配"},
            headers=_auth(seeded["B_id"]),
        )
        assert r_p.status_code == 200, f"proposal submit failed: {r_p.text}"

        # A confirm
        r_c = client.post(
            f"/v1/invitations/{seeded['inv_id']}/confirm",
            headers=_auth(seeded["A_id"]),
        )
        assert r_c.status_code == 200, f"confirm failed: {r_c.text}"

        # 现在 invitation 状态是 handshaked，再 reject → 409
        r = client.post(
            f"/v1/invitations/{seeded['inv_id']}/reject",
            headers=_auth(seeded["B_id"]),
        )
        assert_invalid_state(r, "reject after handshaked")

    def test_submit_proposal_after_handshaked_returns_409(
        self, client: TestClient, seeded
    ):
        """handshaked 状态再 submit_proposal → 409（应在 accepted 状态做）。"""
        # 走到 handshaked
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/proposal",
            json={"content": "B 提交的合作方案，超 20 字符描述非常详细的内容。", "fit_points": "匹配"},
            headers=_auth(seeded["B_id"]),
        )
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/confirm",
            headers=_auth(seeded["A_id"]),
        )

        # 再 submit_proposal → 409
        r = client.post(
            f"/v1/invitations/{seeded['inv_id']}/proposal",
            json={"content": "B 再提交一次方案，超 20 字符描述非常详细。"},
            headers=_auth(seeded["B_id"]),
        )
        assert_invalid_state(r, "submit_proposal after handshaked")

    def test_confirm_after_handshaked_returns_409(
        self, client: TestClient, seeded
    ):
        """已 handshaked 再 confirm → 409。"""
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/proposal",
            json={"content": "B 提交方案超 20 字符描述非常详细的内容。"},
            headers=_auth(seeded["B_id"]),
        )
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/confirm",
            headers=_auth(seeded["A_id"]),
        )

        r = client.post(
            f"/v1/invitations/{seeded['inv_id']}/confirm",
            headers=_auth(seeded["A_id"]),
        )
        assert_invalid_state(r, "confirm after handshaked")

    def test_decline_after_handshaked_returns_409(
        self, client: TestClient, seeded
    ):
        """已 handshaked 再 decline → 409（之前缺失 can_decline 检查 → 500）。"""
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/proposal",
            json={"content": "B 提交方案超 20 字符描述非常详细的内容。"},
            headers=_auth(seeded["B_id"]),
        )
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/confirm",
            headers=_auth(seeded["A_id"]),
        )

        r = client.post(
            f"/v1/invitations/{seeded['inv_id']}/decline",
            headers=_auth(seeded["A_id"]),
        )
        assert_invalid_state(r, "decline after handshaked")

    def test_double_decline_returns_409(
        self, client: TestClient, seeded
    ):
        """buyer decline 一次后再次 decline → 409。"""
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        client.post(
            f"/v1/invitations/{seeded['inv_id']}/proposal",
            json={"content": "B 提交方案超 20 字符描述非常详细的内容。"},
            headers=_auth(seeded["B_id"]),
        )
        r1 = client.post(
            f"/v1/invitations/{seeded['inv_id']}/decline",
            headers=_auth(seeded["A_id"]),
        )
        assert r1.status_code == 200, f"first decline failed: {r1.text}"

        r2 = client.post(
            f"/v1/invitations/{seeded['inv_id']}/decline",
            headers=_auth(seeded["A_id"]),
        )
        assert_invalid_state(r2, "double decline")


class TestGlobalMachineErrorHandler:
    """P1-5：transitions.MachineError 兜底 handler。"""

    def test_machine_error_caught_at_global_handler(
        self, client: TestClient, seeded, monkeypatch
    ):
        """绕过 can_X 检查，直接让 sm.accept() 抛 MachineError → 全局 handler 接住 → 409。"""
        from transitions import MachineError

        from app.domains.invitations import state_machine as sm_module

        # Monkeypatch sm.accept 让它直接抛 MachineError
        original_init = sm_module.InvitationStateMachine.__init__

        def patched_init(self, invitation):
            original_init(self, invitation)

        monkeypatch.setattr(
            sm_module.InvitationStateMachine,
            "accept",
            lambda self: (_ for _ in ()).throw(
                MachineError("Can't trigger event accept from state accepted!")
            ),
        )

        # 先手动让 invitation 进入 accepted 状态（模拟任何路径）
        with SessionLocal() as db:
            from app.models.invitation import InvitationStatus
            inv = db.get(Invitation, seeded["inv_id"])
            inv.status = InvitationStatus.ACCEPTED
            db.commit()

        # 再调 accept → MachineError → 全局 handler 返 409
        r = client.post(
            f"/v1/invitations/{seeded['inv_id']}/accept",
            headers=_auth(seeded["B_id"]),
        )
        assert r.status_code == 409, f"expected 409 from global handler, got {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("code") == 30005
