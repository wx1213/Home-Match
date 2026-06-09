"""Reviews 域 - 评价 + 信用分重算。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.domains.auth.dependencies import get_current_user
from app.domains.reviews.credit_score import (
    compute_credit_score,
    update_user_credit_score,
)
from app.models.cooperation import Cooperation, CooperationStatus
from app.models.review import Review
from app.models.user import User
from app.schemas.business import ReviewCreate, ReviewResponse
from app.schemas.common import APIResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/cooperations/{coop_id}/review", tags=["评价"])


@router.post("", response_model=APIResponse[ReviewResponse], summary="提交评价")
async def submit_review(
    coop_id: int,
    body: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APIResponse[ReviewResponse]:
    """合作结束后提交评价。合作双方必须都评完，信用分才更新。"""
    coop = db.get(Cooperation, coop_id)
    if not coop or coop.deleted_at:
        raise NotFoundError("合作不存在")

    if user.id not in (coop.buyer_id, coop.seller_id):
        raise PermissionDeniedError("只能评价自己参与的合作")

    if coop.status not in (CooperationStatus.HANDSHAKED, CooperationStatus.IN_PROGRESS, CooperationStatus.COMPLETED):
        raise ValidationError("合作尚未开始，不能评价")

    # 不能重复评价
    existing = db.scalar(
        select(Review).where(
            Review.cooperation_id == coop_id,
            Review.reviewer_id == user.id,
        )
    )
    if existing:
        raise ValidationError("已评价过，不可重复")

    # 标记合作方
    reviewee_id = coop.seller_id if user.id == coop.buyer_id else coop.buyer_id

    review = Review(
        cooperation_id=coop_id,
        reviewer_id=user.id,
        reviewee_id=reviewee_id,
        rating=body.rating,
        comment=body.comment,
        tags=body.tags or [],
        is_anonymous=body.is_anonymous,
    )
    db.add(review)

    # 标记已评价
    if user.id == coop.buyer_id:
        coop.buyer_reviewed = True
    else:
        coop.seller_reviewed = True

    # 双方都评完了 → 重算信用分
    if coop.buyer_reviewed and coop.seller_reviewed:
        # 强制 flush，让新评价对后续查询可见
        db.flush()
        # 双方都评完，更新双方信用分
        for uid in (coop.buyer_id, coop.seller_id):
            update_user_credit_score(db, uid)
        # 合作状态推进到 completed
        if coop.status == CooperationStatus.HANDSHAKED or coop.status == CooperationStatus.IN_PROGRESS:
            coop.status = CooperationStatus.COMPLETED
            coop.closed_at = datetime.now(timezone.utc)
        logger.info(
            "Cooperation completed, both reviewed",
            extra={"cooperation_id": coop_id, "buyer_id": coop.buyer_id, "seller_id": coop.seller_id},
        )

    db.commit()
    db.refresh(review)
    logger.info("Review submitted", extra={"review_id": review.id, "reviewer_id": user.id, "rating": review.rating})
    return APIResponse(data=ReviewResponse.model_validate(review))


@router.get("", response_model=APIResponse[list[ReviewResponse]], summary="合作的评价列表")
async def list_reviews(
    coop_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[ReviewResponse]]:
    """查看某合作的所有评价（实名版）。"""
    coop = db.get(Cooperation, coop_id)
    if not coop or coop.deleted_at:
        raise NotFoundError("合作不存在")
    reviews = db.scalars(
        select(Review).where(Review.cooperation_id == coop_id)
        .order_by(Review.created_at.desc())
    ).all()
    return APIResponse(data=[ReviewResponse.model_validate(r) for r in reviews])
