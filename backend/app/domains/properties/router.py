"""Properties 域 - 房源 CRUD。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.domains.auth.dependencies import get_current_user
from app.models.property import Property, PropertyStatus
from app.models.user import User
from app.schemas.business import (
    PropertyCreate,
    PropertyDetail,
    PropertyResponse,
    PropertyUpdate,
)
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/properties", tags=["房源"])


def _user_to_brief(u: User) -> dict:
    """[Sprint1-P0] 把 User 转成脱敏名片 dict（不含真实姓名/手机/邮箱）。"""
    return {
        "id": u.id,
        "display_name": u.display_name,
        "avatar_url": u.avatar_url,
        "credit_score": u.credit_score,
        "is_verified": u.is_verified,
    }




@router.post("", response_model=APIResponse[PropertyResponse], summary="创建房源")
async def create_property(
    body: PropertyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[PropertyResponse]:
    """卖方经纪人发布房源。"""
    seller_id = user.id
    prop = Property(
        seller_id=seller_id,
        community=body.community,
        layout=body.layout,
        area=body.area,
        total_price=body.total_price,
        tags=body.tags,
        images=body.images,
        viewing_time=body.viewing_time,
        source_url=body.source_url,
        is_verified=body.is_verified,
        status=PropertyStatus.ACTIVE,
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    logger.info("Property created", extra={"property_id": prop.id, "seller_id": seller_id})
    return APIResponse(data=PropertyResponse.model_validate(prop))


@router.get("", response_model=APIResponse[list[PropertyResponse]], summary="我的房源")
async def list_my_properties(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[PropertyResponse]]:
    """列出当前用户的所有房源。"""
    seller_id = user.id
    props = db.scalars(
        select(Property)
        .where(Property.seller_id == seller_id, Property.deleted_at.is_(None))
        .order_by(Property.created_at.desc())
    ).all()
    return APIResponse(data=[PropertyResponse.model_validate(p) for p in props])


@router.get("/{prop_id}", response_model=APIResponse[PropertyDetail], summary="房源详情")
async def get_property(
    prop_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[PropertyDetail]:
    """[Sprint1-P0] 返回房源详情 + 脱敏卖家名片（不含真实姓名/手机/邮箱）。

    卖家信息通过 ``seller_brief`` 字段返回，包含：
    - ``display_name``（"张先生" 形式，非真实姓名）
    - ``credit_score`` + ``is_verified`` + ``avatar_url``
    - 真实联系方式（手机/邮箱/姓名）需握手成功后才暴露
    """
    prop = db.get(Property, prop_id)
    if not prop or prop.deleted_at:
        raise NotFoundError("房源不存在")

    # 拉卖家（脱敏）
    seller = db.get(User, prop.seller_id) if prop.seller_id else None
    seller_brief = _user_to_brief(seller) if seller else None

    # 先 dump PropertyResponse 的字段，再注入 seller_brief（避免 model_validate 校验缺字段）
    detail_dict = PropertyResponse.model_validate(prop).model_dump()
    detail_dict["seller_brief"] = seller_brief
    return APIResponse(data=detail_dict)  # type: ignore[arg-type]


@router.patch("/{prop_id}", response_model=APIResponse[PropertyResponse], summary="更新房源")
async def update_property(
    prop_id: int,
    body: PropertyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[PropertyResponse]:
    prop = db.get(Property, prop_id)
    if not prop or prop.deleted_at:
        raise NotFoundError("房源不存在")
    if prop.seller_id != user.id:
        raise PermissionDeniedError("只能修改自己的房源")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(prop, field, value)
    db.commit()
    db.refresh(prop)
    return APIResponse(data=PropertyResponse.model_validate(prop))


@router.delete("/{prop_id}", response_model=APIResponse[dict], summary="下架房源")
async def delete_property(
    prop_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    prop = db.get(Property, prop_id)
    if not prop or prop.deleted_at:
        raise NotFoundError("房源不存在")
    if prop.seller_id != user.id:
        raise PermissionDeniedError("只能下架自己的房源")
    from datetime import datetime, timezone
    prop.deleted_at = datetime.now(timezone.utc)
    prop.status = PropertyStatus.INACTIVE
    db.commit()
    return APIResponse(data={"id": prop_id, "status": "inactive"})
