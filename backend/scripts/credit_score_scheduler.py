#!/usr/bin/env python3
"""HomeMatch 信用分每日定时调度器。

独立的常驻进程：每晚 0:00（local timezone）调一次
`recompute_all_credit_scores_task`（RQ 任务），保证：

- activity_count_30d 字段每日刷新
- 新增/新评的合作/评价被正确计入
- credit_score_updated_at 时间戳推进

用法：
    # 前台跑（开发调试，看日志）
    python -m scripts.credit_score_scheduler

    # 后台跑（生产/开发）
    nohup python -m scripts.credit_score_scheduler > /tmp/credit_score_cron.log 2>&1 &

    # 立即手动跑一次（不等待定时）
    python -m scripts.recompute_credit_scores

实现说明：
- MVP 阶段用进程内 sleep 循环，依赖小、易调试
- 生产建议改用 RQ Scheduler (rq-scheduler) 或系统级 cron (launchd / crontab)
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 路径 hack：让脚本能从项目根目录导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("credit_score_cron")


def _seconds_until_next_3am() -> float:
    """计算到下一个 0:00:00 的秒数。"""
    now = datetime.now()
    next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    # 如果今天还没到 0 点，跨日的话 next_run 应该是今天 0 点
    today_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now < today_run:
        next_run = today_run
    delta = (next_run - now).total_seconds()
    return max(1.0, delta)


def main() -> int:
    logger.info("🚀 HomeMatch 信用分每日调度器启动")
    logger.info("   调度时间: 每日 0:00 (local)")
    logger.info("   Ctrl+C 停止")

    while True:
        sleep_seconds = _seconds_until_next_3am()
        next_run_time = datetime.now() + timedelta(seconds=sleep_seconds)
        logger.info(f"⏰ 下次执行: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')} (sleep {sleep_seconds:.0f}s)")

        try:
            time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            logger.info("🛑 收到 Ctrl+C，退出")
            return 0

        # 触发 RQ 任务（直接调用函数，1 秒内完成，不入队）
        try:
            from app.workers.credit_score import recompute_all_credit_scores_task

            logger.info("🔄 开始重算所有用户信用分...")
            start = time.time()
            count = recompute_all_credit_scores_task()
            elapsed = time.time() - start
            logger.info(f"✅ 重算完成: {count} 个用户，耗时 {elapsed:.2f}s")
        except Exception as e:
            # 任何异常都不能让进程挂掉
            logger.exception(f"❌ 重算失败（将继续等下一周期）: {e}")
            time.sleep(60)  # 失败后等 1 分钟再算下次时间，避免快速循环


if __name__ == "__main__":
    sys.exit(main())
