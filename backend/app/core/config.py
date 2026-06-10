from __future__ import annotations

"""应用配置 - 基于 pydantic-settings。

所有环境变量通过 Settings 单例注入，禁止硬编码。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === 运行模式 ===
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_name: str = "HomeMatch"
    app_version: str = "0.1.0"

    # === 服务 ===
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_base_url: str = "http://localhost:8000"

    # === 日志 ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # === CORS ===
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # === PostgreSQL ===
    database_url: str = "postgresql://homa:devpass@localhost:5432/homa"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_echo: bool = False

    # === Redis ===
    redis_url: str = "redis://localhost:6379/0"

    # === JWT ===
    jwt_secret: str = "dev-secret-change-in-prod-please-32-chars-min"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 120  # 2h
    jwt_refresh_token_expire_days: int = 30  # 30d

    # === 加密（手机号 AES-256-GCM） ===
    phone_encryption_key: str = "base64:Y2hhbmdlLW1lLXRoaXMtaXMtMzItYnl0ZS1iYXNlNjQ="
    phone_hash_key: str = "change-me-to-another-random-string-for-hmac"

    # === 短信（阿里云） ===
    sms_provider: Literal["aliyun", "mock"] = "mock"  # MVP 默认 mock
    sms_access_key_id: str = ""
    sms_access_key_secret: str = ""
    sms_sign_name: str = "HomeMatch"
    sms_template_code: str = "SMS_123456789"
    sms_mock_code: str = "1234"  # 测试时所有验证码都是这个

    # === 微信登录 ===
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_test_app_id: str = ""
    wechat_test_app_secret: str = ""

    # === Apple 登录 ===
    apple_client_id: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key_path: str = "./secrets/apple_key.p8"

    # === 推送 ===
    firebase_credentials_path: str = "./secrets/firebase-service-account.json"
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_key_path: str = "./secrets/apns_key.p8"
    apns_bundle_id: str = "cn.hmatch.app"

    # === OSS ===
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = "oss-cn-beijing.aliyuncs.com"
    oss_bucket: str = "hmatch-dev"
    oss_sts_role_arn: str = ""

    # === 文件上传（P0：房源/头像）===
    # 模式：local（开发，存到本地目录） / oss（生产，存到阿里云 OSS）
    upload_mode: Literal["local", "oss"] = "local"
    # 本地模式：上传目录（绝对路径；不存在自动建）
    upload_dir: str = "./uploads"
    # OSS 模式：CDN 域名（用于拼接 URL；空字符串走 oss_endpoint）
    upload_cdn_base: str = ""
    # 限制：单文件最大 8MB（与 APP 端压缩后大小匹配）
    max_upload_size_mb: int = 8
    # 允许的 MIME 类型（白名单）
    upload_allowed_types: list[str] = Field(
        default_factory=lambda: ["image/jpeg", "image/png", "image/webp", "image/heic"]
    )

    # === LLM ===
    llm_provider: Literal["deepseek", "claude", "openai", "minimax"] = "minimax"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimaxi.com"
    minimax_group_id: str = ""
    llm_soft_cap: int = 2000  # ¥/月
    llm_hard_cap: int = 5000  # ¥/月

    # === Sentry ===
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1

    # === 限流 ===
    rate_limit_default: str = "60/minute"
    rate_limit_auth_sms: str = "5/minute"
    rate_limit_auth_login: str = "10/minute"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """支持 JSON 字符串或列表。"""
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        """生产环境禁用 Swagger UI。"""
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    """单例获取配置。"""
    return Settings()


# 全局快捷访问
settings = get_settings()
