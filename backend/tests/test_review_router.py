"""Stage 3 任务 4: Reviews 域端到端测试。

[reviews/router.py](backend/app/domains/reviews/router.py) 94% → 100% 覆盖。

已有覆盖（不再重复）：
- test_authorization.py:
  - C_cannot_review_AB_cooperation（[P1-3] 越权）
  - TestReviewAnonymousMasking（[Sprint1-P0] 匿名脱敏 2 测试）
- test_credit_score_db.py: 信用分重算的 DB 行为

本文件聚焦：
- POST happy path + 各种 status 允许/禁止
- 必填校验 + 边界
- 重复评价 400
- 双方都评完 → status=COMPLETED + 信用分自动重算
- _build_review_response 边界（is_self_view × is_anonymous 全 4 组合）
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.cooperation import Cooperation, CooperationStatus
from app.models.review import Review
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
    _db,
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
        rating_avg=0.0,
        rating_count=0,
        last_login_at=datetime.now(timezone.utc),
    )
    with SessionLocal() as session:
        session.add(user)
        session.commit()
    return user


def _make_cooperation(
    _db,
    coop_id: int,
    buyer_id: int,
    seller_id: int,
    status: CooperationStatus = CooperationStatus.HANDSHAKED,
    buyer_reviewed: bool = False,
    seller_reviewed: bool = False,
) -> Cooperation:
    coop = Cooperation(
        id=coop_id,
        invitation_id=coop_id + 10000,  # fake unique
        buyer_id=buyer_id,
        seller_id=seller_id,
        status=status,
        memo_content="test memo",
        signed_at=datetime.now(timezone.utc),
        buyer_reviewed=buyer_reviewed,
        seller_reviewed=seller_reviewed,
    )
    with SessionLocal() as session:
        session.add(coop)
        session.commit()
    return coop


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ============================================================
#  POST /cooperations/{coop_id}/review  — 提交评价
# ============================================================

class TestSubmitReview:
    """POST /cooperations/{coop_id}/review 契约。"""

    def test_buyer_submits_happy_path(
        self, client: TestClient, db
    ):
        """买方评价 happy path：review 写入 + reviewee_id 自动 = seller。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5, "comment": "非常专业", "tags": ["响应及时"]},
            headers=_auth(1001),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["rating"] == 5
        assert data["comment"] == "非常专业"
        assert data["tags"] == ["响应及时"]
        assert data["is_anonymous"] is False
        # reviewer_id 实名（自己看自己的）
        assert data["reviewer_id"] == 1001
        # reviewee 自动 = 对方（seller）
        assert data["reviewee_id"] == 1002
        # reviewee_brief 5 字段
        assert data["reviewee_brief"]["id"] == 1002

        # 合作被标记 buyer_reviewed
        with SessionLocal() as session:
            coop = session.get(Cooperation, 5001)
            assert coop.buyer_reviewed is True
            assert coop.seller_reviewed is False

    def test_seller_submits_happy_path(
        self, client: TestClient, db
    ):
        """卖方评价：reviewee_id 自动 = buyer。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 4, "comment": "客户配合"},
            headers=_auth(1002),  # seller
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # reviewer 实名（自己看）
        assert data["reviewer_id"] == 1002
        # reviewee 自动 = 买方
        assert data["reviewee_id"] == 1001

    def test_submit_with_minimal_payload(
        self, client: TestClient, db
    ):
        """只传 rating 即可：comment / tags / is_anonymous 都有默认值。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 3},
            headers=_auth(1001),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["rating"] == 3
        assert data["comment"] is None
        assert data["tags"] == []
        assert data["is_anonymous"] is False

    def test_submit_anonymous_review(
        self, client: TestClient, db
    ):
        """is_anonymous=True：自己看 reviewer_id 仍可见。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5, "is_anonymous": True},
            headers=_auth(1001),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 自己看自己 → reviewer_id 仍展示
        assert data["reviewer_id"] == 1001
        assert data["is_anonymous"] is True

    def test_submit_rejects_rating_above_5(
        self, client: TestClient, db
    ):
        """rating > 5 → 400/10001。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 6},
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 10001

    def test_submit_rejects_rating_below_1(
        self, client: TestClient, db
    ):
        """rating < 1 → 400/10001。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 0},
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 10001

    def test_submit_rejects_coop_not_found(
        self, client: TestClient, db
    ):
        """合作不存在 → 10002。"""
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/cooperations/99999/review",
            json={"rating": 5},
            headers=_auth(1001),
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_submit_rejects_third_party(
        self, client: TestClient, db
    ):
        """[P1-3 已锁] 第三方用户评价 → 10003。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_user(db, 1003, name="Carol")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5},
            headers=_auth(1003),
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

    def test_submit_rejects_terminated_coop(
        self, client: TestClient, db
    ):
        """合作 status=terminated → 400（合作未开始或已破裂不能评价）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(
            db, 5001, buyer_id=1001, seller_id=1002,
            status=CooperationStatus.TERMINATED,
        )

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5},
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        assert "合作尚未开始" in body["message"]

    def test_submit_allows_completed_coop(
        self, client: TestClient, db
    ):
        """已 completed 仍可补评价（双方都评前的状态可再评）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(
            db, 5001, buyer_id=1001, seller_id=1002,
            status=CooperationStatus.COMPLETED,
        )

        resp = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5},
            headers=_auth(1001),
        )
        assert resp.status_code == 200

    def test_submit_rejects_duplicate(
        self, client: TestClient, db
    ):
        """同一用户重复评价同一合作 → 400/10001（[D-005] 评价必填但不能重复）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        # 第一次
        r1 = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5},
            headers=_auth(1001),
        )
        assert r1.status_code == 200
        # 第二次
        r2 = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 4},
            headers=_auth(1001),
        )
        assert r2.status_code == 400
        body = r2.json()
        assert body["code"] == 10001
        assert "已评价" in body["message"]

    def test_submit_requires_auth(self, client: TestClient):
        resp = client.post(
            "/v1/cooperations/1/review",
            json={"rating": 5},
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003


# ============================================================
#  双评价 → 信用分重算 + status=COMPLETED
# ============================================================

class TestBothReviewedTriggersCompletion:
    """双方都评完触发：信用分自动重算 + status 推进到 COMPLETED。"""

    def test_both_reviewed_marks_coop_completed(
        self, client: TestClient, db
    ):
        """第一评价后 buyer_reviewed=True，第二评价后 status→COMPLETED。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        # 第一评（Alice）
        r1 = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5},
            headers=_auth(1001),
        )
        assert r1.status_code == 200
        with SessionLocal() as session:
            coop = session.get(Cooperation, 5001)
            assert coop.buyer_reviewed is True
            assert coop.seller_reviewed is False
            assert coop.status == CooperationStatus.HANDSHAKED  # 还没完成
            assert coop.closed_at is None

        # 第二评（Bob）
        r2 = client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 4},
            headers=_auth(1002),
        )
        assert r2.status_code == 200
        with SessionLocal() as session:
            coop = session.get(Cooperation, 5001)
            assert coop.buyer_reviewed is True
            assert coop.seller_reviewed is True
            # **status 自动推进到 completed**
            assert coop.status == CooperationStatus.COMPLETED
            assert coop.closed_at is not None

    def test_both_reviewed_triggers_credit_score_recompute(
        self, client: TestClient, db
    ):
        """双方都评完 → 双方信用分都重算（update_user_credit_score 调用）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        # Alice 评 Bob 5 星
        client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5},
            headers=_auth(1001),
        )
        # Bob 评 Alice 4 星（触发双方信用分重算）
        client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 4},
            headers=_auth(1002),
        )

        # 双方 rating_avg 都更新了
        with SessionLocal() as session:
            alice = session.get(User, 1001)
            bob = session.get(User, 1002)
            # Alice 收到 4 星评价
            assert alice.rating_count == 1
            assert alice.rating_avg == 4.0
            # Bob 收到 5 星评价
            assert bob.rating_count == 1
            assert bob.rating_avg == 5.0

    def test_first_review_does_not_recompute_credit(
        self, client: TestClient, db
    ):
        """第一评时信用分**不**重算（要等双方都评完）。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        # 只 Alice 评
        client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5},
            headers=_auth(1001),
        )

        with SessionLocal() as session:
            bob = session.get(User, 1002)
            # Bob 的 rating_count 还是 0（没收到评价）
            assert bob.rating_count == 0
            assert bob.rating_avg == 0.0


# ============================================================
#  GET /cooperations/{coop_id}/review  — 评价列表
# ============================================================

class TestListReviews:
    """GET /cooperations/{coop_id}/review 契约。"""

    def test_list_empty_when_no_reviews(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        resp = client.get(
            "/v1/cooperations/5001/review", headers=_auth(1001)
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_returns_all_reviews(
        self, client: TestClient, db
    ):
        """合作有 2 个评价（双方都评了）→ 都返回。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        # 双方都评价
        client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 5, "comment": "A→B"},
            headers=_auth(1001),
        )
        client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 4, "comment": "B→A"},
            headers=_auth(1002),
        )

        resp = client.get(
            "/v1/cooperations/5001/review", headers=_auth(1001)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        # 两条都有 reviewer_id（双方都看，对方也是 reviewer 所以展示）
        assert all(d["reviewer_id"] is not None for d in data)
        # reviewee_id 都填
        assert all(d["reviewee_id"] is not None for d in data)

    def test_list_anonymous_review_hides_reviewer_for_others(
        self, client: TestClient, db
    ):
        """[P1-3 已锁] 匿名评价 → 别人看 reviewer_id=None / reviewer_brief=None。"""
        _make_user(db, 1001, name="Alice", display_name="李先生")
        _make_user(db, 1002, name="Bob", display_name="张先生")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        # Alice 匿名评价 Bob
        client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 3, "is_anonymous": True},
            headers=_auth(1001),
        )

        # Bob 看（其他人）→ reviewer 字段被抹
        resp = client.get(
            "/v1/cooperations/5001/review", headers=_auth(1002)
        )
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["reviewer_id"] is None
        assert data[0]["reviewer_brief"] is None
        # reviewee 仍展示（评价对象始终实名）
        assert data[0]["reviewee_id"] == 1002
        assert data[0]["reviewee_brief"] is not None

    def test_list_anonymous_review_self_view_shows_reviewer(
        self, client: TestClient, db
    ):
        """[P1-3 已锁] 匿名评价 → 评价人自己看 reviewer_id 仍展示。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_cooperation(db, 5001, buyer_id=1001, seller_id=1002)

        client.post(
            "/v1/cooperations/5001/review",
            json={"rating": 3, "is_anonymous": True},
            headers=_auth(1001),
        )

        # Alice 看（评价人自己）
        resp = client.get(
            "/v1/cooperations/5001/review", headers=_auth(1001)
        )
        data = resp.json()["data"]
        # 即使匿名，自己看 reviewer_id 仍展示
        assert data[0]["reviewer_id"] == 1001
        assert data[0]["reviewer_brief"] is not None

    def test_list_coop_not_found(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        resp = client.get(
            "/v1/cooperations/99999/review", headers=_auth(1001)
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_list_requires_auth(self, client: TestClient):
        resp = client.get("/v1/cooperations/1/review")
        assert resp.status_code == 401


# ============================================================
#  _build_review_response 单元测试（4 组合）
# ============================================================

class TestBuildReviewResponse:
    """_build_review_response 4 组合：is_anonymous × is_self_view。"""

    def _review(self, is_anonymous: bool = False) -> Review:
        return Review(
            id=1,
            cooperation_id=5001,
            reviewer_id=1001,
            reviewee_id=1002,
            rating=5,
            comment="test",
            tags=[],
            is_anonymous=is_anonymous,
            created_at=datetime.now(timezone.utc),
        )

    def test_non_anonymous_other_view(
        self,
    ):
        """实名 + 别人看：reviewer_id/brief 都展示。"""
        from app.domains.reviews.router import _build_review_response
        from app.models.user import User

        r = self._review(is_anonymous=False)
        reviewer = User(id=1001, name="Alice", display_name="A先生",
                        credit_score=80.0, is_verified=True)
        reviewee = User(id=1002, name="Bob", display_name="B先生",
                        credit_score=85.0, is_verified=True)

        out = _build_review_response(r, reviewee, reviewer=reviewer, is_self_view=False)
        assert out["reviewer_id"] == 1001
        assert out["reviewer_brief"] is not None
        assert out["reviewer_brief"]["id"] == 1001
        assert out["reviewee_id"] == 1002
        assert out["reviewee_brief"] is not None

    def test_non_anonymous_self_view(
        self,
    ):
        """实名 + 自己看：reviewer_id/brief 仍展示。"""
        from app.domains.reviews.router import _build_review_response
        from app.models.user import User

        r = self._review(is_anonymous=False)
        reviewer = User(id=1001, name="Alice", display_name="A先生",
                        credit_score=80.0, is_verified=True)
        reviewee = User(id=1002, name="Bob", display_name="B先生",
                        credit_score=85.0, is_verified=True)

        out = _build_review_response(r, reviewee, reviewer=reviewer, is_self_view=True)
        assert out["reviewer_id"] == 1001
        assert out["reviewer_brief"] is not None

    def test_anonymous_other_view_hides_reviewer(
        self,
    ):
        """匿名 + 别人看：reviewer_id=None, reviewer_brief=None。"""
        from app.domains.reviews.router import _build_review_response
        from app.models.user import User

        r = self._review(is_anonymous=True)
        reviewer = User(id=1001, name="Alice", display_name="A先生",
                        credit_score=80.0, is_verified=True)
        reviewee = User(id=1002, name="Bob", display_name="B先生",
                        credit_score=85.0, is_verified=True)

        out = _build_review_response(r, reviewee, reviewer=reviewer, is_self_view=False)
        # 匿名 → reviewer 字段抹
        assert out["reviewer_id"] is None
        assert out["reviewer_brief"] is None
        # reviewee 仍展示
        assert out["reviewee_id"] == 1002
        assert out["reviewee_brief"] is not None

    def test_anonymous_self_view_shows_reviewer(
        self,
    ):
        """匿名 + 自己看：reviewer_id/brief 仍展示（[Sprint1-P0] 例外）。"""
        from app.domains.reviews.router import _build_review_response
        from app.models.user import User

        r = self._review(is_anonymous=True)
        reviewer = User(id=1001, name="Alice", display_name="A先生",
                        credit_score=80.0, is_verified=True)
        reviewee = User(id=1002, name="Bob", display_name="B先生",
                        credit_score=85.0, is_verified=True)

        out = _build_review_response(r, reviewee, reviewer=reviewer, is_self_view=True)
        # 自己看自己 → 仍展示
        assert out["reviewer_id"] == 1001
        assert out["reviewer_brief"] is not None
        assert out["reviewer_brief"]["id"] == 1001

    def test_response_includes_basic_fields(
        self,
    ):
        """base 字段 7 个都在。"""
        from app.domains.reviews.router import _build_review_response

        r = self._review(is_anonymous=False)
        out = _build_review_response(r, None, reviewer=None, is_self_view=False)
        for field in ["id", "cooperation_id", "rating", "comment", "tags",
                      "is_anonymous", "created_at"]:
            assert field in out, f"missing field: {field}"
        assert out["tags"] == []
        assert out["is_anonymous"] is False

    def test_no_reviewer_fallback_in_submit(
        self,
    ):
        """[router.py:74-80] 调用方没传 reviewer 时的 fallback：reviewer_id 填、brief=None。"""
        from app.domains.reviews.router import _build_review_response
        from app.models.user import User

        r = self._review(is_anonymous=False)
        reviewee = User(id=1002, name="Bob", display_name="B先生",
                        credit_score=85.0, is_verified=True)
        # reviewer=None（submit_review 路径）
        out = _build_review_response(r, reviewee, reviewer=None, is_self_view=True)
        assert out["reviewer_id"] == 1001  # 从 review.reviewer_id 拿
        assert out["reviewer_brief"] is None  # 没传 reviewer，brief 拿不到
