"""标准化测试数据 seed 脚本。

用法:
    cd backend && source .venv/bin/activate
    python -m scripts.seed_test_data                # 幂等创建
    python -m scripts.seed_test_data --wipe         # 先清掉 test_* 数据再创建
    python -m scripts.seed_test_data --seed 42      # 固定随机种子（可复现）

生成:
    - 10 个用户 (test_user_01 ~ test_user_10)，双重身份（buyer + seller）
    - 100 条房源（每用户 10 条），分布在 9 个北京区
    - 60 条需求（每用户 6 条），覆盖各种价格段 + 户型
    - 故意制造一些状态混合（80% active / 15% inactive / 5% frozen 房源）
    - created_at 跨最近 60 天（让 credit_score 调度器有数据可算）

**不生成**：
- ❌ 邀请/合作/评价（用户自己手动测，避免污染 demo 流）
- ❌ 真实手机号（用 dev 专用 13x 段）
- ❌ 真实姓名（用百家姓生成）

**Idempotency**：
- 通过 wechat_unionid (mock_unionid_test_user_XX) 判重
- 重复运行同一 user / property / demand 不会重复创建
- 用 --wipe 强制重置
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 让脚本能 import app.* 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.crypto import encrypt_phone, hash_phone  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.domains.auth.mock_names import generate_mock_name  # noqa: E402
from app.models.demand import Demand, DemandStatus  # noqa: E402
from app.models.property import Property, PropertyStatus  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402

logger = get_logger(__name__)


# ============================================================
#  测试数据池（真实北京区域 + 常见社区/户型/标签）
# ============================================================

DISTRICTS = [
    "朝阳区", "海淀区", "丰台区", "西城区", "东城区",
    "石景山区", "通州区", "昌平区", "大兴区",
]

COMMUNITIES = [
    # 朝阳区
    "望京西园", "国贸CBD公寓", "三里屯SOHO", "双井富力城", "劲松九区",
    # 海淀区
    "中关村e世界", "五道口华清嘉园", "万柳书院", "西二旗领秀新硅谷", "知春路罗庄西里",
    # 丰台区
    "方庄芳古园", "西罗园", "草桥欣园", "玉泉营万年花城", "科技园诺德中心",
    # 西城区
    "金融街中海凯旋", "西单君太百货公寓", "宣武门富卓花园", "月坛南沙沟", "阜外百万庄",
    # 东城区
    "东直门海晟名苑", "工体北路新中西里", "王府井霞公府", "东四十条", "东四六条",
    # 石景山
    "八角北里", "鲁谷六合园", "金安桥", "苹果园小区",
    # 通州
    "梨园北街", "新华联家园", "万达华府", "北苑南里",
    # 昌平
    "回龙观龙泽苑", "天通苑北一区", "西三旗育新花园", "霍营紫金新干线",
    # 大兴
    "枣园尚城", "西红门兴海家园", "黄村兴丰大街", "亦庄林肯公园",
]

LAYOUTS = ["1室1厅", "2室1厅", "2室2厅", "3室1厅", "3室2厅", "4室2厅"]

TAGS_POOL = [
    "满五唯一", "近地铁", "南北通透", "精装修", "学区房",
    "随时看房", "新房", "改善型", "复式", "顶层", "底层",
    "带车位", "免增值税", "业主诚售",
]

VIEWING_TIMES = [
    "随时", "工作日晚上", "工作日白天", "周末", "工作日晚上+周末",
]

QUALIFICATIONS = ["首套", "二套", "不限"]


# ============================================================
#  10 个测试用户
# ============================================================

@dataclass(frozen=True)
class TestUserSpec:
    """一个测试用户的规格定义。"""

    code: str           # wechat code（test_user_01 ~ test_user_10）
    phone: str          # dev 专用手机号 13x 段（不同号码便于识别）
    role: str           # both（每个用户都是 buyer + seller）
    credit_score: float # 初始信用分（5 档：45-95）
    rating_avg: float   # 评价均分
    rating_count: int   # 评价数
    is_verified: bool


TEST_USERS: list[TestUserSpec] = [
    # code 段是 13900XX 形式（11 位）
    TestUserSpec("test_user_01", "13900000001", "both", 95.0, 4.8, 12, True),
    TestUserSpec("test_user_02", "13900000002", "both", 90.0, 4.5, 8, True),
    TestUserSpec("test_user_03", "13900000003", "both", 88.0, 4.4, 6, True),
    TestUserSpec("test_user_04", "13900000004", "both", 82.0, 4.1, 4, True),
    TestUserSpec("test_user_05", "13900000005", "both", 78.0, 3.9, 3, True),
    TestUserSpec("test_user_06", "13900000006", "both", 75.0, 3.7, 2, True),
    TestUserSpec("test_user_07", "13900000007", "both", 70.0, 3.5, 1, True),
    TestUserSpec("test_user_08", "13900000008", "both", 65.0, 3.2, 1, True),
    TestUserSpec("test_user_09", "13900000009", "both", 55.0, 2.7, 0, False),
    TestUserSpec("test_user_10", "13900000010", "both", 45.0, 2.2, 0, False),
]


# ============================================================
#  核心：幂等创建
# ============================================================

def _make_unionid(code: str) -> str:
    """跟 auth/router.py mock branch 保持一致。"""
    return f"mock_unionid_{code[:16]}"


def _make_openid(code: str) -> str:
    return f"mock_openid_{code[:16]}"


def ensure_test_user(db, spec: TestUserSpec, rng: random.Random) -> tuple[User, bool]:
    """幂等创建单个 test user。返回 (user, is_created)。"""
    unionid = _make_unionid(spec.code)
    openid = _make_openid(spec.code)

    existing = db.scalar(select(User).where(User.wechat_unionid == unionid))
    if existing:
        return existing, False

    # 稳定名（按 code hash 取名）
    name, display_name = generate_mock_name(spec.code)

    # created_at 在最近 90 天内随机
    days_ago = rng.randint(1, 90)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

    user = User(
        wechat_unionid=unionid,
        wechat_openid=openid,
        wechat_nickname=name,
        wechat_avatar_url=None,
        phone_encrypted=encrypt_phone(spec.phone),
        phone_hash=hash_phone(spec.phone),
        name=name,
        display_name=display_name,
        avatar_url=None,
        status=UserStatus.ACTIVE,
        is_verified=spec.is_verified,
        credit_score=spec.credit_score,
        rating_avg=spec.rating_avg,
        rating_count=spec.rating_count,
        activity_count_30d=rng.randint(0, 10),  # 0-10 活跃响应
        completed_count=spec.rating_count,
        credit_score_updated_at=datetime.now(timezone.utc),
        last_login_at=datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 72)),
        created_at=created_at,
    )
    db.add(user)
    db.flush()
    return user, True


def _make_property_for_user(
    user_id: int, idx: int, rng: random.Random
) -> Property:
    """为某用户创建一条 property。"""
    # 价格 1.5M - 15M
    total_price = rng.choice([
        rng.uniform(1_500_000, 3_000_000),  # 30% 小户型
        rng.uniform(3_000_000, 6_000_000),  # 40% 中等
        rng.uniform(6_000_000, 15_000_000), # 30% 大户型
    ])
    # 户型根据面积推
    area = rng.uniform(40, 250)
    if area < 60:
        layout = "1室1厅"
    elif area < 90:
        layout = rng.choice(["2室1厅", "2室2厅"])
    elif area < 130:
        layout = rng.choice(["3室1厅", "3室2厅"])
    else:
        layout = rng.choice(["4室2厅", "3室2厅"])

    # 状态分布：80% active / 15% inactive / 5% frozen
    r = rng.random()
    if r < 0.80:
        status = PropertyStatus.ACTIVE
    elif r < 0.95:
        status = PropertyStatus.INACTIVE
    else:
        status = PropertyStatus.FROZEN

    # 标签：随机 1-3 个
    num_tags = rng.randint(1, 3)
    tags = rng.sample(TAGS_POOL, k=min(num_tags, len(TAGS_POOL)))

    # created_at 在最近 60 天内
    days_ago = rng.randint(0, 60)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

    return Property(
        seller_id=user_id,
        community=rng.choice(COMMUNITIES),
        layout=layout,
        area=round(area, 1),
        total_price=round(total_price / 10000) * 10000,  # 圆整到万
        tags=tags,
        images=[f"https://placeholder.homematch.local/img/{user_id}-{idx}.jpg"],
        source_url=None,
        viewing_time=rng.choice(VIEWING_TIMES),
        is_verified=rng.random() < 0.7,  # 70% 已认证
        verified_at=datetime.now(timezone.utc) - timedelta(days=days_ago) if rng.random() < 0.7 else None,
        status=status,
        view_count=rng.randint(0, 100),
        invite_count=rng.randint(0, 5),
        last_active_at=datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 168)),
        created_at=created_at,
    )


def _make_demand_for_user(
    user_id: int, idx: int, rng: random.Random
) -> Demand:
    """为某用户创建一条 demand。"""
    # 价格段：150w - 1500w
    price_min = round(rng.uniform(150, 1500)) * 10000
    price_max = round(price_min / 10000 + rng.uniform(50, 800)) * 10000
    if price_max <= price_min:
        price_max = price_min + 100_0000

    # 户型：随机 1-2 个
    num_layouts = rng.randint(1, 2)
    layouts = rng.sample(LAYOUTS, k=num_layouts)

    # 状态：75% active / 15% matched / 10% closed
    r = rng.random()
    if r < 0.75:
        status = DemandStatus.ACTIVE
    elif r < 0.90:
        status = DemandStatus.MATCHED
    else:
        status = DemandStatus.CLOSED

    # 看房时间：随机 1-2 个
    num_view = rng.randint(1, 2)
    viewing_time = rng.sample(VIEWING_TIMES, k=min(num_view, len(VIEWING_TIMES)))

    # created_at 在最近 30 天内
    days_ago = rng.randint(0, 30)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

    district = rng.choice(DISTRICTS)
    # 摘要模板（脱敏展示用，跟 backend/app/domains/demands/router.py 的 _generate_summary 一致）
    layouts_str = "、".join(layouts)
    viewing_str = "、".join(viewing_time)
    qualification = rng.choice(QUALIFICATIONS)
    summary = (
        f"{district} | "
        f"{int(price_min/10000)}-{int(price_max/10000)}万 | "
        f"{layouts_str} | {qualification} | {viewing_str}"
    )

    return Demand(
        buyer_id=user_id,
        district=district,
        price_min=price_min,
        price_max=price_max,
        layouts=layouts,
        qualification=qualification,
        viewing_time=viewing_time,
        source_url=None,
        status=status,
        summary=summary,
        invite_count=rng.randint(0, 3),
        last_active_at=datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 72)),
        created_at=created_at,
    )


def ensure_test_properties(db, user_id: int, count: int, rng: random.Random) -> int:
    """为某用户幂等创建 N 条 property（按 seller_id 计数判重）。返回创建数。"""
    existing = db.scalar(
        select(Property).where(Property.seller_id == user_id).limit(1)
    )
    if existing is not None:
        return 0  # 已存在，跳过

    for i in range(count):
        db.add(_make_property_for_user(user_id, i + 1, rng))
    db.flush()
    return count


def ensure_test_demands(db, user_id: int, count: int, rng: random.Random) -> int:
    """为某用户幂等创建 N 条 demand。返回创建数。"""
    existing = db.scalar(
        select(Demand).where(Demand.buyer_id == user_id).limit(1)
    )
    if existing is not None:
        return 0

    for i in range(count):
        db.add(_make_demand_for_user(user_id, i + 1, rng))
    db.flush()
    return count


# ============================================================
#  入口
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="HomeMatch 标准化测试数据 seed")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="先删掉 test_user_* 的所有数据再 seed（⚠️ cascade 删 properties/demands）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="固定随机种子（保证多次运行数据一致）",
    )
    parser.add_argument(
        "--properties-per-user",
        type=int,
        default=10,
        help="每用户房源数（默认 10，10 用户 = 100 条）",
    )
    parser.add_argument(
        "--demands-per-user",
        type=int,
        default=6,
        help="每用户需求数（默认 6，10 用户 = 60 条）",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)

    print("=" * 70)
    print("HomeMatch 标准化测试数据 seed")
    print(f"  seed={args.seed} | properties/user={args.properties_per_user} | demands/user={args.demands_per_user}")
    print("=" * 70)

    with SessionLocal() as db:
        if args.wipe:
            print("\n[1/4] wipe test_user_* 相关数据...")
            from sqlalchemy import text as sql_text
            # 先删子表（properties/demands）+ invitations/cooperations/reviews/user
            # 用 wechat_unionid 判 user_id，再 cascade
            test_user_unionids = [f"mock_unionid_{spec.code[:16]}" for spec in TEST_USERS]
            test_user_ids = [
                u.id for u in db.scalars(
                    select(User.id).where(User.wechat_unionid.in_(test_user_unionids))
                ).all()
            ]
            if test_user_ids:
                # 用 user.id 找关联数据
                from app.models.invitation import Invitation
                from app.models.cooperation import Cooperation
                from app.models.review import Review
                for model in (Property, Demand, Invitation, Cooperation, Review):
                    deleted = 0
                    for col in ("seller_id", "buyer_id", "reviewer_id", "reviewee_id"):
                        c = getattr(model, col, None)
                        if c is None:
                            continue
                        d = db.query(model).filter(c.in_(test_user_ids)).delete(synchronize_session=False)
                        deleted += d
                    if deleted:
                        print(f"    cascade: {model.__tablename__} - {deleted}")
                db.query(User).filter(User.id.in_(test_user_ids)).delete(synchronize_session=False)
                db.commit()
                print(f"  删掉 {len(test_user_ids)} 个 test user + 关联数据")
        else:
            print(f"\n[1/4] 跳过 wipe（传 --wipe 才清）。")

        # 2. 创建 10 个用户
        print(f"\n[2/4] seed {len(TEST_USERS)} 个 test user...")
        users = []
        for spec in TEST_USERS:
            user, created = ensure_test_user(db, spec, rng)
            users.append((user, spec, created))
        db.commit()
        for user, spec, created in users:
            status = "✨ created" if created else "  exists"
            print(
                f"  {spec.code:<14} #{user.id:<4} {user.name:<6} {user.display_name:<8} "
                f"credit={user.credit_score:5.1f} verified={user.is_verified} {status}"
            )

        # 3. 创建 100 条房源
        print(f"\n[3/4] seed {len(users) * args.properties_per_user} 条 property（每用户 {args.properties_per_user}）...")
        total_created = 0
        for user, _, _ in users:
            n = ensure_test_properties(db, user.id, args.properties_per_user, rng)
            total_created += n
        db.commit()
        if total_created == 0:
            print("  已存在（幂等跳过）")
        else:
            print(f"  创建 {total_created} 条 property")

        # 4. 创建 60 条需求
        print(f"\n[4/4] seed {len(users) * args.demands_per_user} 条 demand（每用户 {args.demands_per_user}）...")
        total_created = 0
        for user, _, _ in users:
            n = ensure_test_demands(db, user.id, args.demands_per_user, rng)
            total_created += n
        db.commit()
        if total_created == 0:
            print("  已存在（幂等跳过）")
        else:
            print(f"  创建 {total_created} 条 demand")

        # 汇总
        from sqlalchemy import func as sql_func
        from app.models.property import Property
        from app.models.demand import Demand
        user_count = db.scalar(sql_func.count(User.id)) or 0
        prop_count = db.scalar(sql_func.count(Property.id)) or 0
        dem_count = db.scalar(sql_func.count(Demand.id)) or 0
        print()
        print("=" * 70)
        print(f"📊 当前 DB 总数: user={user_count} | property={prop_count} | demand={dem_count}")
        print("=" * 70)
        print("✅ seed 完成。")
        print("   验证:  psql -U homa -d homa -c 'SELECT count(*) FROM users;'")
        print("   重置:  ./scripts/seed_test_data.sh --wipe")
        print("   复现:  ./scripts/seed_test_data.sh --seed 42")
    return 0


if __name__ == "__main__":
    sys.exit(main())
