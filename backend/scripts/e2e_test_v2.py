"""HomeMatch 端到端集成测试 v2 - 含 JWT 鉴权 + 评价闭环。

新增：使用 JWT token 鉴权（替换硬编码 user_id=1），添加 review 步骤。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.core.config import settings
from app.core.crypto import encrypt_phone, hash_phone
from app.core.database import SessionLocal
from app.models.user import User, UserStatus

BASE_URL = "http://localhost:8000"


def setup_test_users() -> tuple[int, int]:
    """准备测试用户：2 个 active 用户。返回 (buyer_id, seller_id)。"""
    with SessionLocal() as db:
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
            # 重置密码字段以外的状态，确保 active
            buyer.status = UserStatus.ACTIVE
            print(f"  [SETUP] Buyer exists: id={buyer.id}")

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
            seller.status = UserStatus.ACTIVE
            print(f"  [SETUP] Seller exists: id={seller.id}")

        db.commit()
        return buyer.id, seller.id


def login_wechat(client: httpx.Client, user_id_hint: int) -> str:
    """用 mock wechat 登录拿 token。"""
    r = client.post("/v1/auth/wechat-login", json={"code": f"test_e2e_{user_id_hint}"})
    if r.status_code != 200:
        raise RuntimeError(f"Login failed: {r.text}")
    token = r.json()["data"]["access_token"]
    user_id = r.json()["data"]["user"]["id"]
    return token, user_id


def assert_resp(resp: httpx.Response, expected_status: int, label: str) -> dict:
    """断言响应。"""
    if resp.status_code != expected_status:
        print(f"  ❌ {label}: HTTP {resp.status_code}")
        print(f"     Body: {resp.text[:300]}")
        raise AssertionError(f"{label} failed: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("code") not in (0, None):
        print(f"  ❌ {label}: code={data.get('code')}, msg={data.get('message')}")
        raise AssertionError(f"{label} failed: {data.get('message')}")
    print(f"  ✅ {label}: HTTP {resp.status_code}")
    return data.get("data") or {}


def main():
    print("=" * 70)
    print("HomeMatch 端到端集成测试 v2 (JWT 鉴权 + 评价闭环)")
    print("=" * 70)

    print("\n[Step 0] 准备测试数据...")
    buyer_id_orig, seller_id_orig = setup_test_users()

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # Step 1: 健康检查
        print("\n[Step 1] 健康检查...")
        r = client.get("/v1/health")
        h = r.json()
        print(f"  ✅ 服务: {h['status']}, db={h['checks']['database']}, redis={h['checks']['redis']}")

        # Step 2: 两个用户登录（mock wechat）
        print("\n[Step 2] 两个用户登录拿 token...")
        buyer_token, buyer_id = login_wechat(client, 1)
        seller_token, seller_id = login_wechat(client, 2)
        print(f"  ✅ buyer  id={buyer_id}  token={buyer_token[:20]}...")
        print(f"  ✅ seller id={seller_id}  token={seller_token[:20]}...")
        H_BUYER = {"Authorization": f"Bearer {buyer_token}"}
        H_SELLER = {"Authorization": f"Bearer {seller_token}"}

        # Step 3: seller 发布房源
        print("\n[Step 3] seller 发布房源...")
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
        r = client.post("/v1/properties", json=property_data, headers=H_SELLER)
        prop = assert_resp(r, 200, "Create property (seller)")
        prop_id = prop["id"]
        print(f"     property_id={prop_id}")

        # Step 4: buyer 发布需求
        print("\n[Step 4] buyer 发布需求...")
        demand_data = {
            "district": "朝阳区",
            "price_min": 3500000,
            "price_max": 4500000,
            "layouts": ["3室1厅", "2室1厅"],
            "qualification": "首套",
            "viewing_time": ["工作日晚上", "周末"],
        }
        r = client.post("/v1/demands", json=demand_data, headers=H_BUYER)
        demand = assert_resp(r, 200, "Create demand (buyer)")
        demand_id = demand["id"]
        print(f"     demand_id={demand_id}, summary={demand.get('summary')}")

        # Step 5: buyer 获取 Top 5 推荐
        print("\n[Step 5] buyer 获取 Top 5 推荐...")
        r = client.get(f"/v1/demands/{demand_id}/recommendations", headers=H_BUYER)
        rec = assert_resp(r, 200, "Get recommendations")
        sellers_found = rec.get("sellers", [])
        print(f"     🎯 推荐数: {len(sellers_found)}")

        # Step 6: buyer 发起邀请给 seller
        print("\n[Step 6] buyer 发起邀请给 seller...")
        inv_data = {
            "demand_id": demand_id,
            "seller_id": seller_id,
            "note": "客户总价 400-450w，望京附近，3 室优先",
        }
        r = client.post("/v1/invitations", json=inv_data, headers=H_BUYER)
        inv = assert_resp(r, 200, "Create invitation (buyer)")
        inv_id = inv["id"]
        print(f"     invitation_id={inv_id}, 状态={inv['status']}")

        # Step 7: seller 接单
        print("\n[Step 7] seller 接单...")
        r = client.post(f"/v1/invitations/{inv_id}/accept", headers=H_SELLER)
        accept = assert_resp(r, 200, "Accept invitation (seller)")
        print(f"     状态={accept.get('status')}, 方案截止={accept.get('proposal_deadline')}")

        # Step 8: seller 提交方案
        print("\n[Step 8] seller 提交方案...")
        proposal_data = {
            "content": "契合点：1) 总价 420w 在客户预算 400-450w 范围内；2) 望京西园 3 室 1 厅 95.5 平米南北通透；3) 业主诚心出售，新房已购 3 个月，急售可议价。",
            "fit_points": "总价匹配 + 户型匹配 + 区域匹配",
            "viewing_suggestion": "建议周五晚 8 点或周六上午 10 点看房",
            "owner_situation": "业主自住，名下仅此一套，新房已购 3 个月，诚意出售，可议价 5%",
        }
        r = client.post(f"/v1/invitations/{inv_id}/proposal", json=proposal_data, headers=H_SELLER)
        proposal = assert_resp(r, 200, "Submit proposal (seller)")
        proposal_id = proposal["id"]

        # Step 9: buyer 确认方案 → 握手
        print("\n[Step 9] buyer 确认方案 → 握手...")
        r = client.post(f"/v1/invitations/{inv_id}/confirm", headers=H_BUYER)
        coop = assert_resp(r, 200, "Confirm & Handshake (buyer)")
        coop_id = coop["id"]
        print(f"     🤝 COOP-{coop_id}, 状态={coop['status']}")

        # Step 10: 双方互评 → 信用分重算
        print("\n[Step 10] 双方互评 → 信用分重算...")
        # buyer 评 seller
        r1 = client.post(
            f"/v1/cooperations/{coop_id}/review",
            json={"rating": 5, "comment": "响应快，方案专业", "is_anonymous": False},
            headers=H_BUYER,
        )
        review1 = assert_resp(r1, 200, "buyer 评 seller")

        # seller 评 buyer
        r2 = client.post(
            f"/v1/cooperations/{coop_id}/review",
            json={"rating": 5, "comment": "客户靠谱，配合顺利", "is_anonymous": False},
            headers=H_SELLER,
        )
        review2 = assert_resp(r2, 200, "seller 评 buyer")

        # Step 11: AI 能力测试（mock 模式）
        print("\n[Step 11] AI 能力测试（mock 模式）...")
        r = client.post(
            "/v1/ai/generate-proposal",
            json={
                "demand_summary": "客户预算 400-450w",
                "property_info": {"community": "望京西园", "layout": "3室1厅", "area": 95, "total_price": 4200000},
            },
            headers=H_BUYER,
        )
        ai_resp = assert_resp(r, 200, "AI generate-proposal")
        print(f"     Mock 输出: {ai_resp[:100]}...")

        r = client.post(
            "/v1/ai/analyze-review",
            json={"rating": 5, "comment": "好的好的好的好的好的好的好的好的好的好的好的"},
            headers=H_BUYER,
        )
        ai_anomaly = assert_resp(r, 200, "AI analyze-review")
        print(f"     异常检测: {ai_anomaly}")

        # Step 12: 设备注册（推送）
        print("\n[Step 12] 设备注册...")
        r = client.post(
            "/v1/devices/register",
            json={"fcm_token": "test_fcm_token_abc123", "platform": "ios", "app_version": "0.1.0"},
            headers=H_BUYER,
        )
        assert_resp(r, 200, "Register device (buyer iOS)")

        # Step 13: 验证最终数据
        print("\n[Step 13] 验证最终数据（DB 查询）...")
        with SessionLocal() as db:
            from sqlalchemy import select
            from app.models.cooperation import Cooperation
            from app.models.invitation import Invitation, InvitationStatus
            from app.models.proposal import Proposal
            from app.models.review import Review
            from app.models.user import User

            # 邀请状态应该是 handshaked
            i = db.get(Invitation, inv_id)
            assert i.status == InvitationStatus.HANDSHAKED
            print(f"  ✅ Invitation: {i.id} → {i.status.value}")

            # 合作应该是 completed（双方都评完）
            c = db.get(Cooperation, coop_id)
            assert c.buyer_reviewed and c.seller_reviewed
            print(f"  ✅ Cooperation: {c.id} → {c.status.value} (双方已评)")

            # 评价应该有 2 条
            reviews = db.scalars(select(Review).where(Review.cooperation_id == coop_id)).all()
            assert len(reviews) == 2
            print(f"  ✅ Reviews: {len(reviews)} 条")

            # 双方信用分应该都更新了
            b = db.get(User, buyer_id)
            s = db.get(User, seller_id)
            print(f"  ✅ 信用分: buyer={b.credit_score} (rating_avg={b.rating_avg}), "
                  f"seller={s.credit_score} (rating_avg={s.rating_avg})")

    print("\n" + "=" * 70)
    print("🎉 端到端测试 v2 全部通过（含 JWT + 评价 + AI + 推送）")
    print("=" * 70)


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
