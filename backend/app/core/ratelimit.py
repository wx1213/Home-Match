"""限流 - slowapi（基于 IP / 用户）。

MVP 阶段：使用内存存储，避免依赖 Redis（Redis 不可用时不影响接口）。
二期：可切到 Redis 存储做分布式限流。
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# 限流器 - 用内存存储（生产可改 redis://...）
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    storage_uri="memory://",  # MVP 用内存，避免依赖 Redis
    strategy="fixed-window",
    headers_enabled=True,
)


def get_limiter() -> Limiter:
    """获取限流器单例。"""
    return limiter
