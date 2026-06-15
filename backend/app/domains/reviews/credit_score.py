"""信用分计算（[D-002]）。

公式：
    基础分   = 评价均分 × 20
    活跃系数 = min(1.0, 0.3 + 0.7 × min(1, 近30天有效响应数/10))
    信用分   = 基础分 × 活跃系数

范围: 6 - 100

每日定时任务调用，结果缓存到 users.credit_score。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.cooperation import Cooperation, CooperationStatus
from app.models.invitation import Invitation, InvitationStatus
from app.models.review import Review
from app.models.user import User

logger = get_logger(__name__)

# 可调参数
RATING_SCALE = 20  # 1-5 星 → 20-100 分
INACTIVITY_FLOOR = 0.3
ACTIVITY_TARGET = 10  # 每月响应次数目标


def compute_credit_score(
    rating_avg: float,
    activity_count_30d: int,
) -> float:
    """根据评价均分和近 30 天响应数计算信用分。"""
    # 基础分
    base_score = (rating_avg or 0) * RATING_SCALE

    # 活跃系数
    activity_count = min(activity_count_30d, ACTIVITY_TARGET)
    activity_factor = min(1.0, INACTIVITY_FLOOR + 0.7 * (activity_count / ACTIVITY_TARGET))

    # 最终分
    final = base_score * activity_factor
    # 限制在 6-100 范围
    return round(max(6.0, min(100.0, final)), 1)


def _compute_rating_avg(db: Session, user_id: int) -> tuple[float, int]:
    """计算用户的评价均分和评价数。"""
    result = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.reviewee_id == user_id,
            Review.deleted_at.is_(None),
        )
    ).first()
    if result is None:
        return 0.0, 0
    avg = float(result[0]) if result[0] else 0.0
    count = int(result[1]) if result[1] else 0
    return avg, count


def _compute_activity_count(db: Session, user_id: int) -> int:
    """计算用户近 30 天的有效响应数（接单 + 提交方案 + 评价）。"""
    since = datetime.now(timezone.utc) - timedelta(days=30)
    # 接单数
    accepted = db.scalar(
        select(func.count(Invitation.id)).where(
            Invitation.seller_id == user_id,
            Invitation.responded_at >= since,
            Invitation.status.in_([
                InvitationStatus.ACCEPTED.value,
                InvitationStatus.PROPOSAL_REVIEW.value,
                InvitationStatus.HANDSHAKED.value,
            ]),
        )
    ) or 0
    return int(accepted)


def _compute_completed_count(db: Session, user_id: int) -> int:
    """计算用户已完成合作数（作为 buyer 或 seller）。"""
    count = db.scalar(
        select(func.count(Cooperation.id)).where(
            Cooperation.deleted_at.is_(None),
            (Cooperation.buyer_id == user_id) | (Cooperation.seller_id == user_id),
            Cooperation.status == CooperationStatus.COMPLETED.value,
        )
    ) or 0
    return int(count)


def update_user_credit_score(db: Session, user_id: int) -> float:
    """重算并更新用户信用分。返回新分数。"""
    rating_avg, rating_count = _compute_rating_avg(db, user_id)
    activity_count = _compute_activity_count(db, user_id)
    completed_count = _compute_completed_count(db, user_id)
    new_score = compute_credit_score(rating_avg, activity_count)

    user = db.get(User, user_id)
    if user:
        user.credit_score = new_score
        user.rating_avg = rating_avg
        user.rating_count = rating_count
        user.activity_count_30d = activity_count
        user.completed_count = completed_count
        user.credit_score_updated_at = datetime.now(timezone.utc)
        logger.info(
            "Credit score updated",
            extra={
                "user_id": user_id,
                "new_score": new_score,
                "rating_avg": rating_avg,
                "activity": activity_count,
                "completed": completed_count,
            },
        )
    return new_score


def recompute_all_credit_scores(db: Session) -> int:
    """重算所有 active 用户的信用分。返回处理的用户数。"""
    user_ids = db.scalars(
        select(User.id).where(
            User.status == "active",
            User.deleted_at.is_(None),
        )
    ).all()
    count = 0
    for uid in user_ids:
        try:
            update_user_credit_score(db, uid)
            count += 1
        except Exception as e:
            logger.warning(
                "Failed to recompute credit score",
                extra={"user_id": uid, "error": str(e)},
            )
    db.commit()
    logger.info("All credit scores recomputed", extra={"count": count})
    return count

