from __future__ import annotations

"""Redis 客户端 - 用于缓存、倒计时、限流、任务队列。"""

import redis

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
