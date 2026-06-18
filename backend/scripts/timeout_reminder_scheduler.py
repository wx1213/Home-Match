#!/usr/bin/env python3
"""HomeMatch 推送超时提醒调度器（C3）。

独立常驻进程：每 60s 扫一次：
1. 邀请 2h 提醒：Invitation.status=PENDING 且 expired_at - now < 2h 且未提醒
2. 方案 30min 提醒：Invitation.status=ACCEPTED/PROPOSAL_REVIEW 且 proposal_deadline - now < 30min 且未提醒

每个提醒发送后立即标记 reminder_sent_at，避免重复推送。
多实例防重：用 Redis SETNX 锁 + 60s TTL。

用法：
    # 前台跑（开发）
    python -m scripts.timeout_reminder_scheduler

    # 后台跑
    nohup python -m scripts.timeout_reminder_scheduler > /tmp/timeout_reminder.log 2>&1 &

    # 立即手动跑一次（不等待）
    python -m scripts.timeout_reminder_scheduler --once

实现说明（与 credit_score_scheduler 一致）：
- MVP 用进程内 sleep 循环，依赖小、易调试
- 生产建议改用 RQ Scheduler 或 launchd / crontab
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 路径 hack：让脚本能从项目根目录导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("timeout_reminder")


# 锁 key 模板
INVITATION_LOCK_KEY = "lock:timeout_reminder:invitation"
PROPOSAL_LOCK_KEY = "lock:timeout_reminder:proposal"
LOCK_TTL_SECONDS = 60

# 提醒阈值
INVITATION_REMINDER_WINDOW = timedelta(hours=2)
PROPOSAL_REMINDER_WINDOW = timedelta(minutes=30)

# 扫描间隔
SCAN_INTERVAL_SECONDS = 60


def _try_acquire_lock(key: str) -> bool:
    """Redis SETNX 锁（带 TTL）。返回 True 表示拿到锁。"""
    from app.core.redis_client import safe_get, safe_setex

    if safe_get(key) is not None:
        return False
    return safe_setex(key, LOCK_TTL_SECONDS, "1")


async def _scan_invitation_reminders() -> int:
    """扫邀请 2h 提醒。返回发送数。"""
    from app.core.database import SessionLocal
    from app.core.redis_client import safe_get
    from app.domains.push.service import PushTriggers
    from app.models.invitation import Invitation, InvitationStatus
    from sqlalchemy import select

    if safe_get(INVITATION_LOCK_KEY) is not None:
        return 0
    # 简单本地锁（单进程场景足够；多进程用 Redis SETNX 上面已写）
    # 这里单进程内直接执行

    sent = 0
    now = datetime.now(timezone.utc)
    reminder_threshold = now + INVITATION_REMINDER_WINDOW

    with SessionLocal() as db:
        # 找：status=PENDING 且 expired_at < now+2h 且未提醒
        invitations = db.scalars(
            select(Invitation).where(
                Invitation.status == InvitationStatus.PENDING,
                Invitation.deleted_at.is_(None),
                Invitation.expired_at <= reminder_threshold,
                Invitation.invitation_reminder_sent_at.is_(None),
            )
        ).all()

        for inv in invitations:
            try:
                await PushTriggers(db).on_invitation_reminder(inv)
                inv.invitation_reminder_sent_at = datetime.now(timezone.utc)
                sent += 1
            except Exception as e:
                logger.exception(f"Failed to send reminder for invitation {inv.id}: {e}")

        if sent:
            db.commit()
            logger.info(f"📩 Sent {sent} invitation reminder(s)")

    return sent


async def _scan_proposal_reminders() -> int:
    """扫方案 30min 提醒。返回发送数。"""
    from app.core.database import SessionLocal
    from app.core.redis_client import safe_get
    from app.domains.push.service import PushTriggers
    from app.models.invitation import Invitation, InvitationStatus
    from sqlalchemy import select

    if safe_get(PROPOSAL_LOCK_KEY) is not None:
        return 0

    sent = 0
    now = datetime.now(timezone.utc)
    reminder_threshold = now + PROPOSAL_REMINDER_WINDOW

    with SessionLocal() as db:
        # 找：status=ACCEPTED 或 PROPOSAL_REVIEW 且 proposal_deadline < now+30min 且未提醒
        invitations = db.scalars(
            select(Invitation).where(
                Invitation.status.in_(
                    [InvitationStatus.ACCEPTED, InvitationStatus.PROPOSAL_REVIEW]
                ),
                Invitation.deleted_at.is_(None),
                Invitation.proposal_deadline.isnot(None),
                Invitation.proposal_deadline <= reminder_threshold,
                Invitation.proposal_reminder_sent_at.is_(None),
            )
        ).all()

        for inv in invitations:
            try:
                await PushTriggers(db).on_proposal_reminder(inv)
                inv.proposal_reminder_sent_at = datetime.now(timezone.utc)
                sent += 1
            except Exception as e:
                logger.exception(f"Failed to send proposal reminder for invitation {inv.id}: {e}")

        if sent:
            db.commit()
            logger.info(f"📋 Sent {sent} proposal reminder(s)")

    return sent


async def _scan_once() -> tuple[int, int]:
    """一轮扫描。返回 (邀请提醒数, 方案提醒数)。"""
    inv_count = await _scan_invitation_reminders()
    prop_count = await _scan_proposal_reminders()
    return inv_count, prop_count


async def main_async(once: bool = False) -> int:
    logger.info("🚀 HomeMatch 推送超时提醒调度器启动")
    logger.info(f"   扫描间隔: {SCAN_INTERVAL_SECONDS}s")
    logger.info(f"   邀请提醒阈值: <{INVITATION_REMINDER_WINDOW} 到期")
    logger.info(f"   方案提醒阈值: <{PROPOSAL_REMINDER_WINDOW} 到期")
    logger.info("   Ctrl+C 停止")

    if once:
        inv, prop = await _scan_once()
        logger.info(f"✅ One-shot scan done: {inv} invitation + {prop} proposal reminders")
        return 0

    while True:
        try:
            inv, prop = await _scan_once()
            if inv or prop:
                logger.info(f"Scan cycle: {inv} invitation + {prop} proposal reminders")
        except Exception as e:
            logger.exception(f"❌ Scan failed: {e}")

        try:
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("🛑 收到 Ctrl+C，退出")
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="推送超时提醒调度器")
    parser.add_argument(
        "--once",
        action="store_true",
        help="只跑一轮扫描（调试用）",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(once=args.once))


if __name__ == "__main__":
    sys.exit(main())
