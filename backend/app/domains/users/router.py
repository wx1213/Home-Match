"""Users 域 - 当前用户信息 + 业务统计。"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.domains.auth.dependencies import get_current_user
from app.models.cooperation import Cooperation, CooperationStatus
from app.models.demand import Demand, DemandStatus
from app.models.property import Property, PropertyStatus
from app.models.review import Review
from app.models.user import User
from app.schemas.business import UserResponse, UserStatsResponse
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/users", tags=["用户"])


class UserPublicBrief(BaseModel):
    """公开的、用于名片展示的用户简档（不含手机/邮箱等敏感字段）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str | None
    avatar_url: str | None
    credit_score: float
    is_verified: bool


@router.get("/me", response_model=APIResponse[UserResponse], summary="当前用户信息")
async def get_me(
    user: User = Depends(get_current_user),
) -> APIResponse[UserResponse]:
    """返回当前登录用户的完整信息（含信用分）。"""
    return APIResponse(data=UserResponse.model_validate(user))


@router.get(
    "/me/stats",
    response_model=APIResponse[UserStatsResponse],
    summary="当前用户业务统计",
)
async def get_my_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[UserStatsResponse]:
    """返回个人中心需要的全部实时统计。"""
    # 有效需求数（active 或 matched，未删除）
    demand_count = db.scalar(
        select(func.count(Demand.id)).where(
            Demand.buyer_id == user.id,
            Demand.deleted_at.is_(None),
            Demand.status.in_([DemandStatus.ACTIVE.value, DemandStatus.MATCHED.value]),
        )
    ) or 0

    # 有效房源数
    property_count = db.scalar(
        select(func.count(Property.id)).where(
            Property.seller_id == user.id,
            Property.deleted_at.is_(None),
            Property.status.in_([PropertyStatus.ACTIVE.value, PropertyStatus.FROZEN.value]),
        )
    ) or 0

    # 进行中合作数（已握手 + 进行中）
    cooperation_count = db.scalar(
        select(func.count(Cooperation.id)).where(
            Cooperation.deleted_at.is_(None),
            (Cooperation.buyer_id == user.id) | (Cooperation.seller_id == user.id),
            Cooperation.status.in_([
                CooperationStatus.HANDSHAKED.value,
                CooperationStatus.IN_PROGRESS.value,
            ]),
        )
    ) or 0

    # 已完成合作数
    completed_count = db.scalar(
        select(func.count(Cooperation.id)).where(
            Cooperation.deleted_at.is_(None),
            (Cooperation.buyer_id == user.id) | (Cooperation.seller_id == user.id),
            Cooperation.status == CooperationStatus.COMPLETED.value,
        )
    ) or 0

    # 我发出的评价
    review_given = db.scalar(
        select(func.count(Review.id)).where(
            Review.reviewer_id == user.id,
            Review.deleted_at.is_(None),
        )
    ) or 0

    # 我收到的评价
    review_received = db.scalar(
        select(func.count(Review.id)).where(
            Review.reviewee_id == user.id,
            Review.deleted_at.is_(None),
        )
    ) or 0

    return APIResponse(
        data=UserStatsResponse(
            demand_count=int(demand_count),
            property_count=int(property_count),
            cooperation_count=int(cooperation_count),
            completed_count=int(completed_count),
            review_given_count=int(review_given),
            review_received_count=int(review_received),
            credit_score=user.credit_score,
            rating_avg=user.rating_avg,
            rating_count=user.rating_count,
            activity_count_30d=user.activity_count_30d,
        )
    )


@router.get(
    "/batch",
    response_model=APIResponse[List[UserPublicBrief]],
    summary="批量查询用户公开名片",
)
async def batch_get_users(
    ids: str = Query(
        ...,
        description="逗号分隔的 user_id 列表，如 1,2,3",
        examples=["1,2,3"],
    ),
    db: Session = Depends(get_db),
) -> APIResponse[List[UserPublicBrief]]:
    """批量返回用户公开简档。开发模式身份切换器/批量卡片展示用。

    - 不需要鉴权（公开信息）
    - 找不到的 id 静默忽略
    - 按输入 id 顺序返回
    """
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        return APIResponse(data=[])

    if not id_list:
        return APIResponse(data=[])

    users = db.scalars(
        select(User).where(
            User.id.in_(id_list),
            User.deleted_at.is_(None),
        )
    ).all()
    # 按输入顺序排
    user_map = {u.id: u for u in users}
    ordered = [user_map[i] for i in id_list if i in user_map]
    return APIResponse(data=[UserPublicBrief.model_validate(u) for u in ordered])


@router.get(
    "/dev-identities",
    response_model=APIResponse[List[dict]],
    summary="列出可用的 dev 身份（开发模式身份切换用）",
)
async def list_dev_identities(
    db: Session = Depends(get_db),
) -> APIResponse[List[dict]]:
    """返回所有 mock 模式创建的 dev 身份（按 wechat_unionid 识别）。

    用于 dev 切换器自动发现可用身份（不再硬编码 6 个）。
    """
    users = db.scalars(
        select(User)
        .where(
            User.deleted_at.is_(None),
            User.wechat_unionid.like("mock_unionid_%"),
        )
        .order_by(User.id)
    ).all()
    items = []
    for u in users:
        # 从 wechat_unionid 提取出 dev code（去掉 mock_unionid_ 前缀）
        code = u.wechat_unionid.removeprefix("mock_unionid_") if u.wechat_unionid else None
        if not code:
            continue
        # 自动判定角色（基于是否有需求/房源）
        # 简化：从 properties 数量判断卖方，从 demands 判断买方
        from app.models.property import Property
        from app.models.demand import Demand
        prop_count = db.scalar(
            select(func.count(Property.id)).where(Property.seller_id == u.id)
        ) or 0
        demand_count = db.scalar(
            select(func.count(Demand.id)).where(Demand.buyer_id == u.id)
        ) or 0

        if demand_count > 0 and prop_count > 0:
            role = "both"
            role_label = "双重身份"
        elif prop_count > 0:
            role = "seller"
            role_label = "卖方"
        elif demand_count > 0:
            role = "buyer"
            role_label = "买方代表"
        else:
            role = "neither"
            role_label = "未配置"

        items.append({
            "code": code,
            "user_id": u.id,
            "display_name": u.display_name,
            "name": u.name,
            "credit_score": u.credit_score,
            "is_verified": u.is_verified,
            "role": role,
            "role_label": role_label,
            "demand_count": demand_count,
            "property_count": prop_count,
        })
    return APIResponse(data=items)
