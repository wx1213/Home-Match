from __future__ import annotations

"""通用 schema - 响应包装、分页、错误体。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一成功响应。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


class APIError(BaseModel):
    """统一错误响应。"""

    code: int
    message: str
    detail: dict | None = None


class PaginationMeta(BaseModel):
    """分页元数据。"""

    next_cursor: str | None = None
    has_more: bool = False
    total: int | None = None  # MVP 阶段可不返回精确 total（成本高）


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应。"""

    code: int = 0
    message: str = "ok"
    data: list[T] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


class HealthCheckResponse(BaseModel):
    """健康检查响应。"""

    status: str  # ok | degraded | down
    version: str
    environment: str
    checks: dict[str, bool]  # {"database": true, "redis": true}
