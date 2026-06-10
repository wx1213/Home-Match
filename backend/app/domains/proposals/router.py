"""Proposals 域 - 合作方案。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.core.errors import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.domains.invitations.state_machine import InvitationStateMachine
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User
from app.models.proposal import Proposal
from app.schemas.business import ProposalCreate, ProposalResponse
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/invitations/{inv_id}/proposal", tags=["合作方案"])




@router.post("", response_model=APIResponse[ProposalResponse], summary="提交方案（卖方）")
async def submit_proposal(
    inv_id: int,
    body: ProposalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ProposalResponse]:
    """卖方接单后 2h 内提交合作方案。"""
    inv = db.get(Invitation, inv_id)
    if not inv or inv.deleted_at:
        raise NotFoundError("邀请不存在")
    if inv.seller_id != user.id:
        raise PermissionDeniedError("只能为自己的邀请提交方案")

    sm = InvitationStateMachine(inv)
    if not sm.can_submit_proposal():
        raise ValidationError(f"当前状态 {inv.status.value} 不可提交方案")

    # 校验 2h 截止
    # P1-3 修复：SQLite 不存 tz，从 DB 读回的 datetime 是 naive，需补 tz 后再比较
    if inv.proposal_deadline:
        deadline = inv.proposal_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > deadline:
            sm.expire()
            db.commit()
            raise ValidationError("方案提交已超时")

    # 创建方案
    now = datetime.now(timezone.utc)
    proposal = Proposal(
        invitation_id=inv_id,
        content=body.content,
        fit_points=body.fit_points,
        viewing_suggestion=body.viewing_suggestion,
        owner_situation=body.owner_situation,
        submitted_at=now,
    )
    db.add(proposal)

    # 状态机推进
    sm.submit_proposal()
    db.commit()
    db.refresh(proposal)
    logger.info("Proposal submitted", extra={"invitation_id": inv_id, "proposal_id": proposal.id})
    return APIResponse(data=ProposalResponse.model_validate(proposal))


@router.get("", response_model=APIResponse[ProposalResponse], summary="查询方案")
async def get_proposal(
    inv_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ProposalResponse]:
    proposal = db.scalar(select(Proposal).where(Proposal.invitation_id == inv_id))
    if not proposal:
        raise NotFoundError("方案不存在")
    return APIResponse(data=ProposalResponse.model_validate(proposal))
