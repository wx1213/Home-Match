"""Firebase Admin SDK 推送 provider（[D-014] 走 FCM 统一通道）。

FCM 同时管 iOS (APNs) + Android (FCM)：
- iOS: FCM 后台转发到 APNs（需要在 Firebase 控制台上传 APNs Auth Key）
- Android: FCM 直发

Firebase Admin SDK 初始化在模块级一次性完成（firebase_admin 会维护全局 app instance），
失败时上抛异常，由 service.py 的 _select_provider() 捕获并 fallback 到 Mock。
"""
from __future__ import annotations

from app.core.logging import get_logger

from .service import PushPriority, PushProvider

logger = get_logger(__name__)

# 标记 firebase 是否初始化成功（service.py 用此判断 provider 类型）
_initialized: bool = False


class InvalidPushTokenError(Exception):
    """推送 token 永久失效（APP 卸载 / token 过期 / token 格式错）。

    C7 在 push_to_user 内捕获此异常并删除 device 行。
    不继承 AppError - 这是内部信号，不应被 FastAPI 全局 handler 转成 HTTP 响应。
    """

    pass


class FirebasePushProvider(PushProvider):
    """基于 firebase-admin SDK 的 FCM 推送。"""

    def __init__(self, credentials_path: str):
        """初始化 firebase_admin + 持有 messaging 句柄。

        Args:
            credentials_path: Firebase service account JSON 绝对路径
        """
        global _initialized
        # 延迟 import：避免在没装 firebase-admin 的环境 import 失败
        from firebase_admin import credentials, initialize_app, messaging  # type: ignore[import-not-found]

        if not _initialized:
            cred = credentials.Certificate(credentials_path)
            # name 参数避免与 firebase 默认 app 冲突
            initialize_app(cred, name="homematch-push")
            _initialized = True
        self._messaging = messaging

    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: dict | None = None,
        priority: PushPriority = PushPriority.NORMAL,
    ) -> bool:
        """发推送。返回 True 成功 / False 失败（业务失败，不抛回上层）。

        异常：
            InvalidPushTokenError: token 永久失效（NotRegistered / InvalidArgument）
                - 上层（C7）会捕获并删除 device
        """
        fcm_priority = "high" if priority == PushPriority.HIGH else "normal"
        apns_priority = "10" if priority == PushPriority.HIGH else "5"

        # data 必须是 str 映射（FCM API 限制）
        data_str = {k: str(v) for k, v in (data or {}).items()}

        message = self._messaging.Message(
            token=token,
            notification=self._messaging.Notification(title=title, body=body),
            data=data_str,
            android=self._messaging.AndroidConfig(priority=fcm_priority),
            apns=self._messaging.APNSConfig(
                headers={"apns-priority": apns_priority},
                payload=self._messaging.APNSPayload(
                    aps=self._messaging.Aps(sound="default"),
                ),
            ),
        )
        try:
            message_id = self._messaging.send(message)
            logger.info(
                "FCM sent",
                extra={"message_id": message_id, "token": token[:20] + "..."},
            )
            return True
        except self._messaging.UnregisteredError as e:
            logger.warning(
                "FCM token unregistered",
                extra={"token": token[:20] + "...", "err": str(e)},
            )
            raise InvalidPushTokenError("FCM token unregistered") from e
        except self._messaging.InvalidArgumentError as e:
            logger.warning(
                "FCM invalid argument",
                extra={"token": token[:20] + "...", "err": str(e)},
            )
            raise InvalidPushTokenError("FCM token invalid") from e
        except Exception as e:
            # 其他失败（网络 / 配额）—— 返 False 让业务继续
            logger.exception(
                "FCM send failed",
                extra={"token": token[:20] + "...", "err": str(e)},
            )
            return False


def is_firebase_initialized() -> bool:
    """供 service.py 检查 provider 类型。"""
    return _initialized
