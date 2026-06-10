"""Cooperations 域 - 合作主记录 + 握手。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.core.errors import (
    InvalidStateTransitionError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.domains.invitations.state_machine import InvitationStateMachine
from app.models.cooperation import Cooperation, CooperationStatus
from app.models.user import User
from app.models.invitation import Invitation, InvitationStatus
from app.models.proposal import Proposal
from app.schemas.business import CooperationResponse
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(tags=["合作"])




@router.post(
    "/invitations/{inv_id}/confirm",
    response_model=APIResponse[CooperationResponse],
    summary="确认方案 → 握手（买方）",
)
async def confirm_proposal(
    inv_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[CooperationResponse]:
    """买方确认方案，触发握手，生成合作记录。

    握手时自动生成《合作备忘录》内容（MVP：模板拼接）。
    """
    inv = db.get(Invitation, inv_id)
    if not inv or inv.deleted_at:
        raise NotFoundError("邀请不存在")
    if inv.buyer_id != user.id:
        raise PermissionDeniedError("只能确认自己的邀请")

    sm = InvitationStateMachine(inv)
    # P1-5：非法状态转移返 409
    if not sm.can_confirm():
        raise InvalidStateTransitionError(
            f"当前状态 {inv.status} 不可确认",
            detail={"current_state": inv.status, "action": "confirm"},
        )

    proposal = db.scalar(select(Proposal).where(Proposal.invitation_id == inv_id))
    if not proposal:
        raise NotFoundError("方案不存在，无法握手")

    # 生成合作备忘录（MVP：模板）
    now = datetime.now(timezone.utc)
    memo = _generate_memo(inv, proposal)

    cooperation = Cooperation(
        invitation_id=inv_id,
        buyer_id=inv.buyer_id,
        seller_id=inv.seller_id,
        status=CooperationStatus.HANDSHAKED,
        memo_content=memo,
        signed_at=now,
    )
    db.add(cooperation)

    sm.confirm()
    proposal.confirmed_at = now
    db.commit()
    db.refresh(cooperation)
    logger.info("Cooperation created (handshake)", extra={"cooperation_id": cooperation.id})
    return APIResponse(data=CooperationResponse.model_validate(cooperation))


@router.post(
    "/invitations/{inv_id}/decline",
    response_model=APIResponse[dict],
    summary="拒绝方案（买方）",
)
async def decline_proposal(
    inv_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    inv = db.get(Invitation, inv_id)
    if not inv or inv.deleted_at:
        raise NotFoundError("邀请不存在")
    if inv.buyer_id != user.id:
        raise PermissionDeniedError("只能拒绝自己的邀请")

    sm = InvitationStateMachine(inv)
    # P1-5：补 can_decline 校验（之前缺失，导致 handshaked 后再 decline → 500）
    if not sm.can_decline():
        raise InvalidStateTransitionError(
            f"当前状态 {inv.status} 不可拒绝",
            detail={"current_state": inv.status, "action": "decline"},
        )
    sm.decline()

    proposal = db.scalar(select(Proposal).where(Proposal.invitation_id == inv_id))
    if proposal:
        from datetime import datetime, timezone
        proposal.declined_at = datetime.now(timezone.utc)
        if reason:
            proposal.decline_reason = reason

    db.commit()
    return APIResponse(data={"id": inv.id, "status": inv.status.value if hasattr(inv.status, "value") else inv.status})


@router.get("/cooperations/{coop_id}", response_model=APIResponse[CooperationResponse], summary="合作详情")
async def get_cooperation(
    coop_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[CooperationResponse]:
    coop = db.get(Cooperation, coop_id)
    if not coop or coop.deleted_at:
        raise NotFoundError("合作不存在")
    if user.id not in (coop.buyer_id, coop.seller_id):
        raise PermissionDeniedError("只能查看自己参与的合作")
    return APIResponse(data=CooperationResponse.model_validate(coop))


@router.get("/cooperations", response_model=APIResponse[list[CooperationResponse]], summary="我的合作")
async def list_my_cooperations(
    role: str = "all",  # all | buyer | seller
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[CooperationResponse]]:
    """列出当前用户作为买方或卖方的所有合作。"""
    q = select(Cooperation).where(Cooperation.deleted_at.is_(None))
    if role == "buyer":
        q = q.where(Cooperation.buyer_id == user.id)
    elif role == "seller":
        q = q.where(Cooperation.seller_id == user.id)
    else:
        q = q.where(
            (Cooperation.buyer_id == user.id) | (Cooperation.seller_id == user.id)
        )
    q = q.order_by(Cooperation.signed_at.desc())
    coops = list(db.scalars(q).all())
    return APIResponse(data=[CooperationResponse.model_validate(c) for c in coops])


def _generate_memo(inv: Invitation, proposal: Proposal) -> str:
    """生成合作备忘录（MVP 模板）。"""
    return f"""# HomeMatch 合作备忘录

合作 ID: COOP-{inv.id}
买方 ID: {inv.buyer_id}
卖方 ID: {inv.seller_id}
签订时间: {datetime.now(timezone.utc).isoformat()}

## 合作内容
{proposal.content}

## 看房安排
{proposal.viewing_suggestion or "见具体方案"}

## 业主情况
{proposal.owner_situation or "见具体方案"}

---
本备忘录由 HomeMatch 平台自动生成，合作 ID 关联于原邀请 ID {inv.id}。
"""
