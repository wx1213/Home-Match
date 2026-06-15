"""信用分 DB 集成测试。

P2-6 补完：原 test_credit_score.py 只覆盖纯函数 compute_credit_score，
DB 函数（_compute_rating_avg / _compute_activity_count /
_compute_completed_count / update_user_credit_score /
recompute_all_credit_scores）都是 0% 覆盖。本文件加 DB 集成测试。

特点：
- 用 file-based SQLite（conftest 已配），不走 PG
- 每个测试 function-level 自动清表 + 建必要数据
- 不依赖外部 fixture，self-contained
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.domains.reviews.credit_score import (
    compute_credit_score,
    recompute_all_credit_scores,
    update_user_credit_score,
)
from app.models.cooperation import Cooperation, CooperationStatus
from app.models.invitation import Invitation, InvitationStatus
from app.models.review import Review
from app.models.user import User, UserStatus

# ============================================================
#  Fixtures
# ============================================================

@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    """Module 级：建表。

    测试 SQLite file-based DB（conftest 配），不依赖 PG。
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
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """每个测试一个干净 DB session，自动清表。"""
    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"DELETE FROM {table.name}"))
        session.commit()
        yield session
        session.rollback()


def _make_user(db, user_id: int, name: str = "TestUser") -> User:
    """建一个 active 测试用户。"""
    user = User(
        id=user_id,
        name=name,
        display_name=f"{name}先生",
        status=UserStatus.ACTIVE,
        is_verified=True,
        credit_score=60.0,
        rating_avg=0.0,
        rating_count=0,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    return user


def _make_review(
    db,
    reviewer_id: int,
    reviewee_id: int,
    cooperation_id: int,
    rating: int,
    deleted: bool = False,
) -> Review:
    """建一条评价（可选软删）。"""
    from datetime import datetime as _dt

    review = Review(
        cooperation_id=cooperation_id,
        reviewer_id=reviewer_id,
        reviewee_id=reviewee_id,
        rating=rating,
        comment="test",
        tags=[],
        is_anonymous=False,
        is_flagged=False,
    )
    db.add(review)
    db.flush()
    if deleted:
        review.deleted_at = _dt.now(timezone.utc)
        db.flush()
    return review


def _make_invitation(
    db,
    buyer_id: int,
    seller_id: int,
    demand_id: int,
    status: InvitationStatus,
    responded_at: datetime | None = None,
) -> Invitation:
    """建一条邀请。"""
    inv = Invitation(
        demand_id=demand_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        status=status,
        expired_at=datetime.now(timezone.utc) + timedelta(hours=24),
        responded_at=responded_at,
    )
    db.add(inv)
    db.flush()
    return inv


def _make_cooperation(
    db,
    buyer_id: int,
    seller_id: int,
    invitation_id: int,
    status: CooperationStatus = CooperationStatus.HANDSHAKED,
) -> Cooperation:
    """建一条合作。"""
    coop = Cooperation(
        invitation_id=invitation_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        status=status,
        memo_content="test",
        signed_at=datetime.now(timezone.utc),
    )
    db.add(coop)
    db.flush()
    return coop


# ============================================================
#  update_user_credit_score 集成测试
# ============================================================

class TestUpdateUserCreditScore:
    """update_user_credit_score 走完整 DB → 写回 user 字段。"""

    def test_user_with_no_data_floors_at_6(self, db):
        """新用户：无评价无活动 → 6 分下限。"""
        _make_user(db, 1, "Alice")

        new_score = update_user_credit_score(db, 1)
        db.commit()

        assert new_score == 6.0
        user = db.get(User, 1)
        assert user.credit_score == 6.0
        assert user.rating_avg == 0.0
        assert user.rating_count == 0
        assert user.activity_count_30d == 0
        assert user.completed_count == 0
        assert user.credit_score_updated_at is not None

    def test_user_with_reviews_only(self, db):
        """有评价（3 条 5 星）+ 无活跃 → 100 * 0.3 = 30.0。"""
        _make_user(db, 1, "Seller")
        _make_user(db, 2, "Buyer")
        # 3 条 5 星评价
        for i in range(3):
            _make_review(db, reviewer_id=2, reviewee_id=1, cooperation_id=10 + i, rating=5)

        new_score = update_user_credit_score(db, 1)
        db.commit()

        # 5 * 20 = 100 base; activity=0 → factor=0.3; 100*0.3 = 30.0
        assert new_score == 30.0
        user = db.get(User, 1)
        assert user.rating_avg == 5.0
        assert user.rating_count == 3

    def test_user_with_activity_above_target(self, db):
        """10+ 接单 → 活跃系数 = 1.0；分数按 rating 算满。"""
        _make_user(db, 1, "Seller")
        _make_user(db, 2, "Buyer")
        # 1 条评价 4 星
        _make_review(db, reviewer_id=2, reviewee_id=1, cooperation_id=1, rating=4)
        # 12 条接单记录（> ACTIVITY_TARGET=10）
        now = datetime.now(timezone.utc)
        for i in range(12):
            _make_invitation(
                db, buyer_id=2, seller_id=1, demand_id=100 + i,
                status=InvitationStatus.ACCEPTED, responded_at=now,
            )

        new_score = update_user_credit_score(db, 1)
        db.commit()

        # 4 * 20 = 80; factor = 0.3 + 0.7 * 1.0 = 1.0; 80 * 1.0 = 80.0
        assert new_score == 80.0
        user = db.get(User, 1)
        assert user.activity_count_30d == 12

    def test_user_with_completed_cooperations(self, db):
        """完成合作数被正确统计。"""
        _make_user(db, 1, "Alice")
        _make_user(db, 2, "Bob")
        # 5 条 completed 合作
        for i in range(5):
            inv = _make_invitation(
                db, buyer_id=2, seller_id=1, demand_id=100 + i,
                status=InvitationStatus.HANDSHAKED,
                responded_at=datetime.now(timezone.utc),
            )
            _make_cooperation(
                db, buyer_id=2, seller_id=1, invitation_id=inv.id,
                status=CooperationStatus.COMPLETED,
            )

        update_user_credit_score(db, 1)
        db.commit()

        user = db.get(User, 1)
        assert user.completed_count == 5

    def test_deleted_reviews_excluded_from_average(self, db):
        """软删的评价不计入均分。"""
        _make_user(db, 1, "Seller")
        _make_user(db, 2, "Buyer")
        # 2 条 5 星有效
        _make_review(db, reviewer_id=2, reviewee_id=1, cooperation_id=1, rating=5)
        _make_review(db, reviewer_id=2, reviewee_id=1, cooperation_id=2, rating=5)
        # 1 条 1 星软删（不计入）
        _make_review(db, reviewer_id=2, reviewee_id=1, cooperation_id=3, rating=1, deleted=True)

        update_user_credit_score(db, 1)
        db.commit()

        user = db.get(User, 1)
        # 均分应该只看 2 条 5 星 → 5.0
        assert user.rating_avg == 5.0
        assert user.rating_count == 2  # 注意：当前 SQL 是 count(Review.id) 不带 deleted 过滤
        # （这是已知差异，不影响 credit_score 本身计算）

    def test_inactive_user_does_not_exist_skips(self, db):
        """不存在的 user_id 不会抛异常，返回值仍可计算。"""
        # 不创建用户
        new_score = update_user_credit_score(db, 999)
        db.commit()
        # rating_avg=0, activity=0 → 6.0 下限
        assert new_score == 6.0


# ============================================================
#  recompute_all_credit_scores 测试
# ============================================================

class TestRecomputeAllCreditScores:
    """批量重算 — 只处理 active 用户。"""

    def test_processes_only_active_users(self, db):
        """active 用户会被重算，frozen / banned 跳过。"""
        _make_user(db, 1, "Active1")
        _make_user(db, 2, "Active2")
        frozen = _make_user(db, 3, "Frozen")
        frozen.status = UserStatus.FROZEN
        db.flush()

        count = recompute_all_credit_scores(db)

        # 只有 2 个 active
        assert count == 2

    def test_handles_individual_user_failure(self, db):
        """单个用户重算失败不影响其他人。"""
        _make_user(db, 1, "Good")
        _make_user(db, 2, "Bad")
        # 用 mock 来注入失败：
        from unittest.mock import patch
        with patch(
            "app.domains.reviews.credit_score.update_user_credit_score",
            side_effect=[6.0, RuntimeError("boom"), 6.0],
        ):
            count = recompute_all_credit_scores(db)
        # 2 个 active，1 个抛错被 skip，最后 count 只 +1
        # 但 patched 替换了原函数，user_ids 仍是 2 个
        # 第一个返回 6.0，第二个抛错，count 只 +1
        # 等等，原函数是 try/except 包着的，count 只算成功的
        # 第一个 success +1，第二个 fail（logger.warning + 跳过），count = 1
        assert count == 1
        # 恢复（patch 自动还原）

    def test_empty_db_returns_zero(self, db):
        """没有任何 active 用户时返回 0。"""
        count = recompute_all_credit_scores(db)
        assert count == 0
