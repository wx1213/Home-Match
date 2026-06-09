"""邀请状态机（[D-001]）。

使用 transitions 库，状态流转：

    PENDING ──accept──> ACCEPTED ──submit_proposal──> PROPOSAL_REVIEW
       │                    │
       │ reject             │ expire (2h 未交方案)
       ▼                    ▼
    REJECTED            EXPIRED

    PROPOSAL_REVIEW ──confirm──> HANDSHAKED
                  ──decline──> CLOSED

副作用（设置 responded_at / proposal_deadline 等）在调用方手动处理。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from transitions import Machine

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============== 状态定义 ==============

STATES = [
    "pending",
    "accepted",
    "proposal_review",
    "handshaked",
    "rejected",
    "expired",
    "closed",
]


# ============== 转移定义 ==============

TRANSITIONS = [
    # 卖方接单
    {"trigger": "accept", "source": "pending", "dest": "accepted"},
    # 卖方拒绝
    {"trigger": "reject", "source": "pending", "dest": "rejected"},
    # 邀请超时（24h）
    {"trigger": "expire", "source": "pending", "dest": "expired"},
    # 卖方提交方案
    {"trigger": "submit_proposal", "source": "accepted", "dest": "proposal_review"},
    # 卖方在 2h 内没交方案 → 过期
    {"trigger": "expire", "source": "accepted", "dest": "expired"},
    # 买方确认方案 → 握手
    {"trigger": "confirm", "source": "proposal_review", "dest": "handshaked"},
    # 买方拒绝方案
    {"trigger": "decline", "source": "proposal_review", "dest": "closed"},
]


# ============== 业务规则常量 ==============

INVITATION_TTL_HOURS = 24
PROPOSAL_TTL_HOURS = 2


class InvitationStateMachine:
    """邀请状态机（包装 transitions.Machine）。"""

    def __init__(self, invitation: Any):
        """
        Args:
            invitation: Invitation ORM 实例（必须有 status 字段）
        """
        self.invitation = invitation
        # 同步状态机（trigger 方法添加到 model 上，状态字段用 status 而非默认的 state）
        self.machine = Machine(
            model=invitation,
            states=STATES,
            transitions=TRANSITIONS,
            initial=invitation.status.value,
            model_attribute="status",  # ← 关键：告诉 Machine 用 status 字段
            send_event=False,
            auto_transitions=False,
        )

    # ============== 副作用工具（外部调用） ==============

    @staticmethod
    def apply_accept_side_effects(invitation) -> None:
        """accept 后：记录响应时间 + 设置方案截止时间。"""
        now = datetime.now(timezone.utc)
        invitation.responded_at = now
        invitation.proposal_deadline = now + timedelta(hours=PROPOSAL_TTL_HOURS)
        logger.info(
            "Invitation accepted",
            extra={
                "invitation_id": invitation.id,
                "proposal_deadline": invitation.proposal_deadline.isoformat(),
            },
        )

    @staticmethod
    def apply_reject_side_effects(invitation) -> None:
        """reject 后：记录响应时间。"""
        invitation.responded_at = datetime.now(timezone.utc)
        logger.info("Invitation rejected", extra={"invitation_id": invitation.id})

    @staticmethod
    def apply_expire_side_effects(invitation) -> None:
        """expire 后：记录响应时间。"""
        invitation.responded_at = datetime.now(timezone.utc)
        logger.info("Invitation expired", extra={"invitation_id": invitation.id})

    @staticmethod
    def apply_confirm_side_effects(invitation) -> None:
        invitation.responded_at = datetime.now(timezone.utc)
        logger.info("Handshake confirmed", extra={"invitation_id": invitation.id})

    @staticmethod
    def apply_decline_side_effects(invitation) -> None:
        invitation.responded_at = datetime.now(timezone.utc)
        logger.info("Proposal declined", extra={"invitation_id": invitation.id})

    # ============== 便捷触发方法 ==============

    def accept(self) -> None:
        self.invitation.trigger("accept")

    def reject(self) -> None:
        self.invitation.trigger("reject")

    def expire(self) -> None:
        self.invitation.trigger("expire")

    def submit_proposal(self) -> None:
        self.invitation.trigger("submit_proposal")

    def confirm(self) -> None:
        self.invitation.trigger("confirm")

    def decline(self) -> None:
        self.invitation.trigger("decline")

    # ============== 状态查询 ==============

    @property
    def current_state(self) -> str:
        # Machine 把 enum 转成 str 值了，直接返回
        status = self.invitation.status
        return status.value if hasattr(status, "value") else str(status)

    def is_terminal(self) -> bool:
        return self.current_state in ("rejected", "expired", "handshaked", "closed")

    def can_accept(self) -> bool:
        return self.current_state == "pending"

    def can_submit_proposal(self) -> bool:
        return self.current_state == "accepted"

    def can_confirm(self) -> bool:
        return self.current_state == "proposal_review"
