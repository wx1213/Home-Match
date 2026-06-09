from __future__ import annotations

"""pytest 配置和共享 fixture。

MVP 阶段：测试不依赖真实 PG/Redis，只做单元测试和路由 smoke test。
后续接入 PG 后，加 integration test fixture。
"""

import os

# 强制使用 mock 配置（不依赖真实 DB/Redis/SMS）
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-32-chars-minimum-please-ok")
os.environ.setdefault("SMS_PROVIDER", "mock")
os.environ.setdefault("PHONE_ENCRYPTION_KEY", "base64:dGVzdC1rZXktMzItYnl0ZXMtZm9yLXRlc3Q=")
os.environ.setdefault("PHONE_HASH_KEY", "test-hash-key-for-unit-tests")

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="session")
def app():
    """FastAPI app 实例。"""
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    """同步 TestClient（不依赖真实 DB/Redis）。"""
    # 注意：涉及 DB/Redis 的接口会失败，但基础路由（/, /health, /docs）能用
    with TestClient(app) as c:
        yield c
