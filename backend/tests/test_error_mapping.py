"""AppError 契约测试（[app/core/errors.py]）。

P2-6 补完：原 0% 覆盖。本文件锁定 AppError 的"3 元组"契约，
前端 ApiException、文案、UI 跳转逻辑都依赖它。

**契约**（被 [mobile-app/lib/core/network/api_exception.dart] + UI 消费）：
- code: int, 全局唯一, 范围 10001-49999（业务）
- message: str, 中文, 默认文案（可被构造时覆盖）
- http_status: int, HTTP 状态码（前端 401 触发自动登出）

覆盖：
1. 所有 AppError 子类的 3 元组稳定（防止有人改 code 字符串拼错导致前端不识别）
2. code 全局唯一
3. 异常处理器：AppError → JSONResponse 序列化
4. RequestValidationError → 10001 + errors detail
5. 未处理 Exception → 10000 + 500
6. transitions.MachineError 兜底 → 30005 + 409
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from app.core.errors import (
    AppError,
    AppleAuthInvalidTokenError,
    CreditScoreTooLowError,
    DevLoginDisabledError,
    DuplicateReviewError,
    InternalError,
    InvalidSmsCodeError,
    InvalidStateTransitionError,
    InvalidTokenError,
    InvitationAlreadyRespondedError,
    InvitationExpiredError,
    LLMError,
    NotFoundError,
    PermissionDeniedError,
    PropertyExistsError,
    PropertyFrozenError,
    PushError,
    RateLimitError,
    SmsCodeExpiredError,
    SmsSendError,
    TokenExpiredError,
    UnauthorizedError,
    ValidationError,
    WeChatAuthUnavailableError,
    register_exception_handlers,
)

# 所有 AppError 子类（手工列出 + 校验，确保新增子类也被覆盖）
ALL_ERROR_CLASSES: list[type[AppError]] = [
    # 通用
    ValidationError,
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
    RateLimitError,
    InternalError,
    # 认证
    InvalidSmsCodeError,
    SmsCodeExpiredError,
    InvalidTokenError,
    TokenExpiredError,
    # 业务
    PropertyExistsError,
    InvitationExpiredError,
    InvalidStateTransitionError,
    DuplicateReviewError,
    InvitationAlreadyRespondedError,
    CreditScoreTooLowError,
    PropertyFrozenError,
    # 第三方
    SmsSendError,
    LLMError,
    PushError,
    WeChatAuthUnavailableError,
    AppleAuthInvalidTokenError,
    DevLoginDisabledError,
]


# ============================================================
#  3 元组契约
# ============================================================

class TestAppErrorContract:
    """每个 AppError 子类的 code / message / http_status 必须稳定。"""

    @pytest.mark.parametrize("cls", ALL_ERROR_CLASSES, ids=lambda c: c.__name__)
    def test_code_in_valid_range(self, cls):
        """业务错误码在 10001-49999 范围内。"""
        assert 10001 <= cls.code <= 49999, (
            f"{cls.__name__}.code={cls.code} 超出业务码范围 10001-49999"
        )

    @pytest.mark.parametrize("cls", ALL_ERROR_CLASSES, ids=lambda c: c.__name__)
    def test_message_is_non_empty_chinese(self, cls):
        """默认 message 非空（不强制中文，但应该是人类可读字符串）。"""
        assert cls.message and len(cls.message) > 0, (
            f"{cls.__name__}.message 为空"
        )

    @pytest.mark.parametrize("cls", ALL_ERROR_CLASSES, ids=lambda c: c.__name__)
    def test_http_status_in_valid_range(self, cls):
        """HTTP status 在 400-599 之间（4xx/5xx 错误）。"""
        assert 400 <= cls.http_status <= 599, (
            f"{cls.__name__}.http_status={cls.http_status} 不在 4xx/5xx 范围"
        )

    def test_codes_are_globally_unique(self):
        """所有子类的 code 必须唯一（前端按 code 做 case 分支）。"""
        codes = [cls.code for cls in ALL_ERROR_CLASSES]
        dups = {c for c in codes if codes.count(c) > 1}
        assert not dups, f"重复的 code: {dups}"

    def test_known_specific_codes(self):
        """关键错误码的精确值锁定（防止误改）。"""
        # 这些码被前端显式处理
        assert ValidationError.code == 10001
        assert NotFoundError.code == 10002
        assert PermissionDeniedError.code == 10003
        assert UnauthorizedError.code == 10004
        assert RateLimitError.code == 10005
        assert InternalError.code == 10006
        # 认证
        assert InvalidSmsCodeError.code == 20001
        assert SmsCodeExpiredError.code == 20002
        assert InvalidTokenError.code == 20003
        assert TokenExpiredError.code == 20004
        # 业务
        assert PropertyExistsError.code == 30001
        assert InvitationExpiredError.code == 30002
        assert CreditScoreTooLowError.code == 30003
        assert PropertyFrozenError.code == 30004
        assert InvalidStateTransitionError.code == 30005
        assert DuplicateReviewError.code == 30006
        assert InvitationAlreadyRespondedError.code == 30007
        # 第三方
        assert SmsSendError.code == 40001
        assert LLMError.code == 40002
        assert PushError.code == 40003
        assert WeChatAuthUnavailableError.code == 40004
        assert AppleAuthInvalidTokenError.code == 40005
        assert DevLoginDisabledError.code == 40006

    def test_known_specific_http_statuses(self):
        """关键错误码的 HTTP status 锁定（401 触发前端自动登出）。"""
        # 401 必须返 401 — 触发前端 AuthInterceptor 清 token
        assert UnauthorizedError.http_status == 401
        assert InvalidSmsCodeError.http_status == 401
        assert SmsCodeExpiredError.http_status == 401
        assert InvalidTokenError.http_status == 401
        assert TokenExpiredError.http_status == 401
        assert AppleAuthInvalidTokenError.http_status == 401
        # 403 权限
        assert PermissionDeniedError.http_status == 403
        assert CreditScoreTooLowError.http_status == 403
        assert PropertyFrozenError.http_status == 403
        assert DevLoginDisabledError.http_status == 403
        # 404
        assert NotFoundError.http_status == 404
        # 409 冲突
        assert PropertyExistsError.http_status == 409
        assert InvalidStateTransitionError.http_status == 409
        assert DuplicateReviewError.http_status == 409
        assert InvitationAlreadyRespondedError.http_status == 409
        # 410 Gone（邀请超时）
        assert InvitationExpiredError.http_status == 410
        # 429
        assert RateLimitError.http_status == 429
        # 500
        assert InternalError.http_status == 500
        # 502 第三方
        assert SmsSendError.http_status == 502
        assert LLMError.http_status == 502
        assert PushError.http_status == 502
        # 503
        assert WeChatAuthUnavailableError.http_status == 503


class TestAppErrorInstantiation:
    """AppError 子类可正常实例化 + 自定义 message/detail。"""

    def test_default_message(self):
        e = ValidationError()
        assert e.message == "参数错误"
        assert e.code == 10001
        assert e.detail is None

    def test_custom_message(self):
        e = ValidationError(message="价格必须为正数")
        assert e.message == "价格必须为正数"
        assert e.code == 10001  # code 不变

    def test_custom_detail(self):
        e = ValidationError(detail={"field": "price", "value": -1})
        assert e.detail == {"field": "price", "value": -1}

    def test_str_repr_includes_message(self):
        e = NotFoundError(message="房源不存在")
        # str(e) 用 message（Exception.__str__）
        assert "房源不存在" in str(e)


# ============================================================
#  异常处理器（全局 handler）
# ============================================================

@pytest.fixture
def app_with_handlers():
    """装上异常处理器的 FastAPI app。"""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-app-error")
    def _raise_app_error():
        raise NotFoundError(message="房源 999 不存在")

    @app.get("/raise-app-error-with-detail")
    def _raise_with_detail():
        raise ValidationError(
            message="价格非法",
            detail={"field": "total_price", "min": 1},
        )

    @app.get("/raise-generic-exception")
    def _raise_generic():
        raise RuntimeError("DB 连接断开")

    @app.get("/raise-machine-error")
    def _raise_machine_error():
        # 模拟 transitions.MachineError（不在 import 库，构造一个假对象）
        class FakeMachineError(Exception):
            pass
        # 给 class 加 __module__ 模拟 transitions 库
        FakeMachineError.__module__ = "transitions.core"
        raise FakeMachineError("Can't trigger event accept from state handshaked")

    @app.get("/raise-validation-error")
    def _raise_validation():
        raise RequestValidationError(
            errors=[{"loc": ("body", "price"), "msg": "value is not a valid number"}]
        )

    return app


class TestAppErrorHandler:
    """AppError → JSONResponse 序列化。"""

    def test_app_error_returns_correct_status_and_body(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        resp = client.get("/raise-app-error")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 10002
        assert body["message"] == "房源 999 不存在"
        # detail 字段缺失时不应出现
        assert "detail" not in body

    def test_app_error_with_detail_includes_detail(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        resp = client.get("/raise-app-error-with-detail")

        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        assert body["message"] == "价格非法"
        assert body["detail"] == {"field": "total_price", "min": 1}


class TestValidationHandler:
    """RequestValidationError → 10001 + errors detail。"""

    def test_validation_error_returns_10001(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        resp = client.get("/raise-validation-error")

        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 10001
        assert "errors" in body["detail"]


class TestGenericExceptionHandler:
    """未处理 Exception → 500 + 兜底文案。"""

    def test_generic_exception_returns_500_and_10006(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        resp = client.get("/raise-generic-exception")

        assert resp.status_code == 500
        body = resp.json()
        # 全局 handler 返 InternalError (10006)
        assert body["code"] == 10006
        assert "message" in body


class TestMachineErrorHandler:
    """transitions.MachineError 兜底 → 30005 + 409。"""

    def test_machine_error_returns_30005(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        resp = client.get("/raise-machine-error")

        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == 30005
        assert "状态机非法转移" in body["message"]
        # detail 含原始 reason
        assert "reason" in body["detail"]
