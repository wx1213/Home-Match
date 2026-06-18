"""推送服务 - APNs/FCM 抽象层（[D-014]）。

MVP 阶段：抽象接口 + Mock 实现。
二期：对接 firebase-admin SDK 真正发推送。

provider 选型（C2 引入）：
- 启动时检测 `secrets/firebase-service-account.json` 是否存在
  - 存在 + 解析成功 → FirebasePushProvider（真实 FCM 推送）
  - 否则 → MockPushProvider（仅日志，dev 友好）
- 切换无侵入：仅 push_provider 全局变量变化
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
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


def _select_provider() -> PushProvider:
    """启动时决定用 Firebase 还是 Mock。

    规则（dev 友好）：
    - 凭证文件不存在 → Mock + log warn（让 dev 同学不配也能跑）
    - 凭证存在但 firebase-admin 初始化失败 → Mock + log warn（凭据过期等情况）
    - 都 OK → Firebase

    注意：凭证路径是相对路径（settings 存的是 ./secrets/...），需 resolve 到绝对路径再判断。
    """
    cred_path_str = settings.firebase_credentials_path
    if not cred_path_str:
        logger.info("push: no firebase_credentials_path configured, using Mock")
        return MockPushProvider()

    cred_path = Path(cred_path_str)
    if not cred_path.is_absolute():
        # 相对路径相对于 backend 工作目录（CWD）；resolve 成绝对路径再判断
        cred_path = cred_path.resolve()

    if not cred_path.exists():
        logger.info(
            "push: Firebase credentials not found at %s, using Mock (dev mode)",
            cred_path,
        )
        return MockPushProvider()

    try:
        from .firebase_provider import FirebasePushProvider

        logger.info("push: Firebase provider selected (credentials: %s)", cred_path)
        return FirebasePushProvider(credentials_path=str(cred_path))
    except Exception as e:
        # 凭据文件存在但解析/初始化失败（如 service account 过期、APNs key 未配）
        logger.warning(
            "push: Firebase init failed (%s), falling back to Mock",
            str(e),
        )
        return MockPushProvider()


# 懒加载：模块 import 时不初始化（避免 logging 未配置前 log 被吞）
# 第一次 push 时才选 provider
_push_provider_instance: PushProvider | None = None


def get_push_provider() -> PushProvider:
    """懒加载获取 push provider。第一次调用时选型 + 写 log。"""
    global _push_provider_instance
    if _push_provider_instance is None:
        _push_provider_instance = _select_provider()
    return _push_provider_instance


# 兼容旧引用（push_to_user 内部用）—— 用 property 形式不可行，改为函数调用
# push_provider 仅作为类型注解占位，运行时通过 get_push_provider() 获取
push_provider: PushProvider = MockPushProvider()  # 占位，实际不用


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
        """给用户的所有活跃设备发推送。返回成功数。

        注：push 失败不影响业务 - 任何 provider.send 抛异常都被 catch，
        仅记日志。调用方应保证 push 在 db.commit() 之后调用。
        """
        devices = self.db.scalars(
            select(Device).where(
                Device.user_id == user_id,
                Device.fcm_token.isnot(None),
            )
        ).all()

        success_count = 0
        for device in devices:
            try:
                ok = await get_push_provider().send(
                    token=device.fcm_token,
                    title=title,
                    body=body,
                    data=data or {},
                    priority=priority,
                )
                if ok:
                    success_count += 1
            except Exception as e:
                # C7: FCM token 永久失效（APP 卸载 / token 过期）→ 删 device
                # 用 duck-typing 检查异常类型（避免循环 import InvalidPushTokenError）
                if e.__class__.__name__ == "InvalidPushTokenError":
                    logger.warning(
                        "Invalid FCM token, deleting device",
                        extra={
                            "user_id": user_id,
                            "device_id": device.id,
                            "err": str(e),
                        },
                    )
                    self.db.delete(device)
                    # 关键：device 已被标记删除，跳过后续的 last_active_at 更新
                    continue
                # provider 抛其他异常不能让业务回滚；仅记录
                logger.exception(
                    "push_provider.send failed",
                    extra={"user_id": user_id, "device_id": device.id, "err": str(e)},
                )
            device.last_active_at = datetime.utcnow()

        # last_active_at 持久化（即使 push 全失败也提交）
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

    async def on_invitation_reminder(self, invitation) -> None:
        """邀请即将超时（C3）：通知卖方（还剩 2h 提醒一次）。"""
        # 算剩余时间
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        exp = invitation.expired_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        hours_left = max(0, (exp - now).total_seconds() / 3600)

        await self.service.push_to_user(
            user_id=invitation.seller_id,
            title="⏰ 邀请即将超时",
            body=f"还剩 {hours_left:.1f} 小时，请尽快响应",
            data={"type": "invitation_reminder", "invitation_id": str(invitation.id)},
            priority=PushPriority.HIGH,
        )

    async def on_proposal_reminder(self, invitation) -> None:
        """方案即将超时（C3）：通知买方（还剩 30min 提醒一次）。"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        deadline = invitation.proposal_deadline
        if not deadline:
            return  # 安全兜底
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        minutes_left = max(0, (deadline - now).total_seconds() / 60)

        await self.service.push_to_user(
            user_id=invitation.buyer_id,
            title="⏰ 方案即将超时",
            body=f"还剩 {minutes_left:.0f} 分钟，请尽快确认或拒绝",
            data={"type": "proposal_reminder", "invitation_id": str(invitation.id)},
            priority=PushPriority.HIGH,
        )
