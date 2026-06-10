"""P1-4 推荐接口降级测试。

验证：Redis 不可用时，GET /demands/{id}/recommendations 应该**降级**到规则匹配，
**不应该** 5xx。

测试方法：
- mock `safe_get` / `safe_setex` 抛 ConnectionError
- 调推荐接口，断言 200 + 拿到有效推荐
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
import redis.exceptions
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
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
        proposal,
        property,
        review,
        user,
    )
    from app.models.device import Device  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def seeded():
    """建 1 个 buyer A + 1 个 seller B + B 的 1 个 property + 1 个 A 的 demand。"""
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
        # B = seller（有房源）
        db.add(User(
            id=102, name="Bob", display_name="Bob先生",
            status=UserStatus.ACTIVE, is_verified=True,
            credit_score=85.0, rating_avg=4.5, rating_count=3,
            last_login_at=datetime.now(timezone.utc),
        ))
        # C = seller（无房源，应该被过滤）
        db.add(User(
            id=103, name="Carol", display_name="Carol先生",
            status=UserStatus.ACTIVE, is_verified=True,
            credit_score=90.0, rating_avg=5.0, rating_count=10,
            last_login_at=datetime.now(timezone.utc),
        ))
        db.commit()
        # B 的房源
        from app.models.property import Property, PropertyStatus
        db.add(Property(
            id=201, seller_id=102,
            community="望京西园", layout="3室1厅", area=95.5,
            total_price=4_200_000, tags=["近地铁"], images=[],
            viewing_time="工作日晚上", source_url=None,
            is_verified=True, status=PropertyStatus.ACTIVE,
        ))
        db.commit()
        # A 的需求
        from app.models.demand import Demand, DemandStatus
        db.add(Demand(
            id=301, buyer_id=101,
            district="朝阳区", price_min=3_500_000, price_max=4_500_000,
            layouts=["3室1厅"], qualification="首套",
            viewing_time=["周末"], source_url=None,
            status=DemandStatus.ACTIVE,
            summary="朝阳区 | 350-450万 | 3室1厅 | 首套 | 周末",
            invite_count=0,
        ))
        db.commit()
    return {"A_id": 101, "B_id": 102, "C_id": 103, "demand_id": 301, "B_prop_id": 201}


def _auth(user_id: int) -> dict[str, str]:
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ============================================================
#  P1-4 核心测试：Redis 不可用时推荐接口应降级
# ============================================================

class TestRecommendationDegradation:
    """Redis 不可用时，匹配器应降级到实时计算，不应 5xx。"""

    def test_recommendation_succeeds_when_redis_get_fails(
        self, client: TestClient, seeded, monkeypatch
    ):
        """P1-4 核心：redis_client.get 抛 ConnectionError → safe_get 返 None → matcher 回退到 DB 计算。"""
        from app.core import redis_client as rc_module

        def mock_redis_get(*args, **kwargs):
            raise redis.exceptions.ConnectionError("Redis down (simulated)")

        # 在 redis_client 模块层面 mock 掉真实 redis 客户端
        monkeypatch.setattr(rc_module.redis_client, "get", mock_redis_get)

        resp = client.get(
            f"/v1/demands/{seeded['demand_id']}/recommendations",
            headers=_auth(seeded["A_id"]),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["code"] == 0
        sellers = data["data"]["sellers"]
        # B 应该有房源且匹配 C 段，所以应该被推荐
        seller_ids = [s["seller"]["id"] for s in sellers]
        assert seeded["B_id"] in seller_ids, (
            f"Expected B (id={seeded['B_id']}) in {seller_ids}"
        )
        # C 无房源，应该被排除
        assert seeded["C_id"] not in seller_ids, (
            f"C should be excluded (no property), but found in {seller_ids}"
        )

    def test_recommendation_succeeds_when_redis_setex_fails(
        self, client: TestClient, seeded, monkeypatch
    ):
        """P1-4：redis_client.setex 抛 ConnectionError → safe_setex 返 False → matcher 不应崩。"""
        from app.core import redis_client as rc_module

        def mock_redis_setex(*args, **kwargs):
            raise redis.exceptions.ConnectionError("Redis down (simulated)")

        monkeypatch.setattr(rc_module.redis_client, "setex", mock_redis_setex)

        resp = client.get(
            f"/v1/demands/{seeded['demand_id']}/recommendations",
            headers=_auth(seeded["A_id"]),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["code"] == 0
        assert len(data["data"]["sellers"]) > 0

    def test_recommendation_succeeds_when_redis_get_returns_corrupt_data(
        self, client: TestClient, seeded, monkeypatch
    ):
        """safe_get 返非 JSON → matcher 应忽略缓存，走 DB 计算（已有逻辑）。"""
        from app.agents import matcher

        def mock_safe_get(key: str):
            return "this is not valid json {{"

        monkeypatch.setattr(matcher, "safe_get", mock_safe_get)

        resp = client.get(
            f"/v1/demands/{seeded['demand_id']}/recommendations",
            headers=_auth(seeded["A_id"]),
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["code"] == 0
        # 应该返 DB 实时计算结果
        assert len(data["data"]["sellers"]) > 0

    def test_recommendation_uses_cache_when_redis_works(
        self, client: TestClient, seeded, monkeypatch
    ):
        """正常路径：第一次算 + 写缓存，第二次从缓存读（验证 helper 集成正常）。"""
        call_count = {"get": 0, "setex": 0}

        def mock_safe_get(key: str):
            call_count["get"] += 1
            return None  # 模拟冷启动

        def mock_safe_setex(key: str, ttl: int, value: str) -> bool:
            call_count["setex"] += 1
            return True

        from app.agents import matcher
        monkeypatch.setattr(matcher, "safe_get", mock_safe_get)
        monkeypatch.setattr(matcher, "safe_setex", mock_safe_setex)

        # 第一次
        resp1 = client.get(
            f"/v1/demands/{seeded['demand_id']}/recommendations",
            headers=_auth(seeded["A_id"]),
        )
        assert resp1.status_code == 200
        assert call_count["get"] == 1
        assert call_count["setex"] == 1

        # 第二次：模拟缓存命中
        cached_data = json.dumps(resp1.json()["data"]["sellers"], default=str)
        def mock_cached_get(key: str):
            call_count["get"] += 1
            return cached_data
        monkeypatch.setattr(matcher, "safe_get", mock_cached_get)

        resp2 = client.get(
            f"/v1/demands/{seeded['demand_id']}/recommendations",
            headers=_auth(seeded["A_id"]),
        )
        assert resp2.status_code == 200
        # 第二次 get 调用了 1 次（mock cached_get）；setex 不会调（缓存命中不重写）
        assert call_count["get"] == 2
        assert call_count["setex"] == 1
