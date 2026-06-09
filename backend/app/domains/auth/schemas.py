from __future__ import annotations

"""Auth 域的请求/响应模型。"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============== 短信验证码 ==============


class SmsCodeRequest(BaseModel):
    """发送短信验证码请求。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {"phone": "13800138000", "purpose": "login"}
    })

    phone: str = Field(..., description="手机号（11位，1开头）")
    purpose: Literal["login", "bind_phone"] = Field(
        default="login", description="用途：login 登录 / bind_phone 绑定手机号"
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """校验手机号格式。"""
        v = v.strip()
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class SmsCodeResponse(BaseModel):
    """发送短信验证码响应。"""

    expire_in: int = Field(..., description="验证码有效期（秒）")
    # 注意：永远不要在响应里返回验证码本身！


# ============== 短信登录 ==============


class SmsLoginRequest(BaseModel):
    """短信验证码登录请求。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {"phone": "13800138000", "sms_code": "1234"}
    })

    phone: str = Field(..., description="手机号")
    sms_code: str = Field(..., min_length=4, max_length=6, description="短信验证码")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


# ============== 微信登录 ==============


class WechatLoginRequest(BaseModel):
    """微信登录请求（v0.4：主登录方式）。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {"code": "wx_code_from_sdk", "app_id": "test_app_id"}
    })

    code: str = Field(..., description="微信 OAuth code（前端 SDK 拿到）")
    app_id: str | None = Field(default=None, description="AppID（可选；测试时填测试号）")


# ============== Apple 登录 ==============


class AppleLoginRequest(BaseModel):
    """Apple 登录请求（iOS 必选）。"""

    model_config = ConfigDict(json_schema_extra={
        "example": {"identity_token": "eyJraWQ...", "user_info": {"name": {"firstName": "张"}}}
    })

    identity_token: str = Field(..., description="Apple identity_token (JWT)")
    user_info: dict | None = Field(default=None, description="Apple userInfo（仅首次登录返回）")


# ============== Token 刷新 ==============


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求。"""

    refresh_token: str = Field(..., description="Refresh token")


# ============== 统一登录响应 ==============


class UserInfo(BaseModel):
    """用户信息（登录响应中返回）。"""

    id: int
    name: str
    display_name: str | None
    avatar_url: str | None
    phone_mask: str | None = Field(default=None, description="脱敏手机号")
    credit_score: float
    is_new: bool = Field(default=False, description="是否新注册用户")
    is_verified: bool = Field(default=False, description="是否完成资质审核")


class TokenPair(BaseModel):
    """Token 组合。"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(..., description="access_token 有效期（秒）")


class LoginResponse(BaseModel):
    """登录响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserInfo
