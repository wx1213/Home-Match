"""Invitations 域 - 邀请生命周期。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.core.errors import (
    InvitationExpiredError,
    InvalidStateTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.domains.invitations.state_machine import (
    INVITATION_TTL_HOURS,
    InvitationStateMachine,
)
from app.models.demand import Demand
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User
from app.schemas.business import (
    InvitationAcceptResponse,
    InvitationCreate,
    InvitationResponse,
)
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/invitations", tags=["邀请"])




@router.post("", response_model=APIResponse[InvitationResponse], summary="发起邀请")
async def create_invitation(
    body: InvitationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[InvitationResponse]:
    """买方从 Top 5 中选 1 名卖方发起邀请。"""
    buyer_id = user.id

    # 校验需求存在
    demand = db.get(Demand, body.demand_id)
    if not demand or demand.deleted_at:
        raise NotFoundError("需求不存在")
    if demand.buyer_id != buyer_id:
        raise PermissionDeniedError("只能为自己的需求发起邀请")
    if demand.status == "closed":
        raise ValidationError("需求已关闭")

    # 校验卖方存在
    seller = db.get(User, body.seller_id)
    if not seller or seller.deleted_at:
        raise NotFoundError("卖方用户不存在")

    # 校验：本轮是否已经邀请过
    existing = db.scalar(
        select(Invitation).where(
            Invitation.demand_id == body.demand_id,
            Invitation.seller_id == body.seller_id,
            Invitation.status.in_([
                InvitationStatus.PENDING.value,
                InvitationStatus.ACCEPTED.value,
                InvitationStatus.PROPOSAL_REVIEW.value,
            ]),
        )
    )
    if existing:
        raise ValidationError("已向该卖方发起过邀请，请勿重复")

    # 创建
    now = datetime.now(timezone.utc)
    invitation = Invitation(
        demand_id=body.demand_id,
        buyer_id=buyer_id,
        seller_id=body.seller_id,
        status=InvitationStatus.PENDING,
        expired_at=now + timedelta(hours=INVITATION_TTL_HOURS),
        note=body.note,
    )
    db.add(invitation)
    demand.invite_count = (demand.invite_count or 0) + 1
    db.commit()
    db.refresh(invitation)
    logger.info(
        "Invitation created",
        extra={"invitation_id": invitation.id, "demand_id": body.demand_id, "seller_id": body.seller_id},
    )
    return APIResponse(data=InvitationResponse.model_validate(invitation))


@router.get("", response_model=APIResponse[list[InvitationResponse]], summary="我的邀请")
async def list_my_invitations(
    role: str = "buyer",  # buyer | seller
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[InvitationResponse]]:
    """列出当前用户的邀请（按角色：买方/卖方）。"""
    user_id = user.id
    if role == "buyer":
        stmt = select(Invitation).where(Invitation.buyer_id == user_id)
    else:
        stmt = select(Invitation).where(Invitation.seller_id == user_id)
    if status:
        stmt = stmt.where(Invitation.status == status)
    stmt = stmt.where(Invitation.deleted_at.is_(None)).order_by(Invitation.created_at.desc())
    items = db.scalars(stmt).all()
    return APIResponse(data=[InvitationResponse.model_validate(i) for i in items])


@router.get("/{inv_id}", response_model=APIResponse[InvitationResponse], summary="邀请详情")
async def get_invitation(
    inv_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[InvitationResponse]:
    inv = db.get(Invitation, inv_id)
    if not inv or inv.deleted_at:
        raise NotFoundError("邀请不存在")
    if user.id not in (inv.buyer_id, inv.seller_id):
        raise PermissionDeniedError("只能查看自己参与的合作")
    return APIResponse(data=InvitationResponse.model_validate(inv))


@router.post(
    "/{inv_id}/accept",
    response_model=APIResponse[InvitationAcceptResponse],
    summary="接单（卖方）",
)
async def accept_invitation(
    inv_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[InvitationAcceptResponse]:
    """卖方在 24h 内点击"感兴趣"，状态机：pending → accepted。"""
    inv = db.get(Invitation, inv_id)
    if not inv or inv.deleted_at:
        raise NotFoundError("邀请不存在")

    if inv.seller_id != user.id:
        raise PermissionDeniedError("只能接自己的邀请")

    sm = InvitationStateMachine(inv)
    # P1-5：非法状态转移返 409 (InvalidStateTransitionError)，不是 400
    if not sm.can_accept():
        raise InvalidStateTransitionError(
            f"当前状态 {inv.status} 不可接单",
            detail={"current_state": inv.status, "action": "accept"},
        )

    # 检查是否超时
    # P1-3 修复：SQLite 不存 tz，从 DB 读回的 datetime 是 naive，需补 tz 后再比较
    expired_at = inv.expired_at
    if expired_at.tzinfo is None:
        expired_at = expired_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expired_at:
        # 触发过期
        sm.expire()
        db.commit()
        raise InvitationExpiredError("邀请已超时失效")

    sm.accept()
    InvitationStateMachine.apply_accept_side_effects(inv)
    db.commit()
    db.refresh(inv)
    logger.info("Invitation accepted", extra={"invitation_id": inv.id})

    return APIResponse(
        data=InvitationAcceptResponse(
            invitation_id=inv.id,
            status=inv.status.value if hasattr(inv.status, "value") else inv.status,
            proposal_deadline=inv.proposal_deadline,
        )
    )


@router.post("/{inv_id}/reject", response_model=APIResponse[dict], summary="拒绝（卖方）")
async def reject_invitation(
    inv_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    """卖方主动拒绝。"""
    inv = db.get(Invitation, inv_id)
    if not inv or inv.deleted_at:
        raise NotFoundError("邀请不存在")
    if inv.seller_id != user.id:
        raise PermissionDeniedError("只能拒绝自己的邀请")

    sm = InvitationStateMachine(inv)
    # P1-5：补 can_reject 校验（之前缺失，导致 accept/reject/expire 后再 reject → 500）
    if not sm.can_reject():
        raise InvalidStateTransitionError(
            f"当前状态 {inv.status} 不可拒绝",
            detail={"current_state": inv.status, "action": "reject"},
        )
    sm.reject()
    InvitationStateMachine.apply_reject_side_effects(inv)
    if reason:
        inv.reject_reason = reason
    db.commit()
    return APIResponse(data={"id": inv.id, "status": inv.status.value if hasattr(inv.status, "value") else inv.status})
