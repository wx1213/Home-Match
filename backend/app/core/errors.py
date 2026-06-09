from __future__ import annotations

"""统一错误处理 - 业务异常类 + RFC 7807 风格响应。"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """业务异常基类。"""

    code: int = 10000
    message: str = "应用错误"
    http_status: int = status.HTTP_400_BAD_REQUEST
    detail: dict | None = None

    def __init__(
        self,
        message: str | None = None,
        detail: dict | None = None,
    ) -> None:
        if message:
            self.message = message
        if detail:
            self.detail = detail
        super().__init__(self.message)


# ============== 通用错误 ==============

class ValidationError(AppError):
    code = 10001
    message = "参数错误"
    http_status = 400


class NotFoundError(AppError):
    code = 10002
    message = "资源不存在"
    http_status = 404


class PermissionDeniedError(AppError):
    code = 10003
    message = "权限不足"
    http_status = 403


class UnauthorizedError(AppError):
    code = 10004
    message = "未认证"
    http_status = 401


class RateLimitError(AppError):
    code = 10005
    message = "请求过于频繁"
    http_status = 429


class InternalError(AppError):
    code = 10006
    message = "服务器异常"
    http_status = 500


# ============== 认证错误 ==============

class InvalidSmsCodeError(AppError):
    code = 20001
    message = "验证码错误"
    http_status = 401


class SmsCodeExpiredError(AppError):
    code = 20002
    message = "验证码已过期"
    http_status = 401


class InvalidTokenError(AppError):
    code = 20003
    message = "Token 无效"
    http_status = 401


class TokenExpiredError(AppError):
    code = 20004
    message = "Token 已过期"
    http_status = 401


# ============== 业务错误 ==============

class PropertyExistsError(AppError):
    code = 30001
    message = "房源已存在"
    http_status = 409


class InvitationExpiredError(AppError):
    code = 30002
    message = "邀请已超时失效"
    http_status = 410


class CreditScoreTooLowError(AppError):
    code = 30003
    message = "信用分不足"
    http_status = 403


class PropertyFrozenError(AppError):
    code = 30004
    message = "房源已冻结"
    http_status = 403


# ============== 第三方错误 ==============

class SmsSendError(AppError):
    code = 40001
    message = "短信发送失败"
    http_status = 502


class LLMError(AppError):
    code = 40002
    message = "AI 服务异常"
    http_status = 502


class PushError(AppError):
    code = 40003
    message = "推送发送失败"
    http_status = 502


# ============== 全局异常处理器 ==============

def _error_response(
    code: int,
    message: str,
    http_status: int,
    detail: dict | None = None,
) -> JSONResponse:
    """构造统一错误响应。"""
    body: dict = {"code": code, "message": message}
    if detail:
        body["detail"] = detail
    return JSONResponse(status_code=http_status, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.warning(
            "AppError",
            extra={
                "path": request.url.path,
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )
        return _error_response(exc.code, exc.message, exc.http_status, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ):
        logger.warning(
            "ValidationError",
            extra={"path": request.url.path, "errors": exc.errors()},
        )
        return _error_response(
            ValidationError.code,
            "请求参数错误",
            ValidationError.http_status,
            {"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(
            "Unhandled exception",
            extra={"path": request.url.path, "error": str(exc)},
        )
        return _error_response(
            InternalError.code,
            "服务器开小差了",
            InternalError.http_status,
        )
