"""dev 用户 seed 脚本（P1-0 修复）。

用法:
    cd backend && source .venv/bin/activate
    python -m scripts.seed_dev_users            # 幂等创建（推荐）
    python -m scripts.seed_dev_users --wipe     # 先清掉所有 mock user 再创建（危险：cascade 删 properties/demands/...）

效果:
    确保 6 个稳定 dev code 永远存在于 users 表里，让 dev 切换器有可预期的身份。
    - dev code 是稳定 label（永远不变）
    - user id 由 PostgreSQL SERIAL 序列决定（不可预测、依赖创建顺序）
    - 不修改 schema，不动 find_or_create_by_wechat
    - 详细文档见 docs/05-dev-users.md
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

# 让脚本能 import app.* 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.domains.auth.mock_names import generate_mock_name  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402


# ============================================================
#  6 个稳定 dev 用户定义
# ============================================================

@dataclass(frozen=True)
class DevUserSpec:
    """一个 dev code 的规格定义。"""

    code: str           # wechat code（登录用，label 永远不变）
    name: str           # 描述性名字（脚本日志用）
    role: str           # buyer / seller / both
    credit_score: float # 初始信用分（用于演示不同档位色）
    note: str           # 用途说明


DEV_USERS: list[DevUserSpec] = [
    DevUserSpec(
        code="dev_alice",
        name="Alice",
        role="buyer",
        credit_score=85.0,
        note="高信用买方代表（demo 推荐 Top 5 中高分种子）",
    ),
    DevUserSpec(
        code="dev_bob",
        name="Bob",
        role="seller",
        credit_score=88.0,
        note="高信用卖方（demo 接单/合作）",
    ),
    DevUserSpec(
        code="dev_carol",
        name="Carol",
        role="both",
        credit_score=82.0,
        note="双重身份（demo 复杂场景）",
    ),
    DevUserSpec(
        code="dev_dave",
        name="Dave",
        role="buyer",
        credit_score=55.0,
        note="低信用买方（demo 信用分差异）",
    ),
    DevUserSpec(
        code="dev_eve",
        name="Eve",
        role="seller",
        credit_score=92.0,
        note="高信用卖方（demo 接单优先）",
    ),
    DevUserSpec(
        code="dev_zach",
        name="Zach",
        role="buyer",
        credit_score=70.0,
        note="E2E 测试跑用户（被 e2e_test_v2.py 复用）",
    ),
]


# ============================================================
#  核心：幂等创建 / wipe
# ============================================================

def _make_unionid(code: str) -> str:
    """跟 auth/router.py mock branch 保持一致：mock_unionid_{code[:16]}。"""
    return f"mock_unionid_{code[:16]}"


def _make_openid(code: str) -> str:
    return f"mock_openid_{code[:16]}"


def ensure_dev_user(db, spec: DevUserSpec) -> tuple[User, bool]:
    """幂等创建单个 dev user。返回 (user, is_created)。"""
    unionid = _make_unionid(spec.code)
    openid = _make_openid(spec.code)

    existing = db.scalar(select(User).where(User.wechat_unionid == unionid))
    if existing:
        return existing, False

    # 稳定名（按 code hash 取名，幂等）
    name, display_name = generate_mock_name(spec.code)

    user = User(
        wechat_unionid=unionid,
        wechat_openid=openid,
        wechat_nickname=name,
        wechat_avatar_url=None,
        name=name,
        display_name=display_name,
        avatar_url=None,
        status=UserStatus.ACTIVE,
        is_verified=True,  # dev 身份默认通过认证，避免被推荐算法降权
        credit_score=spec.credit_score,
        rating_avg=spec.credit_score / 20.0,  # 80 -> 4.0 星
        rating_count=0,
        activity_count_30d=0,
        completed_count=0,
        last_login_at=None,
    )
    db.add(user)
    db.flush()
    return user, True


def wipe_all_mock_users(db) -> int:
    """删掉所有 wechat_unionid 形如 mock_% 或 wechat_openid 形如 mock_% 的用户。

    ⚠️ 会触发级联删除（properties / demands / invitations / proposals / cooperations / reviews）
    仅在 dev 环境用！生产前必须 verify APP_ENV=development。

    Returns: 删掉的 user 数
    """
    from app.core.config import settings
    if settings.app_env not in ("development", "test", None):
        print(f"  ⚠️  APP_ENV={settings.app_env!r}，拒绝 wipe（仅 dev/test 允许）")
        return 0

    # 显式依赖，避免循环
    from app.models.demand import Demand
    from app.models.invitation import Invitation
    from app.models.property import Property

    mock_users = db.scalars(
        select(User).where(
            (User.wechat_unionid.like("mock_%")) | (User.wechat_openid.like("mock_%"))
        )
    ).all()
    user_ids = [u.id for u in mock_users]
    if not user_ids:
        return 0

    # 显式 cascade：先删 child 再删 user（即便 DB 层有 ON DELETE CASCADE 也走一遍更稳）
    for model in (Demand, Invitation, Property):
        deleted = db.query(model).filter(
            model.buyer_id.in_(user_ids) | model.seller_id.in_(user_ids)
        ).delete(synchronize_session=False)
        if deleted:
            print(f"    cascade: {model.__tablename__} - {deleted}")

    # proposals / cooperations / reviews 通过 user_id 关联，需要单独查
    from app.models.cooperation import Cooperation, Review
    from app.models.proposal import Proposal
    for model in (Proposal, Cooperation, Review):
        # 这些表可能 FK 列名不一致，谨慎处理
        for col_name in ("buyer_id", "seller_id", "reviewer_id", "reviewee_id"):
            col = getattr(model, col_name, None)
            if col is None:
                continue
            deleted = db.query(model).filter(col.in_(user_ids)).delete(synchronize_session=False)
            if deleted:
                print(f"    cascade: {model.__tablename__}.{col_name} - {deleted}")

    # 最后删 user 本身
    db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()
    return len(user_ids)


# ============================================================
#  入口
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="HomeMatch dev users seed 脚本（P1-0）")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="先删掉所有 mock user 再 seed（⚠️ cascade 删 properties/demands/...）",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("HomeMatch dev users seed（P1-0）")
    print("=" * 70)

    with SessionLocal() as db:
        if args.wipe:
            print("\n[1/2] wipe 所有 mock user...")
            n = wipe_all_mock_users(db)
            print(f"  删掉 {n} 个 mock user")
        else:
            print(f"\n[1/2] 跳过 wipe（传 --wipe 才清）。")

        print(f"\n[2/2] seed {len(DEV_USERS)} 个 dev user...")
        results = []
        for spec in DEV_USERS:
            user, created = ensure_dev_user(db, spec)
            results.append((spec, user, created))
        db.commit()

        # 打印对照表
        print()
        print(f"{'code':<18} {'user_id':<8} {'name':<8} {'display':<8} {'role':<8} {'credit':<6} 状态")
        print("-" * 88)
        for spec, user, created in results:
            status = "✨ created" if created else "  exists"
            print(
                f"{spec.code:<18} #{user.id:<7} {user.name or '-':<8} {user.display_name or '-':<8} {spec.role:<8} {user.credit_score:<6.1f} {status}"
            )

        print()
        print("✅ seed 完成。dev 切换器可正常发现这些身份。")
        print("   查实际 user_id：curl http://localhost:8000/v1/users/dev-identities")
        if not args.wipe:
            print("   想要 clean start：./scripts/seed_dev_users.sh --wipe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
