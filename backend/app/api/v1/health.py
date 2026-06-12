from __future__ import annotations

"""健康检查接口。

3 个端点（[Sprint2-#11]）：

- ``/healthz``  liveness probe（[Sprint2-#11]）
  - **永远 200**，只确认进程活着
  - k8s liveness 用：失败 → 重启 pod
  - 不依赖任何外部组件（即使 PG/Redis 全挂也要能响应）

- ``/readyz``  readiness probe（[Sprint2-#11]）
  - 检查 PG + Redis 联通
  - 任一不通过 → 503（k8s 会从 LB 摘除该 pod）
  - 不查业务（不跑 SQL/不调业务），只 ping

- ``/v1/health``  详细健康（已有，含 status / version / checks）
  - 监控/排障用
"""

from fastapi import APIRouter, Response, status

from app import __version__
from app.core.config import settings
from app.core.database import check_db_connection
from app.core.logging import get_logger
from app.core.redis_client import check_redis_connection
from app.schemas.common import HealthCheckResponse

logger = get_logger(__name__)

router = APIRouter(tags=["健康检查"])


@router.get("/healthz", summary="Liveness probe（[Sprint2-#11] k8s/Docker 用）")
async def liveness() -> dict:
    """Liveness 探针：永远 200。

    不要在这里查 PG/Redis —— 那种应该走 /readyz。
    进程活着就返 200，让 k8s 知道别重启 pod。
    """
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe（[Sprint2-#11]）")
async def readiness(response: Response) -> dict:
    """Readiness 探针：检查 PG + Redis 联通。

    k8s 配 readinessProbe.httpGet.path=/readyz
    成功 → pod 加进 Service endpoints（接收流量）
    失败 → pod 从 Service 摘除（停止接收流量，但 pod 不重启）
    """
    db_ok = check_db_connection()
    redis_ok = check_redis_connection()

    if db_ok and redis_ok:
        return {"status": "ready", "database": True, "redis": True}

    # 不通过 → 503，让 LB/k8s 摘除
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    logger.warning(
        "Readiness check failed",
        extra={"database": db_ok, "redis": redis_ok},
    )
    return {
        "status": "not_ready",
        "database": db_ok,
        "redis": redis_ok,
    }


@router.get("/health", response_model=HealthCheckResponse, summary="详细健康检查")
async def health_check() -> HealthCheckResponse:
    """详细健康检查 + 依赖项状态。

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
