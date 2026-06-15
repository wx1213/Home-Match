"""信用分调度器测试（[scripts/credit_score_scheduler.py]）。

P2-6 补完：原 0% 覆盖。本文件测试：
1. `_seconds_until_next_3am` 各种场景（虽然函数名叫 3am，实际算 0 点 — 这是已知命名误导）
2. `main()` 循环逻辑（mock time.sleep + 注入任务调用）
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from freezegun import freeze_time

from scripts.credit_score_scheduler import _seconds_until_next_3am, main


class TestSecondsUntilNext3am:
    """`_seconds_until_next_3am` 名字误导 — 实际算到下一个 0:00:00 的秒数。"""

    def test_morning_returns_seconds_until_midnight(self):
        """早上 8 点 → 还有 16 小时到次日 0 点。"""
        with freeze_time("2026-06-15 08:00:00"):
            secs = _seconds_until_next_3am()
        # 16 小时 = 57600 秒
        assert secs == 16 * 3600

    def test_just_before_midnight_returns_one_second(self):
        """23:59:59 → 1 秒到 0 点。"""
        with freeze_time("2026-06-15 23:59:59"):
            secs = _seconds_until_next_3am()
        assert secs == 1.0  # 函数内有 max(1.0, ...)

    def test_at_midnight_returns_one_second(self):
        """0:00:00 整 → 应该返回 1 秒（min 下限）。"""
        with freeze_time("2026-06-15 00:00:00"):
            secs = _seconds_until_next_3am()
        # 跨日：今天 0 点 = 当前，没有更早的；明天 0 点 - 0 秒 = 0 → max(1, 0) = 1
        assert secs == 1.0

    def test_afternoon_returns_seconds_until_midnight(self):
        """下午 14:30:00 → 9.5 小时到次日 0 点。"""
        with freeze_time("2026-06-15 14:30:00"):
            secs = _seconds_until_next_3am()
        # 9.5 小时 = 34200 秒
        assert secs == 9.5 * 3600

    def test_always_at_least_one_second(self):
        """任何时刻返回值都 ≥ 1（防止 sleep(0) 死循环）。"""
        for hour in [0, 1, 6, 12, 18, 23]:
            with freeze_time(f"2026-06-15 {hour:02d}:00:00"):
                secs = _seconds_until_next_3am()
            assert secs >= 1.0


class TestMainLoop:
    """main() 无限循环 — 用 mock time.sleep 退出。"""

    def test_runs_one_iteration_then_breaks_on_keyboard_interrupt(self):
        """一次 sleep 后 KeyboardInterrupt → 优雅退出，返回 0。"""
        with (
            patch("scripts.credit_score_scheduler.time.sleep", side_effect=KeyboardInterrupt),
            patch(
                "app.workers.credit_score.recompute_all_credit_scores_task",
                return_value=42,
            ) as mock_task,
        ):
            exit_code = main()

        assert exit_code == 0
        # 任务还没触发就被 KeyboardInterrupt 打断（在 sleep 时）
        mock_task.assert_not_called()

    def test_invokes_task_after_sleep(self):
        """sleep 不抛异常 → 调一次 task 任务。"""
        # 第一次 sleep 成功（让循环走完一次），第二次抛 KeyboardInterrupt 退出
        with patch("scripts.credit_score_scheduler.time.sleep") as mock_sleep:
            mock_sleep.side_effect = [None, KeyboardInterrupt]
            with patch(
                "app.workers.credit_score.recompute_all_credit_scores_task",
                return_value=10,
            ) as mock_task:
                exit_code = main()

        assert exit_code == 0
        # 第二次 sleep 是失败后的 60 秒等待（不会被触达，因为抛 KeyboardInterrupt 早退）
        # task 调了 1 次
        assert mock_task.call_count == 1

    def test_task_failure_does_not_kill_loop(self):
        """task 抛异常 → 循环 catch + 等 60s + 继续下一周期（不退出）。"""
        with patch("scripts.credit_score_scheduler.time.sleep") as mock_sleep:
            # 第一次 sleep（等 0 点）→ 成功
            # 第二次 sleep（失败后等 60s）→ 抛 KeyboardInterrupt 退出
            mock_sleep.side_effect = [None, None, KeyboardInterrupt]
            with patch(
                "app.workers.credit_score.recompute_all_credit_scores_task",
                side_effect=RuntimeError("DB down"),
            ):
                exit_code = main()

        # 进程没有崩溃退出，而是 KeyboardInterrupt 退出
        assert exit_code == 0
        # mock_sleep 至少被调 2 次：等 0 点 + 失败后等 60 秒
        assert mock_sleep.call_count >= 2
