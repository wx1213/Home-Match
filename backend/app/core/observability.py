"""可观测性 — Sentry 集成（[Sprint2-#11]）。

Sentry 是生产环境的错误监控 + APM 工具：
- 自动收集所有未捕获异常
- 性能追踪（APM）：每个请求的 latency + DB 查询时间
- 用户上下文：request_id / user_id 透传到 Sentry dashboard

启用条件：
- ``SENTRY_DSN`` 不为空
- ``app_env=production`` / ``staging``（dev 不上送，避免污染）

降级：
- 没装 ``sentry-sdk[fastapi]`` 时静默跳过（pip install sentry-sdk[fastapi]）
- DSN 为空时跳过
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_initialized = False


def init_sentry() -> None:
    """初始化 Sentry（在 app 启动时调一次）。

    失败也不抛异常 —— 监控层故障不该影响主业务。
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    dsn = settings.sentry_dsn.strip()
    if not dsn:
        logger.info("Sentry DSN not set, skip initialization")
        return

    if settings.is_development:
        # dev 模式不上送（避免污染 Sentry dashboard）
        logger.info("Sentry skipped in development mode")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning(
            "sentry-sdk not installed, run: pip install sentry-sdk[fastapi]"
        )
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.sentry_environment or settings.app_env,
        release=f"homematch-backend@{settings.app_version}",
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # 慢请求 / 错误请求采样
        profiles_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            LoggingIntegration(
                level=None,  # 不接管 logging（我们已经走 JSON 格式了）
                event_level=None,  # 也不自动上送 logging.error（避免重复）
            ),
        ],
        # [Sprint1-P0] 不上送敏感字段
        before_send=_scrub_sensitive,  # type: ignore[arg-type]
    )
    logger.info(
        "Sentry initialized",
        extra={
            "environment": settings.sentry_environment,
            "release": f"homematch-backend@{settings.app_version}",
            "traces_sample_rate": settings.sentry_traces_sample_rate,
        },
    )


def _scrub_sensitive(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """[Sprint1-P0] 上送 Sentry 前先脱敏（不要泄漏 token / phone / body）。

    同步 :class:`app.core.network.log_interceptor` 的字段策略。
    """
    sensitive_keys = {
        "token", "access_token", "refresh_token", "authorization",
        "password", "phone", "phone_encrypted", "phone_hash",
        "openid", "unionid", "id_token", "identity_token",
        "sms_code", "credit_card", "cvv", "pin",
    }
    return _scrub_dict(event, sensitive_keys)


def _scrub_dict(d: dict, sensitive_keys: set[str]) -> dict:
    """递归脱敏 dict 里的敏感字段。"""
    if not isinstance(d, dict):
        return d
    out: dict[str, object] = {}
    for k, v in d.items():
        if isinstance(k, str) and k.lower() in sensitive_keys:
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = _scrub_dict(v, sensitive_keys)
        elif isinstance(v, list):
            out[k] = [_scrub_dict(x, sensitive_keys) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


def set_user_context(user_id: int | None) -> None:
    """[Sprint2-#11] 把 user_id 透传到 Sentry（方便 dashboard 过滤）。"""
    try:
        import sentry_sdk

        if user_id is not None:
            sentry_sdk.set_user({"id": str(user_id)})
        else:
            sentry_sdk.set_user(None)
    except ImportError:
        pass


def capture_exception(error: BaseException, **extra: Any) -> None:
    """手动上送异常到 Sentry（带 extra context）。"""
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for k, v in extra.items():
                scope.set_extra(k, v)
            sentry_sdk.capture_exception(error)
    except ImportError:
        pass
