from __future__ import annotations

"""Redis 客户端 - 用于缓存、倒计时、限流、任务队列。"""

import redis
import redis.exceptions

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Redis 客户端单例
redis_client: redis.Redis = redis.from_url(
    settings.redis_url,
    decode_responses=True,  # 自动 decode 为 str
    socket_connect_timeout=5,
    socket_keepalive=True,
    health_check_interval=30,
)


def get_redis() -> redis.Redis:
    """FastAPI 依赖：获取 Redis 客户端。"""
    return redis_client


def check_redis_connection() -> bool:
    """健康检查：Redis 是否连通。"""
    try:
        redis_client.ping()
        return True
    except Exception as e:
        logger.error("Redis connection check failed", extra={"error": str(e)})
        return False


# ============== 优雅降级 helpers（P1-4）==============
# 某些场景（推荐缓存、LLM 计数）希望 Redis 不可用时回退到内存/规则，
# 而不是 5xx。safe_get / safe_setex 集中处理异常，调用方不需要 try/except。

def safe_get(key: str) -> str | None:
    """读 Redis；连接失败时返 None，调用方按「无缓存」处理。

    仅捕获 ConnectionError / TimeoutError（Redis 不可用场景）；
    其他异常（语法错等）原样抛出。
    """
    try:
        value = redis_client.get(key)
        return value.decode() if isinstance(value, bytes) else value
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.warning(
            "Redis GET failed, degrading to no-cache",
            extra={"key": key, "error": str(e)},
        )
        return None


def safe_setex(key: str, ttl_seconds: int, value: str) -> bool:
    """写 Redis（带 TTL）；连接失败时返 False，调用方不视为错误。

    返回 True 表示成功写缓存；False 表示 Redis 不可用但不影响主流程。
    """
    try:
        redis_client.setex(key, ttl_seconds, value)
        return True
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.warning(
            "Redis SETEX failed, skipping cache",
            extra={"key": key, "error": str(e)},
        )
        return False


# ============== 常用 key 工具 ==============

def sms_code_key(phone_hash: str, purpose: str) -> str:
    """短信验证码 key: sms:code:{phone_hash}:{purpose}"""
    return f"sms:code:{phone_hash}:{purpose}"


def sms_rate_limit_key(phone_hash: str) -> str:
    """短信发送频率限制 key: sms:rate:{phone_hash}"""
    return f"sms:rate:{phone_hash}"


def invitation_countdown_key(invitation_id: int) -> str:
    """邀请倒计时 key: invitation:countdown:{id}"""
    return f"invitation:countdown:{invitation_id}"


def recommendation_cache_key(demand_id: int) -> str:
    """推荐结果缓存 key: recommendation:demand:{id}"""
    return f"recommendation:demand:{demand_id}"


def rate_limit_key(identifier: str, endpoint: str) -> str:
    """限流 key: ratelimit:{identifier}:{endpoint}"""
    return f"ratelimit:{identifier}:{endpoint}"
