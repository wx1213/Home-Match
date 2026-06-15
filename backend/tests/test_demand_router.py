"""Stage 3 任务 3: Demands 域端到端测试。

[demands/router.py](backend/app/domains/demands/router.py) 0% → 100% 覆盖。

已有覆盖（不再重复）：
- test_recommendation_degradation.py → Redis 降级（[Sprint1-P0] safe_get 不可用）
- test_authorization.py → P1-3 越权矩阵（含 demand delete）

本文件聚焦：
- 5 个端点的正常路径 + 校验 + 越权
- _generate_summary 字符串拼接逻辑
- recommendations 基础 Top 5 输出结构
- close_demand **幂等** 行为
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.demand import Demand, DemandStatus
from app.models.property import Property, PropertyStatus
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
    """每个测试一个干净 DB — **drop + recreate** tables 模式。

    DELETE FROM 模式 + session 关闭对推荐接口不起作用（TestClient 用 connection pool
    里的连接，DELETE 写盘后该连接还是看不到新数据 — SQLite locking 怪现象）。
    drop_all + create_all 强制刷新 schema + WAL，绝对干净。
    """
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
def _flush_recommendation_cache():
    """每个测试前后清掉推荐结果缓存（5min TTL，跨测试会污染）。

    [matcher.py:90-94] 用 demand_id 作 cache key，相同 demand_id 在两个测试
    里会返回上次的缓存（即使 DB 已 drop）。
    """
    from app.core import redis_client as rc

    def _flush():
        # 删所有 recommendation:* 键（scan_iter 避免 KEYS 阻塞 Redis）
        for k in rc.redis_client.scan_iter(match="recommendation:*"):
            rc.redis_client.delete(k)

    _flush()
    yield
    _flush()


def _make_user(
    _db,
    user_id: int,
    name: str = "TestUser",
    display_name: str | None = None,
    credit_score: float = 80.0,
) -> User:
    """每个 helper 自己开 SessionLocal（避免共用连接池状态污染）。

    `_db` 形参保留仅为 API 一致（test 仍传 db fixture）。
    """
    user = User(
        id=user_id,
        name=name,
        display_name=display_name or f"{name}先生",
        status=UserStatus.ACTIVE,
        is_verified=True,
        credit_score=credit_score,
        rating_avg=4.0,
        rating_count=0,
        activity_count_30d=5,
        last_login_at=datetime.now(timezone.utc),
    )
    with SessionLocal() as session:
        session.add(user)
        session.commit()
    return user


def _make_demand(
    _db,
    demand_id: int,
    buyer_id: int,
    **overrides,
) -> Demand:
    """建一个 ACTIVE 测试需求。"""
    defaults = {
        "district": "朝阳区",
        "price_min": 3_000_000.0,
        "price_max": 5_000_000.0,
        "layouts": ["2室1厅"],
        "qualification": "首套",
        "viewing_time": ["周末"],
        "source_url": None,
        "status": DemandStatus.ACTIVE,
        "summary": None,
    }
    defaults.update(overrides)
    demand = Demand(id=demand_id, buyer_id=buyer_id, **defaults)
    with SessionLocal() as session:
        session.add(demand)
        session.commit()
    return demand


def _make_property(
    _db,
    prop_id: int,
    seller_id: int,
    **overrides,
) -> Property:
    defaults = {
        "community": "望京西园",
        "layout": "2室1厅",
        "area": 90.0,
        "total_price": 4_200_000.0,
        "tags": [],
        "images": [],
        "viewing_time": "工作日晚上+周末",
        "status": PropertyStatus.ACTIVE,
    }
    defaults.update(overrides)
    prop = Property(id=prop_id, seller_id=seller_id, **defaults)
    with SessionLocal() as session:
        session.add(prop)
        session.commit()
    return prop


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ============================================================
#  POST /demands  — 发布需求
# ============================================================

class TestCreateDemand:
    """POST /demands 契约。"""

    def test_create_returns_200_with_active_status_and_summary(
        self, client: TestClient, db
    ):
        """正常创建：status=active + summary 自动生成。"""
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/demands",
            json={
                "district": "朝阳区",
                "price_min": 3_000_000,
                "price_max": 5_000_000,
                "layouts": ["2室1厅", "3室1厅"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=_auth(1001),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "active"
        assert data["buyer_id"] == 1001
        assert data["district"] == "朝阳区"
        assert data["summary"] is not None
        # 摘要格式: "朝阳区 | 300-500万 | 2室1厅、3室1厅 | 首套 | 周末"
        assert "朝阳区" in data["summary"]
        assert "300-500万" in data["summary"]
        assert "首套" in data["summary"]

    def test_create_with_source_url(
        self, client: TestClient, db
    ):
        """带 source_url（贝壳链接）能存。"""
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/demands",
            json={
                "district": "海淀区",
                "price_min": 4_000_000,
                "price_max": 6_000_000,
                "layouts": ["3室1厅"],
                "qualification": "不限",
                "viewing_time": ["工作日晚上"],
                "source_url": "https://ke.com/buyhouse/abc.html",
            },
            headers=_auth(1001),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["source_url"] == "https://ke.com/buyhouse/abc.html"

    def test_create_rejects_min_greater_than_max(
        self, client: TestClient, db
    ):
        """price_min > price_max → 400 + 10001。"""
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/demands",
            json={
                "district": "朝阳区",
                "price_min": 5_000_000,  # min > max
                "price_max": 3_000_000,
                "layouts": ["2室1厅"],
                "qualification": "首套",
                "viewing_time": ["周末"],
            },
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        assert "价格区间" in body["message"]

    def test_create_rejects_zero_price(
        self, client: TestClient, db
    ):
        """price_min=0 → 400 + 10001（Field(gt=0)）。"""
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/demands",
            json={
                "district": "朝阳区",
                "price_min": 0,
                "price_max": 5_000_000,
                "layouts": [],
                "qualification": "不限",
                "viewing_time": [],
            },
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 10001

    def test_create_rejects_missing_required_field(
        self, client: TestClient, db
    ):
        """漏掉必填 district → 400 + 10001。"""
        _make_user(db, 1001, name="Alice")
        resp = client.post(
            "/v1/demands",
            json={
                # district missing
                "price_min": 3_000_000,
                "price_max": 5_000_000,
                "layouts": [],
                "qualification": "不限",
                "viewing_time": [],
            },
            headers=_auth(1001),
        )
        assert resp.status_code == 400
        assert "district" in str(resp.json())

    def test_create_buyer_id_comes_from_token(
        self, client: TestClient, db
    ):
        """buyer_id 永远从 JWT 取，不被 body 覆盖。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")

        body = {
            "district": "朝阳区",
            "price_min": 3_000_000,
            "price_max": 5_000_000,
            "layouts": [],
            "qualification": "不限",
            "viewing_time": [],
        }
        # 即使 body 里塞 buyer_id，存进 DB 的是 token 里的
        # 注：DemandCreate schema 没有 buyer_id 字段，所以这里只能验
        # status / district 正确就代表是 token 里的 user.id
        resp = client.post("/v1/demands", json=body, headers=_auth(1001))
        assert resp.json()["data"]["buyer_id"] == 1001

    def test_create_requires_auth(self, client: TestClient):
        resp = client.post(
            "/v1/demands",
            json={
                "district": "朝阳区",
                "price_min": 3_000_000,
                "price_max": 5_000_000,
                "layouts": [],
                "qualification": "不限",
                "viewing_time": [],
            },
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == 20003


# ============================================================
#  GET /demands  — 我的需求
# ============================================================

class TestListMyDemands:
    """GET /demands 契约。"""

    def test_list_empty_when_no_demands(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        resp = client.get("/v1/demands", headers=_auth(1001))
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_list_returns_only_my_demands(
        self, client: TestClient, db
    ):
        """用户 A 只能看到自己的需求。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001, district="A 区")
        _make_demand(db, 2002, buyer_id=1002, district="B 区")
        _make_demand(db, 2003, buyer_id=1002, district="B 区 2")

        resp = client.get("/v1/demands", headers=_auth(1001))
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["district"] == "A 区"
        assert data[0]["buyer_id"] == 1001

    def test_list_excludes_soft_deleted(
        self, client: TestClient, db
    ):
        """软删的需求不出现。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001, district="保留")
        d2 = _make_demand(db, 2002, buyer_id=1001, district="关闭")
        # 手动软删
        with SessionLocal() as session:
            d2 = session.get(Demand, d2.id)
            d2.deleted_at = datetime.now(timezone.utc)
            d2.status = DemandStatus.CLOSED
            session.commit()

        resp = client.get("/v1/demands", headers=_auth(1001))
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["district"] == "保留"

    def test_list_requires_auth(self, client: TestClient):
        resp = client.get("/v1/demands")
        assert resp.status_code == 401


# ============================================================
#  GET /demands/{id}  — 需求详情（含 buyer_brief 脱敏）
# ============================================================

class TestGetDemand:
    """GET /demands/{id} 契约（[Sprint1-P0] 含 buyer_brief 脱敏）。"""

    def test_get_returns_buyer_brief_with_masked_fields(
        self, client: TestClient, db
    ):
        """详情含 buyer_brief：5 字段，不含真实姓名/手机/邮箱。

        用第三方用户 1002 看 A 的需求 → buyer_brief 5 字段脱敏。
        """
        _make_user(db, 1001, name="李寻欢", display_name="李先生")
        _make_user(db, 1002, name="访客", display_name="访客先生")  # 第三方查看者
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.get("/v1/demands/2001", headers=_auth(1002))
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 业务字段
        assert data["id"] == 2001
        assert data["district"] == "朝阳区"

        # buyer_brief
        bb = data["buyer_brief"]
        assert bb is not None
        assert bb["id"] == 1001
        assert bb["display_name"] == "李先生"  # 脱敏后的名字

        # 不暴露真实姓名/手机/邮箱
        forbidden = {"name", "phone_encrypted", "phone_hash", "email", "wechat_unionid"}
        leaked = forbidden & set(bb.keys())
        assert not leaked, f"buyer_brief leaked sensitive keys: {leaked}"

    def test_get_self_demand_also_returns_masked_brief(
        self, client: TestClient, db
    ):
        """自己看自己：buyer_brief 也脱敏（[Sprint1-P0]）。"""
        _make_user(db, 1001, name="我自己", display_name="我先生")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.get("/v1/demands/2001", headers=_auth(1001))
        bb = resp.json()["data"]["buyer_brief"]
        assert bb["display_name"] == "我先生"
        assert "name" not in bb

    def test_get_not_found_returns_10002(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        resp = client.get("/v1/demands/99999", headers=_auth(1001))
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_get_soft_deleted_returns_404(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)
        # 手动软删
        with SessionLocal() as session:
            d = session.get(Demand, 2001)
            d.deleted_at = datetime.now(timezone.utc)
            session.commit()

        resp = client.get("/v1/demands/2001", headers=_auth(1001))
        assert resp.status_code == 404

    def test_get_known_gap_other_user_can_view(
        self, client: TestClient, db
    ):
        """[P1-3 已知缺口] GET /demands/{id} 任意登录用户可看，**不**做权限拦截。

        锁定这个 gap（防止有人无意中加了 403 改坏语义）。
        """
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.get("/v1/demands/2001", headers=_auth(1002))
        assert resp.status_code == 200  # 不是 403
        assert resp.json()["data"]["buyer_id"] == 1001

    def test_get_requires_auth(self, client: TestClient):
        resp = client.get("/v1/demands/1")
        assert resp.status_code == 401


# ============================================================
#  GET /demands/{id}/recommendations  — Top 5 推荐
# ============================================================

class TestGetRecommendations:
    """GET /demands/{id}/recommendations 契约（不测 Redis 降级，那在 test_recommendation_degradation.py）。"""

    def test_recommendations_returns_top_sellers_with_properties(
        self, client: TestClient, db
    ):
        """正常路径：返回 Top N 卖方 + 每个卖方带 matched_properties。"""
        # 买方
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)

        # 3 个卖方，每个 1 个 active 房源，价格都在区间内
        for i, sid in enumerate([2001, 2002, 2003], 1):
            _make_user(
                db, sid, name=f"Seller{i}",
                display_name=f"卖方{i}", credit_score=80 + i * 5,
            )
            _make_property(
                db, prop_id=3000 + i, seller_id=sid,
                total_price=3_500_000 + i * 100_000, layout="2室1厅",
            )

        resp = client.get(
            "/v1/demands/2001/recommendations", headers=_auth(1001)
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["demand_id"] == 2001
        assert len(data["sellers"]) == 3
        # rank 1/2/3 连续
        assert [s["rank"] for s in data["sellers"]] == [1, 2, 3]
        # 每个 seller 含 7 字段 + matched_properties
        for s in data["sellers"]:
            assert "match_score" in s
            assert 0 < s["match_score"] <= 1.0
            assert "seller" in s
            assert "matched_properties" in s
            assert len(s["matched_properties"]) >= 1
            # seller 脱敏字段
            seller = s["seller"]
            for field in ["id", "display_name", "credit_score",
                          "rating_avg", "completed_count"]:
                assert field in seller

    def test_recommendations_excludes_buyer_self(
        self, client: TestClient, db
    ):
        """买方本人不出现在推荐里。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)
        # Alice 自己又有 active 房源（罕见但要排除）
        _make_property(db, 3001, seller_id=1001, total_price=4_000_000)
        # Bob 是真卖方
        _make_user(db, 1002, name="Bob")
        _make_property(db, 3002, seller_id=1002, total_price=4_000_000)

        resp = client.get(
            "/v1/demands/2001/recommendations", headers=_auth(1001)
        )
        sellers = resp.json()["data"]["sellers"]
        seller_ids = [s["seller"]["id"] for s in sellers]
        assert 1001 not in seller_ids  # 自己排除
        assert 1002 in seller_ids

    def test_recommendations_excludes_sellers_with_no_active_property(
        self, client: TestClient, db
    ):
        """没 active 房源的卖方不出现。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)
        # Bob 有 active 房源
        _make_user(db, 1002, name="Bob")
        _make_property(db, 3001, seller_id=1002)
        # Carol 没房源
        _make_user(db, 1003, name="Carol")

        resp = client.get(
            "/v1/demands/2001/recommendations", headers=_auth(1001)
        )
        seller_ids = [s["seller"]["id"] for s in resp.json()["data"]["sellers"]]
        assert 1002 in seller_ids
        assert 1003 not in seller_ids

    def test_recommendations_excludes_inactive_sellers(
        self, client: TestClient, db
    ):
        """frozen 状态的用户不出现。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)
        # Bob frozen
        _make_user(db, 1002, name="Bob")
        with SessionLocal() as session:
            bob = session.get(User, 1002)
            bob.status = UserStatus.FROZEN
            session.commit()
        _make_property(db, 3001, seller_id=1002)

        resp = client.get(
            "/v1/demands/2001/recommendations", headers=_auth(1001)
        )
        seller_ids = [s["seller"]["id"] for s in resp.json()["data"]["sellers"]]
        assert 1002 not in seller_ids

    def test_recommendations_empty_when_no_sellers(
        self, client: TestClient, db
    ):
        """没卖方 → 空 list。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.get(
            "/v1/demands/2001/recommendations", headers=_auth(1001)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["sellers"] == []

    def test_recommendations_demand_not_found_returns_10002(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        resp = client.get(
            "/v1/demands/99999/recommendations", headers=_auth(1001)
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_recommendations_known_gap_no_ownership_check(
        self, client: TestClient, db
    ):
        """[P1-3 已知缺口] 推荐接口任意登录用户可看，**不**做权限拦截。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.get(
            "/v1/demands/2001/recommendations", headers=_auth(1002)
        )
        assert resp.status_code == 200  # 不是 403

    def test_recommendations_requires_auth(self, client: TestClient):
        resp = client.get("/v1/demands/1/recommendations")
        assert resp.status_code == 401


# ============================================================
#  DELETE /demands/{id}  — 下架需求（幂等）
# ============================================================

class TestCloseDemand:
    """DELETE /demands/{id} 契约（幂等下架 + 越权）。"""

    def test_close_own_demand_sets_deleted_and_closed(
        self, client: TestClient, db
    ):
        """下架自己需求：deleted_at 非空 + status=closed。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.delete("/v1/demands/2001", headers=_auth(1001))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == 2001
        assert data["status"] == "closed"
        # 第一次关闭不带 idempotent
        assert "idempotent" not in data or data.get("idempotent") is False

        with SessionLocal() as session:
            d = session.get(Demand, 2001)
            assert d.deleted_at is not None
            assert d.status == DemandStatus.CLOSED

    def test_close_is_idempotent(
        self, client: TestClient, db
    ):
        """重复下架返 200 + idempotent=True（APP 防双击）。"""
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)

        # 第一次
        r1 = client.delete("/v1/demands/2001", headers=_auth(1001))
        assert r1.status_code == 200
        # 第二次（幂等）
        r2 = client.delete("/v1/demands/2001", headers=_auth(1001))
        assert r2.status_code == 200
        data = r2.json()["data"]
        assert data["status"] == "closed"
        assert data.get("idempotent") is True

    def test_close_other_users_demand_returns_10003(
        self, client: TestClient, db
    ):
        """用户 B 关闭 A 的需求 → 403。"""
        _make_user(db, 1001, name="Alice")
        _make_user(db, 1002, name="Bob")
        _make_demand(db, 2001, buyer_id=1001)

        resp = client.delete("/v1/demands/2001", headers=_auth(1002))
        assert resp.status_code == 403
        assert resp.json()["code"] == 10003

        # DB 状态没变
        with SessionLocal() as session:
            d = session.get(Demand, 2001)
            assert d.deleted_at is None
            assert d.status == DemandStatus.ACTIVE

    def test_close_not_found_returns_10002(
        self, client: TestClient, db
    ):
        _make_user(db, 1001, name="Alice")
        resp = client.delete("/v1/demands/99999", headers=_auth(1001))
        assert resp.status_code == 404
        assert resp.json()["code"] == 10002

    def test_close_soft_deleted_is_idempotent(
        self, client: TestClient, db
    ):
        """[幂等旁路] 需求已 deleted_at 但 status 还是 ACTIVE → 仍判定幂等。

        这是 P1-3 设计：任何"已下架过"的状态都返 idempotent=True。
        """
        _make_user(db, 1001, name="Alice")
        _make_demand(db, 2001, buyer_id=1001)
        with SessionLocal() as session:
            d = session.get(Demand, 2001)
            d.deleted_at = datetime.now(timezone.utc)
            # 故意 status 留 active
            session.commit()

        resp = client.delete("/v1/demands/2001", headers=_auth(1001))
        assert resp.status_code == 200
        assert resp.json()["data"].get("idempotent") is True

    def test_close_requires_auth(self, client: TestClient):
        resp = client.delete("/v1/demands/1")
        assert resp.status_code == 401


# ============================================================
#  _generate_summary 拼接逻辑
# ============================================================

class TestGenerateSummary:
    """_generate_summary 字符串拼接覆盖。"""

    def test_summary_includes_district_price_layouts_qualification_viewing(
        self,
    ):
        """摘要 5 段：district | price_min-max万 | layouts | qualification | viewing_time。"""
        from app.domains.demands.router import _generate_summary
        d = Demand(
            id=1, buyer_id=1,
            district="海淀区",
            price_min=3_500_000,
            price_max=4_500_000,
            layouts=["2室1厅", "3室1厅"],
            qualification="首套",
            viewing_time=["周末"],
        )
        s = _generate_summary(d)
        assert s == "海淀区 | 350-450万 | 2室1厅、3室1厅 | 首套 | 周末"

    def test_summary_empty_layouts_uses_不限(self):
        from app.domains.demands.router import _generate_summary
        d = Demand(
            id=1, buyer_id=1,
            district="朝阳区",
            price_min=3_000_000,
            price_max=5_000_000,
            layouts=[],
            qualification="不限",
            viewing_time=["周末"],
        )
        s = _generate_summary(d)
        assert "不限" in s

    def test_summary_empty_viewing_uses_时间不限(self):
        from app.domains.demands.router import _generate_summary
        d = Demand(
            id=1, buyer_id=1,
            district="朝阳区",
            price_min=3_000_000,
            price_max=5_000_000,
            layouts=["2室1厅"],
            qualification="首套",
            viewing_time=[],
        )
        s = _generate_summary(d)
        assert "时间不限" in s
