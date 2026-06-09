"""信用分重算 - RQ 任务。"""

from __future__ import annotations

import logging

from app.core.database import SessionLocal
from app.domains.reviews.credit_score import (
    recompute_all_credit_scores,
    update_user_credit_score,
)

logger = logging.getLogger(__name__)


def recompute_all_credit_scores_task() -> int:
    """RQ 任务入口：每日定时重算所有用户信用分。返回处理用户数。"""
    logger.info("Starting daily credit score recomputation")
    with SessionLocal() as db:
        try:
            count = recompute_all_credit_scores(db)
            logger.info(f"Recomputed credit scores for {count} users")
            return count
        except Exception as e:
            logger.exception(f"Failed to recompute credit scores: {e}")
            db.rollback()
            raise


def recompute_user_credit_score_task(user_id: int) -> float:
    """RQ 任务入口：单个用户信用分重算（评价提交后立即调用）。"""
    logger.info(f"Recomputing credit score for user {user_id}")
    with SessionLocal() as db:
        try:
            score = update_user_credit_score(db, user_id)
            db.commit()
            return score
        except Exception as e:
            logger.exception(f"Failed to recompute credit score for user {user_id}: {e}")
            db.rollback()
            raise
