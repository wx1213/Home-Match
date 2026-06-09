#!/usr/bin/env python3
"""每日定时任务：重算所有用户信用分。

用法：
    # 直接运行（开发/MVP）
    python -m scripts.recompute_credit_scores

    # 或通过 cron（生产）：
    0 3 * * * cd /app && python -m scripts.recompute_credit_scores >> /var/log/homematch/credit.log 2>&1
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# 路径 hack：让脚本能从项目根目录导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.domains.reviews.credit_score import recompute_all_credit_scores
from app.workers.credit_score import recompute_all_credit_scores_task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    start = time.time()
    try:
        # 复用 worker 函数（与 RQ 任务入口一致）
        count = recompute_all_credit_scores_task()
        elapsed = time.time() - start
        logger.info(f"✅ 重算完成: {count} 个用户，耗时 {elapsed:.2f}s")
        return 0
    except Exception as e:
        logger.exception(f"❌ 重算失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
