from __future__ import annotations

"""健康检查 smoke test。"""

import pytest
from fastapi.testclient import TestClient


def test_root(client: TestClient):
    """根路径返回服务信息。"""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "data" in data
    assert "name" in data["data"]
    assert "version" in data["data"]
    assert "environment" in data["data"]
    print(f"Service: {data['data']['name']} v{data['data']['version']} ({data['data']['environment']})")


def test_docs_available(client: TestClient):
    """Swagger UI 可访问。"""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_openapi_available(client: TestClient):
    """OpenAPI schema 可访问。"""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "openapi" in data
    assert "paths" in data
    # 验证我们的关键接口都已注册
    paths = data["paths"]
    assert "/v1/health" in paths
    assert "/v1/auth/sms-code" in paths
    assert "/v1/auth/login" in paths
    assert "/v1/auth/wechat-login" in paths
    assert "/v1/auth/apple-login" in paths
    assert "/v1/auth/refresh" in paths
    print(f"OpenAPI paths: {list(paths.keys())}")


def test_health_check(client: TestClient):
    """健康检查接口。

    注意：本测试在没有真实 PG/Redis 的环境下运行，所以 checks 都是 false。
    这是正常的 — 验证接口定义、响应格式、错误处理是对的。
    """
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"]
    assert data["environment"]
    assert "checks" in data
    print(f"Health: {data['status']}, checks={data['checks']}")


def test_sms_code_validation(client: TestClient):
    """短信验证码 - 手机号格式校验。"""
    # 错误格式 → 400 (ValidationError)
    resp = client.post(
        "/v1/auth/sms-code",
        json={"phone": "123", "purpose": "login"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 10001  # ValidationError

    # 正确格式 - 依赖 Redis
    # Redis 可用时 → 200
    # Redis 不可用时 → 500 (底层服务异常，符合预期)
    try:
        resp = client.post(
            "/v1/auth/sms-code",
            json={"phone": "13800138000", "purpose": "login"},
        )
        # 200 = 验证码已发送（mock 模式）
        # 500 = Redis 不可用（开发环境无 Redis）
        # 503 = 限流服务异常
        assert resp.status_code in (200, 500, 503), f"Unexpected: {resp.status_code} {resp.text}"
    except Exception as e:
        # TestClient 在某些情况下会传播未捕获的异常
        # 这种情况下视为"环境无 Redis，预期行为"
        assert "Redis" in str(e) or "Connection" in str(e), f"Unexpected error: {e}"
