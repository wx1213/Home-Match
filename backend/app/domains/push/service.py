"""推送服务 - APNs/FCM 抽象层（[D-014]）。

MVP 阶段：抽象接口 + Mock 实现。
二期：对接 firebase-admin SDK 真正发推送。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.device import Device

logger = get_logger(__name__)


class PushPriority(str, Enum):
    """推送优先级。"""

    HIGH = "high"  # 通知栏立即弹出
    NORMAL = "normal"  # 通知栏
    LOW = "low"  # 静默数据消息


class PushProvider(ABC):
    """推送提供者抽象基类。"""

    @abstractmethod
    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict | None = None,
        priority: PushPriority = PushPriority.NORMAL,
    ) -> bool:
        """发送单条推送。返回是否成功。"""
        ...


class MockPushProvider(PushProvider):
    """Mock 推送（开发/测试用，只打日志不发真消息）。"""

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict | None = None,
        priority: PushPriority = PushPriority.NORMAL,
    ) -> bool:
        logger.info(
            "[MOCK PUSH]",
            extra={
                "token": token[:20] + "...",
                "title": title,
                "body": body,
                "data": data,
                "priority": priority.value,
            },
        )
        return True


# MVP 用 mock，二期换成 FirebasePushProvider
push_provider: PushProvider = MockPushProvider()


class PushService:
    """推送服务 - 给指定用户的所有设备发推送。"""

    def __init__(self, db: Session):
        self.db = db

    async def push_to_user(
        self,
        user_id: int,
        title: str,
        body: str,
        data: dict | None = None,
        priority: PushPriority = PushPriority.NORMAL,
    ) -> int:
        """给用户的所有活跃设备发推送。返回成功数。"""
        devices = self.db.scalars(
            select(Device).where(
                Device.user_id == user_id,
                Device.fcm_token.isnot(None),
            )
        ).all()

        success_count = 0
        for device in devices:
            ok = await push_provider.send(
                token=device.fcm_token,
                title=title,
                body=body,
                data=data or {},
                priority=priority,
            )
            if ok:
                success_count += 1
            device.last_active_at = datetime.utcnow()

        self.db.commit()
        logger.info(
            "Push sent to user",
            extra={"user_id": user_id, "devices": len(devices), "success": success_count},
        )
        return success_count


# ============== 业务事件触发器 ==============


class PushTriggers:
    """关键业务事件 → 推送触发。"""

    def __init__(self, db: Session):
        self.service = PushService(db)

    async def on_new_invitation(self, invitation) -> None:
        """新邀请：通知卖方。"""
        await self.service.push_to_user(
            user_id=invitation.seller_id,
            title="📩 收到新的合作邀请",
            body="有经纪人邀请您合作，请于 24 小时内响应",
            data={"type": "new_invitation", "invitation_id": str(invitation.id)},
            priority=PushPriority.HIGH,
        )

    async def on_invitation_accepted(self, invitation) -> None:
        """卖方接单：通知买方。"""
        await self.service.push_to_user(
            user_id=invitation.buyer_id,
            title="✅ 卖方已接单",
            body="请等待对方提交合作方案（2 小时内）",
            data={"type": "invitation_accepted", "invitation_id": str(invitation.id)},
        )

    async def on_proposal_submitted(self, invitation) -> None:
        """方案提交：通知买方。"""
        await self.service.push_to_user(
            user_id=invitation.buyer_id,
            title="📋 收到合作方案",
            body="请查看并确认或拒绝",
            data={"type": "proposal_submitted", "invitation_id": str(invitation.id)},
            priority=PushPriority.HIGH,
        )

    async def on_handshake(self, cooperation) -> None:
        """握手成功：通知双方。"""
        for uid in (cooperation.buyer_id, cooperation.seller_id):
            await self.service.push_to_user(
                user_id=uid,
                title="🤝 合作已建立",
                body="合作 ID: COOP-" + str(cooperation.id),
                data={"type": "handshaked", "cooperation_id": str(cooperation.id)},
            )
