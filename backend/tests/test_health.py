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
    """短信验证码 - 手机号格式校验。

    P1-1 修复：用 conftest.py 注入的 _InMemorySmsService 替代真实 Redis，
    避免「环境有时 Redis 在跑就过，没跑就 fail」的不稳定状态。
    """
    # 错误格式 → 400 (ValidationError)
    resp = client.post(
        "/v1/auth/sms-code",
        json={"phone": "123", "purpose": "login"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 10001  # ValidationError

    # 正确格式 → 200（P1-1: 永远 200，因为 SmsService 是 in-memory 替身）
    resp = client.post(
        "/v1/auth/sms-code",
        json={"phone": "13800138000", "purpose": "login"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["code"] == 0
    assert "expire_in" in data["data"]
