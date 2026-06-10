"""P2-6: 信用分计算纯函数测试（最高 ROI — 业务核心逻辑）。

compute_credit_score 是纯函数（无 DB 依赖），便于单测覆盖。
其他函数（_compute_*）需要 DB 集成测试，留给 e2e。
"""
from __future__ import annotations

import pytest

from app.domains.reviews.credit_score import (
    ACTIVITY_TARGET,
    INACTIVITY_FLOOR,
    RATING_SCALE,
    compute_credit_score,
)


class TestComputeCreditScore:
    """P2-6：信用分公式边界值覆盖。"""

    def test_zero_rating_floors_at_6(self):
        """rating_avg=0 → 基础分=0，活跃系数最低 0.3 → 0 * 0.3 = 0 → 取 6 下限。"""
        result = compute_credit_score(0.0, 0)
        assert result == 6.0

    def test_zero_rating_active_floors_at_6(self):
        """rating_avg=0 + 高活跃 → 0 * 1.0 = 0 → 仍 6 下限。"""
        result = compute_credit_score(0.0, 100)
        assert result == 6.0

    def test_perfect_rating_no_activity(self):
        """5 星 + 0 活跃 → 5*20 * (0.3 + 0.7*0) = 100*0.3 = 30.0。"""
        result = compute_credit_score(5.0, 0)
        assert result == 30.0

    def test_perfect_rating_full_activity(self):
        """5 星 + 10+ 活跃 → 5*20 * 1.0 = 100.0。"""
        result = compute_credit_score(5.0, 10)
        assert result == 100.0

    def test_partial_activity(self):
        """4 星 + 5 活跃（半满）→ 4*20 * (0.3 + 0.7*0.5) = 80 * 0.65 = 52.0。"""
        result = compute_credit_score(4.0, 5)
        assert result == 52.0

    def test_activity_beyond_target_caps_at_1(self):
        """活跃数 > ACTIVITY_TARGET → 系数仍 1.0。"""
        result_10 = compute_credit_score(4.0, 10)
        result_100 = compute_credit_score(4.0, 100)
        assert result_10 == result_100  # 都被 cap 在 1.0

    def test_result_clamped_between_6_and_100(self):
        """结果强制在 [6, 100]。"""
        # 极端低
        assert 6.0 <= compute_credit_score(0, 0) <= 100.0
        # 极端高
        assert 6.0 <= compute_credit_score(5.0, 100) <= 100.0
        # 正常范围
        for rating in [0, 1, 2, 3, 4, 5]:
            for activity in [0, 5, 10, 20]:
                score = compute_credit_score(rating, activity)
                assert 6.0 <= score <= 100.0, f"rating={rating} activity={activity} → {score}"

    def test_none_rating_treated_as_zero(self):
        """rating_avg=None → 当 0 处理。"""
        result = compute_credit_score(None, 0)  # type: ignore[arg-type]
        assert result == 6.0

    def test_result_is_rounded_to_1_decimal(self):
        """结果四舍五入到 1 位小数。"""
        result = compute_credit_score(3.333, 7)
        # 3.333 * 20 = 66.66
        # 活跃系数 = 0.3 + 0.7*(7/10) = 0.3 + 0.49 = 0.79
        # 66.66 * 0.79 = 52.6614 → 52.7
        assert result == 52.7

    def test_constants_match_spec(self):
        """常量符合 D-002 公式定义。"""
        assert RATING_SCALE == 20
        assert INACTIVITY_FLOOR == 0.3
        assert ACTIVITY_TARGET == 10
