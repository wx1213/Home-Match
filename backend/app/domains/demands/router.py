"""Demands 域 - 需求 CRUD + 推荐。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.matcher import find_top_sellers
from app.core.database import get_db
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.domains.auth.dependencies import get_current_user
from app.models.demand import Demand, DemandStatus
from app.models.user import User
from app.schemas.business import (
    DemandCreate,
    DemandResponse,
    RecommendationResponse,
    SellerMatch,
)
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/demands", tags=["需求"])



@router.post("", response_model=APIResponse[DemandResponse], summary="发布需求")
async def create_demand(
    body: DemandCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[DemandResponse]:
    """买方经纪人发布需求。"""
    if body.price_min > body.price_max:
        from app.core.errors import ValidationError
        raise ValidationError("价格区间无效：min 不能大于 max")

    buyer_id = user.id
    demand = Demand(
        buyer_id=buyer_id,
        district=body.district,
        price_min=body.price_min,
        price_max=body.price_max,
        layouts=body.layouts,
        qualification=body.qualification,
        viewing_time=body.viewing_time,
        source_url=body.source_url,
        status=DemandStatus.ACTIVE,
    )
    # 简单的 AI 摘要（MVP：直接拼接）
    demand.summary = _generate_summary(demand)
    db.add(demand)
    db.commit()
    db.refresh(demand)
    logger.info("Demand created", extra={"demand_id": demand.id, "buyer_id": buyer_id})
    return APIResponse(data=DemandResponse.model_validate(demand))


@router.get("", response_model=APIResponse[list[DemandResponse]], summary="我的需求")
async def list_my_demands(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[DemandResponse]]:
    buyer_id = user.id
    demands = db.scalars(
        select(Demand)
        .where(Demand.buyer_id == buyer_id, Demand.deleted_at.is_(None))
        .order_by(Demand.created_at.desc())
    ).all()
    return APIResponse(data=[DemandResponse.model_validate(d) for d in demands])


@router.get("/{demand_id}", response_model=APIResponse[DemandResponse], summary="需求详情")
async def get_demand(
    demand_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[DemandResponse]:
    demand = db.get(Demand, demand_id)
    if not demand or demand.deleted_at:
        raise NotFoundError("需求不存在")
    return APIResponse(data=DemandResponse.model_validate(demand))


@router.get(
    "/{demand_id}/recommendations",
    response_model=APIResponse[RecommendationResponse],
    summary="获取 Top 5 推荐卖方",
)
async def get_recommendations(
    demand_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[RecommendationResponse]:
    """根据需求推荐最匹配的 5 名卖方经纪人。"""
    demand = db.get(Demand, demand_id)
    if not demand or demand.deleted_at:
        raise NotFoundError("需求不存在")

    top = find_top_sellers(db, demand, top_n=5)
    return APIResponse(
        data=RecommendationResponse(
            demand_id=demand_id,
            sellers=[SellerMatch(**item) for item in top],
        )
    )


@router.delete(
    "/{demand_id}",
    response_model=APIResponse[dict],
    summary="下架需求",
)
async def close_demand(
    demand_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    """下架自己的需求（软删除 + status=closed，幂等）。"""
    demand = db.get(Demand, demand_id)
    if not demand:
        raise NotFoundError("需求不存在")
    if demand.buyer_id != user.id:
        raise PermissionDeniedError("只能下架自己的需求")
    # 幂等：已下架过直接返成功（避免 APP 端重复点击报错）
    if demand.deleted_at is not None or demand.status == DemandStatus.CLOSED:
        return APIResponse(data={"id": demand_id, "status": "closed", "idempotent": True})
    from datetime import datetime, timezone
    demand.deleted_at = datetime.now(timezone.utc)
    demand.status = DemandStatus.CLOSED
    db.commit()
    return APIResponse(data={"id": demand_id, "status": "closed"})


def _generate_summary(demand: Demand) -> str:
    """生成需求摘要卡（脱敏）。MVP 阶段简单拼接，二期用 LLM。"""
    layouts = "、".join(demand.layouts) if demand.layouts else "不限"
    viewing = "、".join(demand.viewing_time) if demand.viewing_time else "时间不限"
    return (
        f"{demand.district} | "
        f"{int(demand.price_min/10000)}-{int(demand.price_max/10000)}万 | "
        f"{layouts} | {demand.qualification} | {viewing}"
    )
