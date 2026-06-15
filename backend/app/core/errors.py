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


class InvalidStateTransitionError(AppError):
    """P1-5: 状态机非法转移（不在 allowed 列表内的状态切换）。"""
    code = 30005
    message = "状态机非法转移"
    http_status = 409


class DuplicateReviewError(AppError):
    code = 30006
    message = "已评价过"
    http_status = 409


class InvitationAlreadyRespondedError(AppError):
    """P1-5: 邀请已被响应（accept/reject/expire），重复操作返 409。"""
    code = 30007
    message = "邀请已被响应"
    http_status = 409


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


class WeChatAuthUnavailableError(AppError):
    """[Sprint1-P0] 微信登录未配置 / mock 兜底被生产禁用。"""

    code = 40004
    message = "微信登录暂不可用"
    http_status = 503


class AppleAuthInvalidTokenError(AppError):
    """[Sprint1-P0] Apple identity_token 验签失败（签名/aud/iss/exp 任一不通过）。"""

    code = 40005
    message = "Apple 身份令牌无效"
    http_status = 401


class DevLoginDisabledError(AppError):
    """[Sprint1-P0] 生产环境禁止 dev login 兜底。"""

    code = 40006
    message = "Dev 登录已禁用"
    http_status = 403


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
                "err_message": exc.message,  # 修复：原 key 'message' 跟 LogRecord 内置字段冲突
                "detail": exc.detail,
            },
        )
        return _error_response(exc.code, exc.message, exc.http_status, exc.detail)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """P1-5 兜底：捕获 transitions.MachineError 等意外异常，避免 5xx。

        注意：这个 handler 只对未被子 handler 捕获的 Exception 兜底；
        AppError 子类仍由 app_error_handler 处理。
        """
        # transitions 库的 MachineError 是状态机非法转移
        exc_module = getattr(exc.__class__, "__module__", "")
        if "transitions" in exc_module and "MachineError" in exc.__class__.__name__:
            logger.warning(
                "StateMachine MachineError caught at global handler",
                extra={"path": request.url.path, "error": str(exc)},
            )
            return _error_response(
                30005, "状态机非法转移", 409, detail={"reason": str(exc)}
            )
        # 其他未知异常：打 ERROR 日志，返 500
        logger.error(
            "Unhandled exception",
            extra={"path": request.url.path, "error": str(exc), "type": exc.__class__.__name__},
        )
        # 修复：原代码 hardcoded 10000 (AppError 基类)，应与 InternalError.code 一致 (10006)
        # 前端按 code 做 case 分支，10006 才是"服务器异常"
        return _error_response(InternalError.code, InternalError.message, InternalError.http_status)

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

    # 注：原代码这里有第二个 `@app.exception_handler(Exception)`，会被 generic 覆盖
    # （starlette handler dict 按 exception_class 索引，后注册覆盖前注册）。
    # generic_exception_handler 已经覆盖了所有 Exception，包括 transitions.MachineError
    # 和未处理异常的兜底（500），不需要再注册一次。
    # 修复：删除冗余 unhandled_exception_handler
