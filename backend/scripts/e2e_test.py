"""HomeMatch 端到端集成测试。

流程：
  1. 准备测试数据（2 个用户：buyer + seller）
  2. seller 发布房源
  3. buyer 发布需求
  4. buyer 获取 Top 5 推荐
  5. buyer 发起邀请
  6. seller 接单
  7. seller 提交方案
  8. buyer 确认方案 → 握手 → 合作建立
  9. 验证所有数据正确落库

运行：python scripts/e2e_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 把项目根加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import json
from datetime import datetime, timezone

from app.core.config import settings
from app.core.crypto import encrypt_phone, hash_phone
from app.core.database import SessionLocal
from app.models.user import User, UserStatus


BASE_URL = "http://localhost:8000"


def setup_test_users() -> tuple[int, int]:
    """准备测试用户：2 个 active 用户。返回 (buyer_id, seller_id)。"""
    with SessionLocal() as db:
        # 用户 1：买方
        buyer = db.get(User, 1)
        if not buyer:
            phone = "13800138001"
            buyer = User(
                wechat_unionid="test_buyer_unionid",
                wechat_openid="test_buyer_openid",
                phone_encrypted=encrypt_phone(phone),
                phone_hash=hash_phone(phone),
                name="测试买方-张三",
                display_name="张先生",
                credit_score=80.0,
                rating_avg=4.5,
                rating_count=10,
                status=UserStatus.ACTIVE,
            )
            db.add(buyer)
            db.flush()
            print(f"  [SETUP] Created buyer: id={buyer.id}")
        else:
            print(f"  [SETUP] Buyer already exists: id={buyer.id}")

        # 用户 2：卖方
        seller = db.get(User, 2)
        if not seller:
            phone = "13800138002"
            seller = User(
                wechat_unionid="test_seller_unionid",
                wechat_openid="test_seller_openid",
                phone_encrypted=encrypt_phone(phone),
                phone_hash=hash_phone(phone),
                name="测试卖方-李四",
                display_name="李女士",
                credit_score=85.0,
                rating_avg=4.7,
                rating_count=15,
                status=UserStatus.ACTIVE,
            )
            db.add(seller)
            db.flush()
            print(f"  [SETUP] Created seller: id={seller.id}")
        else:
            print(f"  [SETUP] Seller already exists: id={seller.id}")

        db.commit()
        return buyer.id, seller.id


def override_user_id(client: httpx.Client, user_id: int) -> None:
    """MVP 阶段：路由硬编码 user_id=1。
    测试时用 httpx header 注入 - 但需要路由支持。
    简化处理：每个步骤里手动修改请求 body 里的 user_id。
    """
    pass  # 暂未用，依赖 SQL 验证


def assert_resp(resp: httpx.Response, expected_status: int, label: str) -> dict:
    """断言响应状态并返回 data。"""
    if resp.status_code != expected_status:
        print(f"  ❌ {label}: HTTP {resp.status_code}")
        print(f"     Body: {resp.text[:500]}")
        raise AssertionError(f"{label} failed: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") != 0:
        print(f"  ❌ {label}: code={data.get('code')}, msg={data.get('message')}")
        raise AssertionError(f"{label} failed: {data.get('message')}")
    print(f"  ✅ {label}: HTTP {resp.status_code}, data keys = {list((data.get('data') or {}).keys())[:5]}")
    return data.get("data") or {}


def main():
    print("=" * 70)
    print("HomeMatch 端到端集成测试")
    print("=" * 70)

    # === Step 0: 准备测试数据 ===
    print("\n[Step 0] 准备测试用户...")
    buyer_id, seller_id = setup_test_users()
    print(f"  buyer_id={buyer_id}, seller_id={seller_id}")

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # === Step 1: 健康检查 ===
        print("\n[Step 1] 健康检查...")
        r = client.get("/v1/health")
        h = r.json()
        assert r.status_code == 200
        print(f"  ✅ 服务状态: {h['status']}, db={h['checks']['database']}, redis={h['checks']['redis']}")

        # === Step 2: seller 发布房源 ===
        print("\n[Step 2] seller 发布房源...")
        # 路由硬编码 user_id=1，所以这里建房源的 seller_id 会是 1
        # 但我们想 seller_id=2（用户 2）。所以先建一个 user_id=1 的房源
        # MVP 阶段简化：所有操作都用 user_id=1（buyer = seller）
        # 在测试中我们让 user 1 同时是 buyer 和 seller
        # 所以 seller_id 也用 1

        # 房源数据
        property_data = {
            "community": "望京西园",
            "layout": "3室1厅",
            "area": 95.5,
            "total_price": 4200000,
            "tags": ["满五唯一", "近地铁", "南北通透"],
            "images": ["https://placeholder/img1.jpg", "https://placeholder/img2.jpg"],
            "viewing_time": "工作日晚上+周末",
            "is_verified": True,
        }
        r = client.post("/v1/properties", json=property_data)
        prop = assert_resp(r, 200, "Create property")
        prop_id = prop["id"]

        # === Step 3: buyer 发布需求 ===
        print("\n[Step 3] buyer 发布需求...")
        demand_data = {
            "district": "朝阳区",
            "price_min": 3500000,
            "price_max": 4500000,
            "layouts": ["3室1厅", "2室1厅"],
            "qualification": "首套",
            "viewing_time": ["工作日晚上", "周末"],
        }
        r = client.post("/v1/demands", json=demand_data)
        demand = assert_resp(r, 200, "Create demand")
        demand_id = demand["id"]
        print(f"  📋 需求摘要: {demand.get('summary')}")

        # === Step 4: buyer 获取 Top 5 推荐 ===
        print("\n[Step 4] buyer 获取 Top 5 推荐...")
        r = client.get(f"/v1/demands/{demand_id}/recommendations")
        rec = assert_resp(r, 200, "Get recommendations")
        sellers = rec.get("sellers", [])
        print(f"  🎯 推荐数: {len(sellers)}")
        if sellers:
            top = sellers[0]
            print(f"     #1: seller_id={top['seller']['id']}, match_score={top['match_score']}, "
                  f"matched_properties={len(top['matched_properties'])}")

        # === Step 5: buyer 发起邀请 ===
        print("\n[Step 5] buyer 发起邀请...")
        # 我们的 user 1 同时是 buyer 和 seller
        # 实际场景：buyer_id != seller_id，但 MVP 简化用同一用户
        # 让 seller_id 也指向 user 1（既是 buyer 又是 seller）
        inv_data = {
            "demand_id": demand_id,
            "seller_id": buyer_id,  # MVP 简化：同一用户
            "note": "客户总价 400-450w，望京附近，3 室优先",
        }
        r = client.post("/v1/invitations", json=inv_data)
        inv = assert_resp(r, 200, "Create invitation")
        inv_id = inv["id"]
        print(f"  ⏰ 过期时间: {inv['expired_at']}")
        print(f"  📌 状态: {inv['status']}")

        # === Step 6: seller 接单 ===
        print("\n[Step 6] seller 接单...")
        r = client.post(f"/v1/invitations/{inv_id}/accept")
        accept_resp = assert_resp(r, 200, "Accept invitation")
        print(f"  ⏰ 方案截止时间: {accept_resp.get('proposal_deadline')}")
        print(f"  📌 状态: {accept_resp.get('status')}")

        # === Step 7: seller 提交方案 ===
        print("\n[Step 7] seller 提交方案...")
        proposal_data = {
            "content": "契合点：1) 总价 420w 在客户预算 400-450w 范围内；2) 望京西园 3 室 1 厅 95.5 平米南北通透；3) 业主诚心出售，新房已购 3 个月，急售可议价。",
            "fit_points": "总价匹配 + 户型匹配 + 区域匹配",
            "viewing_suggestion": "建议周五晚 8 点或周六上午 10 点看房",
            "owner_situation": "业主自住，名下仅此一套，新房已购 3 个月，诚意出售，可议价 5%",
        }
        r = client.post(f"/v1/invitations/{inv_id}/proposal", json=proposal_data)
        proposal = assert_resp(r, 200, "Submit proposal")
        proposal_id = proposal["id"]

        # === Step 8: buyer 确认方案 → 握手 ===
        print("\n[Step 8] buyer 确认方案 → 握手...")
        r = client.post(f"/v1/invitations/{inv_id}/confirm")
        coop = assert_resp(r, 200, "Confirm & Handshake")
        coop_id = coop["id"]
        print(f"  🤝 合作 ID: COOP-{coop_id}")
        print(f"  📌 状态: {coop['status']}")
        print(f"  📝 备忘录长度: {len(coop['memo_content'])} 字符")

        # === Step 9: 验证所有数据落库 ===
        print("\n[Step 9] 验证数据落库...")
        with SessionLocal() as db:
            from sqlalchemy import select
            from app.models.cooperation import Cooperation
            from app.models.invitation import Invitation, InvitationStatus
            from app.models.proposal import Proposal
            from app.models.demand import Demand
            from app.models.property import Property

            # Property
            p = db.get(Property, prop_id)
            assert p and not p.deleted_at
            assert p.community == "望京西园"
            print(f"  ✅ Property: id={p.id}, community={p.community}, "
                  f"price=¥{p.total_price/10000:.0f}万")

            # Demand
            d = db.get(Demand, demand_id)
            assert d and not d.deleted_at
            assert d.buyer_id == buyer_id
            assert d.summary is not None
            print(f"  ✅ Demand: id={d.id}, district={d.district}, "
                  f"price=¥{d.price_min/10000:.0f}-{d.price_max/10000:.0f}万, "
                  f"summary={d.summary}")

            # Invitation
            i = db.get(Invitation, inv_id)
            assert i.status == InvitationStatus.HANDSHAKED
            assert i.responded_at is not None
            assert i.proposal_deadline is not None
            print(f"  ✅ Invitation: id={i.id}, status={i.status.value}, "
                  f"responded_at={i.responded_at.isoformat()[:19]}")

            # Proposal
            pr = db.get(Proposal, proposal_id)
            assert pr and pr.confirmed_at is not None
            assert "契合点" in pr.content
            print(f"  ✅ Proposal: id={pr.id}, confirmed_at={pr.confirmed_at.isoformat()[:19]}")

            # Cooperation
            c = db.get(Cooperation, coop_id)
            assert c.status.value == "handshaked"
            assert c.signed_at is not None
            assert "合作备忘录" in c.memo_content
            print(f"  ✅ Cooperation: id={c.id}, status={c.status.value}, "
                  f"signed_at={c.signed_at.isoformat()[:19]}")
            print(f"     备忘录预览（前 200 字）:")
            print(f"     {c.memo_content[:200]}...")

    print("\n" + "=" * 70)
    print("🎉 端到端测试全部通过！")
    print("=" * 70)
    print(f"\n数据汇总：")
    print(f"  User:       buyer_id={buyer_id}, seller_id={seller_id}")
    print(f"  Property:   id={prop_id} (¥{property_data['total_price']/10000:.0f}万)")
    print(f"  Demand:     id={demand_id} ({demand['summary']})")
    print(f"  Invitation: id={inv_id} → {inv['status']}")
    print(f"  Proposal:   id={proposal_id}")
    print(f"  Cooperation: id={coop_id} → {coop['status']}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
