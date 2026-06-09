"""FastAPI 应用主入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import (
    AppError,
    InternalError,
    ValidationError,
    _error_response,
)
from app.core.logging import get_logger, setup_logging
from app.core.ratelimit import limiter
from app.core.redis_client import redis_client
from app.schemas.common import APIResponse

logger = get_logger(__name__)


# ============== 慢 API 限流异常处理 ==============

async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """限流异常处理。"""
    logger.warning(
        "Rate limit exceeded",
        extra={"path": request.url.path, "limit": str(exc.detail)},
    )
    return JSONResponse(
        status_code=429,
        content={"code": 10005, "message": "请求过于频繁", "detail": str(exc.detail)},
    )


# ============== 应用生命周期 ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期。"""
    setup_logging()
    logger.info(
        "Starting HomeMatch backend",
        extra={"env": settings.app_env, "version": __version__, "debug": settings.app_debug},
    )
    try:
        redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis not available (running degraded): {e}")

    app.state.redis = redis_client
    yield
    logger.info("Shutting down HomeMatch backend")


# ============== 工厂函数 ==============

def create_app() -> FastAPI:
    """工厂函数：创建 FastAPI 应用。"""
    app = FastAPI(
        title=f"{settings.app_name} API",
        description="""
# Home Match 后端 API

北京二手房独立经纪人撮合评价平台（MVP v0.4）。

## 核心业务闭环

需求发布 → AI 推荐 Top 5 → 发起邀请 → 卖方接单 → 提交方案 → 买方确认 → 握手 → 互评 → 信用分更新

## 角色与权限

- **每个用户可以同时是买方和卖方**
- 状态机驱动的邀请/合作生命周期
- 信用分 = 评价均分 × 20 × 活跃系数（6-100 分）

## 认证

所有 `/v1/*` 接口（除 `/auth/*` 和 `/users/dev-identities` 外）需要在 Header 携带：
```
Authorization: Bearer <access_token>
```

401 → token 过期，APP 端会自动跳登录。

## 接口分组

- **认证** (`/auth/*`)：微信登录、短信登录、Token 刷新
- **用户** (`/users/*`)：个人信息、业务统计、公开名片
- **需求** (`/demands/*`)：需求 CRUD + AI 推荐
- **房源** (`/properties/*`)：房源 CRUD
- **邀请** (`/invitations/*`)：邀请生命周期
- **合作方案** (`/invitations/{id}/proposal`)：卖方提交方案
- **合作** (`/cooperations/*`)：合作主记录
- **评价** (`/cooperations/{id}/review`)：合作评价
- **设备** (`/devices/*`)：推送设备注册
- **AI 能力** (`/ai/*`)：AI 评价异常检测、方案生成
- **健康检查** (`/health`)：服务健康

详见左侧 Tags 树。
        """.strip(),
        version=__version__,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    # === CORS ===
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # === 限流器（注册到 app.state，但暂不挂 middleware，避免 Pydantic 校验冲突） ===
    # 限流逻辑下沉到 SmsService 内部（MVP 阶段）
    # 二期如果加全局限流，再启用 SlowAPIMiddleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # === 业务异常处理 ===
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        # 注意：extra 不能用 'message'（LogRecord 保留字段）
        logger.warning(
            "AppError",
            extra={"path": request.url.path, "code": exc.code, "error_message": exc.message},
        )
        return _error_response(exc.code, exc.message, exc.http_status, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # 用 jsonable_encoder 处理 ValueError 等不可序列化的对象
        return _error_response(
            ValidationError.code,
            "请求参数错误",
            ValidationError.http_status,
            {"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return _error_response(10000 + exc.status_code, exc.detail or "HTTP 错误", exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """最后兜底。"""
        logger.exception(
            "Unhandled exception",
            extra={"path": request.url.path, "error": str(exc)},
        )
        return _error_response(
            InternalError.code,
            "服务器开小差了",
            InternalError.http_status,
        )

    # === 路由 ===
    app.include_router(api_router)

    # === 根路径 ===
    @app.get("/", response_model=APIResponse, tags=["元信息"], summary="服务信息")
    async def root():
        return APIResponse(
            data={
                "name": settings.app_name,
                "version": __version__,
                "environment": settings.app_env,
                "docs": "/docs" if settings.docs_enabled else None,
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )
