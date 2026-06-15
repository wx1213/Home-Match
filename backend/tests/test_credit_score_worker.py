"""RQ 任务入口测试（[app/workers/credit_score.py]）。

P2-6 补完：原 0% 覆盖。本文件加 worker 层集成测试。

覆盖：
1. recompute_all_credit_scores_task — 调 recompute_all_credit_scores + 异常时 rollback
2. recompute_user_credit_score_task — 调 update_user_credit_score + commit + 异常 rollback
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.database import SessionLocal
from app.models.user import User, UserStatus
from app.workers.credit_score import (
    recompute_all_credit_scores_task,
    recompute_user_credit_score_task,
)


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    """Module 级：建表。"""
    from app.core.database import Base, engine
    from app.models import (  # noqa: F401
        cooperation,
        demand,
        invitation,
        property,
        proposal,
        review,
        user,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def clean_db():
    """每个测试一个干净 DB。"""
    from sqlalchemy import text

    from app.core.database import Base

    with SessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"DELETE FROM {table.name}"))
        session.commit()
    yield


def _make_user(user_id: int, name: str = "TestUser") -> None:
    """建一个 active 测试用户。"""
    from datetime import datetime, timezone
    with SessionLocal() as db:
        db.add(User(
            id=user_id,
            name=name,
            display_name=f"{name}先生",
            status=UserStatus.ACTIVE,
            is_verified=True,
            credit_score=60.0,
            last_login_at=datetime.now(timezone.utc),
        ))
        db.commit()


class TestRecomputeAllCreditScoresTask:
    """recompute_all_credit_scores_task 包装层。"""

    def test_returns_count_from_inner_function(self, clean_db):
        """正常路径：3 个 active 用户 → 返回 3。"""
        _make_user(1, "Alice")
        _make_user(2, "Bob")
        _make_user(3, "Carol")

        count = recompute_all_credit_scores_task()

        assert count == 3

    def test_empty_db_returns_zero(self, clean_db):
        """无 active 用户 → 返回 0。"""
        count = recompute_all_credit_scores_task()
        assert count == 0

    def test_inner_exception_triggers_rollback_then_reraises(self, clean_db):
        """recompute_all_credit_scores 抛异常 → 任务 catch + rollback + re-raise。"""
        with patch(
            "app.workers.credit_score.recompute_all_credit_scores",
            side_effect=RuntimeError("DB boom"),
        ), pytest.raises(RuntimeError, match="DB boom"):
            recompute_all_credit_scores_task()


class TestRecomputeUserCreditScoreTask:
    """recompute_user_credit_score_task 包装层。"""

    def test_returns_new_score(self, clean_db):
        """正常路径：返回 update_user_credit_score 的结果。"""
        _make_user(1, "Alice")

        score = recompute_user_credit_score_task(1)

        # 新用户无数据 → 6 分下限
        assert score == 6.0

    def test_commits_changes(self, clean_db):
        """成功路径会 db.commit()，user 字段被持久化。"""
        _make_user(1, "Alice")

        recompute_user_credit_score_task(1)

        # 重新开 session 验证
        with SessionLocal() as db:
            user = db.get(User, 1)
            assert user is not None
            assert user.credit_score == 6.0
            assert user.credit_score_updated_at is not None

    def test_inner_exception_triggers_rollback_then_reraises(self, clean_db):
        """update_user_credit_score 抛异常 → 任务 catch + rollback + re-raise。"""
        with patch(
            "app.workers.credit_score.update_user_credit_score",
            side_effect=RuntimeError("user boom"),
        ), pytest.raises(RuntimeError, match="user boom"):
            recompute_user_credit_score_task(999)
