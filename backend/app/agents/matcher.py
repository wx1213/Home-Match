"""匹配器 - 给定需求，返回 Top 5 卖方。

MVP 阶段：基于规则打分（区域 + 价格 + 户型 + 信用分 + 活跃度）。
二期：可加 LLM 解释/增强。

匹配流程：
1. 候选卖方：所有 status=active 且有 active 房源的卖方
2. 过滤：排除需求方本人
3. 过滤：排除已发过邀请的卖方（本轮淘汰）
4. 打分：每个卖方按多维加权
5. 排序：取 Top 5
6. 缓存：5min（避免重复计算）
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.redis_client import recommendation_cache_key, redis_client
from app.models.demand import Demand
from app.models.invitation import Invitation, InvitationStatus
from app.models.property import Property, PropertyStatus
from app.models.user import User, UserStatus

logger = get_logger(__name__)

CACHE_TTL = 300  # 5 分钟


def compute_match_score(demand: Demand, seller: User, properties: list[Property]) -> float:
    """计算单个卖方与需求的匹配分（0-1）。"""
    if not properties:
        return 0.0

    # === 维度 1：价格匹配度（40%） ===
    price_scores = []
    for p in properties:
        if p.total_price < demand.price_min * 0.8 or p.total_price > demand.price_max * 1.2:
            # 价格偏离太多
            continue
        # 在区间内越居中分越高
        center = (demand.price_min + demand.price_max) / 2
        spread = (demand.price_max - demand.price_min) / 2 or 1
        distance = abs(p.total_price - center) / spread
        price_scores.append(max(0, 1 - distance))
    price_score = max(price_scores) if price_scores else 0.0

    # === 维度 2：户型匹配（20%） ===
    layout_match = 0.0
    if demand.layouts:
        demand_layouts = set(demand.layouts)
        for p in properties:
            if p.layout in demand_layouts:
                layout_match = 1.0
                break
    else:
        layout_match = 1.0  # 无要求 = 全匹配

    # === 维度 3：信用分（25%） ===
    credit_score = (seller.credit_score or 60) / 100.0

    # === 维度 4：活跃度（15%） ===
    activity_score = min(1.0, (seller.activity_count_30d or 0) / 10.0)

    # === 加权 ===
    total = (
        price_score * 0.40
        + layout_match * 0.20
        + credit_score * 0.25
        + activity_score * 0.15
    )
    return round(total, 3)


def find_top_sellers(
    db: Session,
    demand: Demand,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """找 Top N 卖方。

    Returns:
        [{"rank": 1, "match_score": 0.92, "seller": {...}, "properties": [...]}, ...]
    """
    # 1. 查缓存
    cache_key = recommendation_cache_key(demand.id)
    cached = redis_client.get(cache_key)
    if cached:
        import json
        try:
            return json.loads(cached)
        except Exception:
            pass

    # 2. 候选卖方：所有 active 用户（除买方本人）
    candidates = db.scalars(
        select(User).where(
            User.id != demand.buyer_id,
            User.status == UserStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
    ).all()

    if not candidates:
        return []

    # 3. 过滤：排除本轮已发过邀请的卖方
    invited_seller_ids = set(
        db.scalars(
            select(Invitation.seller_id).where(
                Invitation.demand_id == demand.id,
                Invitation.status.in_([
                    InvitationStatus.PENDING.value,
                    InvitationStatus.ACCEPTED.value,
                    InvitationStatus.PROPOSAL_REVIEW.value,
                    InvitationStatus.HANDSHAKED.value,
                ]),
            )
        ).all()
    )

    # 4. 每个候选卖方：取其 active 房源，按需计算匹配分
    results = []
    for seller in candidates:
        if seller.id in invited_seller_ids:
            continue
        properties = db.scalars(
            select(Property).where(
                Property.seller_id == seller.id,
                Property.status == PropertyStatus.ACTIVE,
                Property.deleted_at.is_(None),
            ).limit(5)
        ).all()
        if not properties:
            continue
        score = compute_match_score(demand, seller, list(properties))
        if score > 0:
            results.append({
                "seller": seller,
                "properties": list(properties),
                "score": score,
            })

    # 5. 排序 + 取 Top N
    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:top_n]

    # 6. 格式化输出
    output = []
    for i, item in enumerate(top, 1):
        seller = item["seller"]
        output.append({
            "rank": i,
            "match_score": item["score"],
            "seller": {
                "id": seller.id,
                "display_name": seller.display_name or f"用户{seller.id}",
                "avatar_url": seller.avatar_url,
                "credit_score": seller.credit_score,
                "rating_avg": seller.rating_avg,
                "rating_count": seller.rating_count,
                "completed_count": seller.completed_count,
            },
            "matched_properties": [  # 改名为 matched_properties 匹配 schema
                {
                    "id": p.id,
                    "community": p.community,
                    "layout": p.layout,
                    "area": p.area,
                    "total_price": p.total_price,
                    "tags": p.tags or [],
                    "images": (p.images or [])[:1],
                }
                for p in item["properties"]
            ],
        })

    # 7. 写缓存
    import json
    try:
        redis_client.setex(cache_key, CACHE_TTL, json.dumps(output, default=str))
    except Exception as e:
        logger.warning("Failed to cache recommendations", extra={"error": str(e)})

    return output
