"""Demo 数据 seed 脚本（5 经纪人 + 50 房源 + 50 需求 + 50 合作）。

用法:
    cd backend && source .venv/bin/activate
    python -m scripts.seed_demo_data                # 幂等创建
    python -m scripts.seed_demo_data --wipe         # 先清 demo_* 数据再创建
    python -m scripts.seed_demo_data --seed 42      # 固定随机种子

生成:
- 5 个 demo 经纪人（demo_agent_01 ~ 05），不同 credit_score
- 50 条房源（每经纪人 10 条作为卖方）
- 50 条需求（每经纪人 10 条作为买方）
- 50 条合作（每经纪人 10 条作为买方，卖方从其他 4 经纪人中循环选）

与 [seed_test_data.py](seed_test_data.py) 区别：
- seed_test_data.py 是 10 user × 10 property × 6 demand（**不**生成合作）
- seed_demo_data.py 是 5 agent × 10 property × 10 demand × 10 cooperation
- demo 前缀独立，互不影响；可以共存

**Idempotency**：
- 通过 wechat_unionid (mock_unionid_demo_agent_XX) 判 user 重
- 同一 user 的 property/demand 计数判重
- cooperation 每次重数（避免重复 invitation_id）
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.crypto import encrypt_phone, hash_phone  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.logging import get_logger  # noqa: E402
from app.domains.auth.mock_names import generate_mock_name  # noqa: E402
from app.models.cooperation import Cooperation, CooperationStatus  # noqa: E402
from app.models.demand import Demand, DemandStatus  # noqa: E402
from app.models.invitation import Invitation, InvitationStatus  # noqa: E402
from app.models.property import Property, PropertyStatus  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402

logger = get_logger(__name__)

# ============================================================
#  数据池（复用 seed_test_data 同款字段池）
# ============================================================

DISTRICTS = [
    "朝阳区", "海淀区", "丰台区", "西城区", "东城区",
    "石景山区", "通州区", "昌平区", "大兴区",
]

COMMUNITIES = [
    "望京西园", "国贸CBD公寓", "三里屯SOHO", "双井富力城", "劲松九区",
    "中关村e世界", "五道口华清嘉园", "万柳书院", "西二旗领秀新硅谷", "知春路罗庄西里",
    "方庄芳古园", "西罗园", "草桥欣园", "玉泉营万年花城", "科技园诺德中心",
    "金融街中海凯旋", "西单君太百货公寓", "宣武门富卓花园", "月坛南沙沟", "阜外百万庄",
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

# 合作 memo 模板（真实业务可能的内容）
COOP_MEMOS = [
    "客户对 3 室 2 厅户型有明确需求，预算充足，业主配合度高",
    "学区需求强烈，目标小区为望京西园和国贸CBD公寓二选一",
    "客户首付 50% 资金已到位，看房时间灵活可约",
    "业主急售，已购新房 3 个月，倾向 30 天内成交",
    "客户为改善型需求，对物业品质和社区环境有要求",
    "双方价格预期差距 < 5%，谈判空间大",
    "客户有公积金贷款需求，需协助对接银行",
    "业主全权委托，配合签字和过户流程",
    "客户工作日晚上和周末可看房，业主配合度待确认",
    "学区+改善双重需求，户型优先 3 室及以上",
]


# ============================================================
#  5 个 demo 经纪人
# ============================================================

@dataclass(frozen=True)
class DemoAgentSpec:
    code: str
    phone: str
    credit_score: float
    rating_avg: float
    rating_count: int
    is_verified: bool


DEMO_AGENTS: list[DemoAgentSpec] = [
    # 5 个不同档位信用分，覆盖高中低
    DemoAgentSpec("demo_agent_01", "13811110001", 95.0, 4.8, 25, True),
    DemoAgentSpec("demo_agent_02", "13811110002", 88.0, 4.4, 18, True),
    DemoAgentSpec("demo_agent_03", "13811110003", 80.0, 4.0, 12, True),
    DemoAgentSpec("demo_agent_04", "13811110004", 72.0, 3.6,  6, True),
    DemoAgentSpec("demo_agent_05", "13811110005", 60.0, 3.0,  3, False),
]


# ============================================================
#  Helpers
# ============================================================

def _make_unionid(code: str) -> str:
    return f"mock_unionid_{code[:16]}"


def _make_openid(code: str) -> str:
    return f"mock_openid_{code[:16]}"


def ensure_demo_agent(db, spec: DemoAgentSpec, rng: random.Random) -> tuple[User, bool]:
    """幂等创建单个 demo agent。"""
    unionid = _make_unionid(spec.code)
    existing = db.scalar(select(User).where(User.wechat_unionid == unionid))
    if existing:
        return existing, False

    name, display_name = generate_mock_name(spec.code)

    # created_at 跨 60-180 天（让 demo 数据有"老用户"质感）
    days_ago = rng.randint(60, 180)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

    user = User(
        wechat_unionid=unionid,
        wechat_openid=_make_openid(spec.code),
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
        activity_count_30d=rng.randint(3, 12),
        completed_count=spec.rating_count,
        credit_score_updated_at=datetime.now(timezone.utc),
        last_login_at=datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 24)),
        created_at=created_at,
    )
    db.add(user)
    db.flush()
    return user, True


def _make_property_for_agent(
    user_id: int, idx: int, rng: random.Random
) -> Property:
    """为某 demo agent 生成一条 property。"""
    total_price = rng.choice([
        rng.uniform(1_500_000, 3_000_000),
        rng.uniform(3_000_000, 6_000_000),
        rng.uniform(6_000_000, 15_000_000),
    ])
    area = rng.uniform(40, 250)
    if area < 60:
        layout = "1室1厅"
    elif area < 90:
        layout = rng.choice(["2室1厅", "2室2厅"])
    elif area < 130:
        layout = rng.choice(["3室1厅", "3室2厅"])
    else:
        layout = rng.choice(["4室2厅", "3室2厅"])

    # demo 数据 90% active / 10% inactive（比 test 数据更健康）
    r = rng.random()
    if r < 0.90:
        status = PropertyStatus.ACTIVE
    else:
        status = PropertyStatus.INACTIVE

    num_tags = rng.randint(1, 3)
    tags = rng.sample(TAGS_POOL, k=min(num_tags, len(TAGS_POOL)))

    days_ago = rng.randint(0, 45)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

    return Property(
        seller_id=user_id,
        community=rng.choice(COMMUNITIES),
        layout=layout,
        area=round(area, 1),
        total_price=round(total_price / 10000) * 10000,
        tags=tags,
        images=[],  # demo 不放图（避免占存储）
        source_url=None,
        viewing_time=rng.choice(VIEWING_TIMES),
        is_verified=rng.random() < 0.85,
        verified_at=datetime.now(timezone.utc) - timedelta(days=days_ago) if rng.random() < 0.85 else None,
        status=status,
        view_count=rng.randint(0, 200),
        invite_count=rng.randint(0, 8),
        last_active_at=datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 168)),
        created_at=created_at,
    )


def _make_demand_for_agent(
    user_id: int, idx: int, rng: random.Random
) -> Demand:
    """为某 demo agent 生成一条 demand。"""
    price_min = round(rng.uniform(150, 1500)) * 10000
    price_max = round(price_min / 10000 + rng.uniform(50, 800)) * 10000
    if price_max <= price_min:
        price_max = price_min + 100_0000

    num_layouts = rng.randint(1, 2)
    layouts = rng.sample(LAYOUTS, k=num_layouts)

    # demo: 70% active / 20% matched / 10% closed
    r = rng.random()
    if r < 0.70:
        status = DemandStatus.ACTIVE
    elif r < 0.90:
        status = DemandStatus.MATCHED
    else:
        status = DemandStatus.CLOSED

    num_view = rng.randint(1, 2)
    viewing_time = rng.sample(VIEWING_TIMES, k=min(num_view, len(VIEWING_TIMES)))

    days_ago = rng.randint(0, 30)
    created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)

    district = rng.choice(DISTRICTS)
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


def _make_cooperation(
    buyer_id: int,
    seller_id: int,
    invitation_id: int,
    rng: random.Random,
) -> Cooperation:
    """生成一条合作（cooperation）。

    status 分布：40% HANDSHAKED / 30% IN_PROGRESS / 25% COMPLETED / 5% TERMINATED
    """
    r = rng.random()
    if r < 0.40:
        status = CooperationStatus.HANDSHAKED
    elif r < 0.70:
        status = CooperationStatus.IN_PROGRESS
    elif r < 0.95:
        status = CooperationStatus.COMPLETED
    else:
        status = CooperationStatus.TERMINATED

    days_ago = rng.randint(1, 30)
    signed_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    closed_at = None
    if status in (CooperationStatus.COMPLETED, CooperationStatus.TERMINATED):
        closed_at = signed_at + timedelta(days=rng.randint(7, 30))

    # COMPLETED 默认双方都评了；其他状态通常 0-1 个评
    if status == CooperationStatus.COMPLETED:
        buyer_reviewed = rng.random() < 0.7
        seller_reviewed = rng.random() < 0.7
    elif status == CooperationStatus.TERMINATED:
        buyer_reviewed = False
        seller_reviewed = False
    else:
        buyer_reviewed = rng.random() < 0.2
        seller_reviewed = rng.random() < 0.2

    return Cooperation(
        invitation_id=invitation_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        status=status,
        memo_content=rng.choice(COOP_MEMOS),
        signed_at=signed_at,
        closed_at=closed_at,
        close_reason="双方协商终止" if status == CooperationStatus.TERMINATED else None,
        buyer_reviewed=buyer_reviewed,
        seller_reviewed=seller_reviewed,
    )


# ============================================================
#  幂等创建（按 agent 计数）
# ============================================================

def ensure_demo_properties(db, user_id: int, count: int, rng: random.Random) -> int:
    """幂等：已存在任何 property 就跳过。"""
    existing = db.scalar(
        select(Property).where(Property.seller_id == user_id).limit(1)
    )
    if existing is not None:
        return 0
    for i in range(count):
        db.add(_make_property_for_agent(user_id, i + 1, rng))
    db.flush()
    return count


def ensure_demo_demands(db, user_id: int, count: int, rng: random.Random) -> int:
    existing = db.scalar(
        select(Demand).where(Demand.buyer_id == user_id).limit(1)
    )
    if existing is not None:
        return 0
    for i in range(count):
        db.add(_make_demand_for_agent(user_id, i + 1, rng))
    db.flush()
    return count


def ensure_demo_cooperations(
    db,
    agents: list[User],
    per_agent: int,
    rng: random.Random,
) -> int:
    """为每个 agent 作为买方建 per_agent 条合作。

    **分布策略**：50 合作 = 5 agents × 10 合作每 agent (as buyer)。
    卖方从其他 4 agent 中 round-robin 选择 → 每个 agent 也大致
    接到 10 次作为卖方（5×10/4 ≈ 12.5 的均分）。

    **FK 约束**：cooperation.invitation_id → invitations.id。
    所以先建 stub invitations（HANDSHAKED 状态 + 24h 前过期），
    再建 cooperations 引用它们。

    **幂等**：已存在任何 cooperation 就跳过（防止重复 invitation_id）。
    """
    existing = db.scalar(select(Cooperation).limit(1))
    if existing is not None:
        return 0

    # 取每个 buyer 的一个真实 demand（合作必关联一个 demand）
    buyer_demands: dict[int, int] = {}
    for buyer in agents:
        demand = db.scalar(
            select(Demand).where(Demand.buyer_id == buyer.id).limit(1)
        )
        if demand is None:
            print(f"  ⚠️ {buyer.name} 没有 demand，跳过建合作")
            continue
        buyer_demands[buyer.id] = demand.id

    # 先建 stub invitations（用负数 ID 避冲突：-10000 起）
    base_inv_id = -10000
    invitations = []
    n = 0
    for i, buyer in enumerate(agents):
        if buyer.id not in buyer_demands:
            continue
        for j in range(per_agent):
            sellers = [a for a in agents if a.id != buyer.id]
            seller = sellers[(i * per_agent + j) % len(sellers)]
            inv = Invitation(
                id=base_inv_id + n,
                demand_id=buyer_demands[buyer.id],
                buyer_id=buyer.id,
                seller_id=seller.id,
                status=InvitationStatus.HANDSHAKED,
                expired_at=datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 30)),
                responded_at=datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 30)),
                proposal_deadline=None,
                reject_reason=None,
                note="demo seed",
            )
            db.add(inv)
            invitations.append(inv)
            n += 1
    db.flush()

    # 再建 cooperations
    for inv in invitations:
        coop = _make_cooperation(
            buyer_id=inv.buyer_id,
            seller_id=inv.seller_id,
            invitation_id=inv.id,
            rng=rng,
        )
        db.add(coop)
    db.flush()
    return n


# ============================================================
#  入口
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="HomeMatch demo 数据 seed (5 agents)")
    parser.add_argument(
        "--wipe", action="store_true",
        help="先清 demo_* 数据再 seed（cascade 删 properties/demands/cooperations）",
    )
    parser.add_argument("--seed", type=int, default=None, help="固定随机种子")
    parser.add_argument("--properties-per-agent", type=int, default=10, help="每经纪人房源数")
    parser.add_argument("--demands-per-agent", type=int, default=10, help="每经纪人需求数")
    parser.add_argument("--cooperations-per-agent", type=int, default=10, help="每经纪人合作数（作为买方）")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    print("=" * 70)
    print("HomeMatch demo 数据 seed（5 经纪人）")
    print(
        f"  seed={args.seed} | properties/agent={args.properties_per_agent} | "
        f"demands/agent={args.demands_per_agent} | coops/agent={args.cooperations_per_agent}"
    )
    print("=" * 70)

    with SessionLocal() as db:
        # 1. Wipe
        if args.wipe:
            print("\n[1/5] wipe demo_* 数据...")
            demo_unionids = [f"mock_unionid_{spec.code[:16]}" for spec in DEMO_AGENTS]
            demo_user_ids = list(
                db.scalars(
                    select(User.id).where(User.wechat_unionid.in_(demo_unionids))
                ).all()
            )
            if demo_user_ids:
                # 删子表
                for model in (Property, Demand, Invitation, Cooperation, Review):
                    deleted = 0
                    for col in ("seller_id", "buyer_id", "reviewer_id", "reviewee_id"):
                        c = getattr(model, col, None)
                        if c is None:
                            continue
                        d = db.query(model).filter(c.in_(demo_user_ids)).delete(synchronize_session=False)
                        deleted += d
                    if deleted:
                        print(f"    cascade: {model.__tablename__} - {deleted}")
                db.query(User).filter(User.id.in_(demo_user_ids)).delete(synchronize_session=False)
                db.commit()
                print(f"  删掉 {len(demo_user_ids)} 个 demo agent + 关联数据")
        else:
            print("\n[1/5] 跳过 wipe（传 --wipe 才清）。")

        # 2. 创建 5 个经纪人
        print(f"\n[2/5] seed {len(DEMO_AGENTS)} 个 demo agent...")
        agents = []
        for spec in DEMO_AGENTS:
            user, created = ensure_demo_agent(db, spec, rng)
            agents.append(user)
        db.commit()
        for user, spec in zip(agents, DEMO_AGENTS):
            print(
                f"  {spec.code:<16} #{user.id:<4} {user.name:<6} {user.display_name:<8} "
                f"credit={user.credit_score:5.1f} verified={user.is_verified}"
            )

        # 3. 创建房源
        total_props = len(agents) * args.properties_per_agent
        print(f"\n[3/5] seed {total_props} 条 property（每 agent {args.properties_per_agent}）...")
        n_created = 0
        for agent in agents:
            n_created += ensure_demo_properties(db, agent.id, args.properties_per_agent, rng)
        db.commit()
        print(f"  创建 {n_created} 条 property（{total_props - n_created} 已存在）")

        # 4. 创建需求
        total_demands = len(agents) * args.demands_per_agent
        print(f"\n[4/5] seed {total_demands} 条 demand（每 agent {args.demands_per_agent}）...")
        n_created = 0
        for agent in agents:
            n_created += ensure_demo_demands(db, agent.id, args.demands_per_agent, rng)
        db.commit()
        print(f"  创建 {n_created} 条 demand（{total_demands - n_created} 已存在）")

        # 5. 创建合作
        total_coops = len(agents) * args.cooperations_per_agent
        print(f"\n[5/5] seed {total_coops} 条 cooperation（每 agent {args.cooperations_per_agent} as buyer）...")
        n_created = ensure_demo_cooperations(db, agents, args.cooperations_per_agent, rng)
        db.commit()
        print(f"  创建 {n_created} 条 cooperation（{total_coops - n_created} 已存在）")

        # 6. 实际分布统计
        print("\n" + "=" * 70)
        print("📊 实际分布：")
        for agent in agents:
            with_buyer = db.scalar(
                select(__import__('sqlalchemy').func.count(Cooperation.id))
                .where(Cooperation.buyer_id == agent.id)
            )
            with_seller = db.scalar(
                select(__import__('sqlalchemy').func.count(Cooperation.id))
                .where(Cooperation.seller_id == agent.id)
            )
            print(
                f"  {agent.name:<6} (#{agent.id}): buyer={with_buyer:>2}  seller={with_seller:>2}  "
                f"total={with_buyer + with_seller:>2}"
            )

        print("=" * 70)
        print("✅ demo 数据 seed 完成")
        return 0


if __name__ == "__main__":
    sys.exit(main())
