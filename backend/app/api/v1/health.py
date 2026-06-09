from __future__ import annotations

"""健康检查接口。"""

from fastapi import APIRouter

from app import __version__
from app.core.config import settings
from app.core.database import check_db_connection
from app.core.redis_client import check_redis_connection
from app.schemas.common import HealthCheckResponse

router = APIRouter(tags=["健康检查"])


@router.get("/health", response_model=HealthCheckResponse, summary="健康检查")
async def health_check() -> HealthCheckResponse:
    """服务健康检查 + 依赖项状态。

    返回:
    - status: ok / degraded / down
    - checks: 各项依赖（db / redis）的健康状态
    """
    db_ok = check_db_connection()
    redis_ok = check_redis_connection()

    if db_ok and redis_ok:
        status_str = "ok"
    elif db_ok or redis_ok:
        status_str = "degraded"
    else:
        status_str = "down"

    return HealthCheckResponse(
        status=status_str,
        version=__version__,
        environment=settings.app_env,
        checks={"database": db_ok, "redis": redis_ok},
    )


@router.get("/", summary="根路径")
async def root() -> dict:
    """根路径 - 服务信息。"""
    return {
        "name": settings.app_name,
        "version": __version__,
        "environment": settings.app_env,
        "docs": "/docs" if settings.docs_enabled else None,
    }
