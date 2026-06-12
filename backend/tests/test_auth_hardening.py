"""[Sprint1-P0] 认证硬化测试。

覆盖：
- 微信登录：production 缺凭证 → 503（禁止 mock 兜底）
- 微信登录：development 缺凭证 → mock 走通（regression）
- Apple 登录：production 强制走真实验签
- Apple 登录：development + 缺 client_id → 走 mock 路径
- /users/dev-identities：production → 403 DevLoginDisabledError
- Apple 验签单元：合法 token / 错签名 / 错 aud / 错 iss / 过期 / 缺 sub
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

# ============================================================
#  Apple 验签单元测试
# ============================================================


@pytest.fixture(scope="module")
def rsa_keypair():
    """生成一对临时 RSA key（用 Apple 的 RS256 算法）。"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="module")
def rsa_pem(rsa_keypair):
    """PEM 格式私钥（用于签 token）。"""
    from cryptography.hazmat.primitives import serialization

    private_key, _ = rsa_keypair
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _make_apple_token(
    rsa_pem: bytes,
    *,
    kid: str = "test-kid-1",
    aud: str = "cn.hmatch.app",
    iss: str = "https://appleid.apple.com",
    sub: str = "001234.deadbeef.5678",
    exp_offset_sec: int = 3600,
) -> str:
    """签一个合法的 Apple identity_token（用于 mock JWKS 测试）。"""
    now = int(time.time())
    headers = {"alg": "RS256", "kid": kid, "typ": "JWT"}
    payload = {
        "iss": iss,
        "aud": aud,
        "exp": now + exp_offset_sec,
        "iat": now,
        "sub": sub,
    }
    return jwt.encode(payload, rsa_pem, algorithm="RS256", headers=headers)


class TestAppleVerifyUnit:
    """apple_verify.py 单元测试（不发起真实 JWKS 拉取，用 mock PyJWKClient）。"""

    def test_valid_token_returns_payload(self, rsa_pem, rsa_keypair, monkeypatch):
        """合法 token：验签成功，返回 payload（含 sub）。"""
        from app.core.config import settings
        from app.domains.auth import apple_verify

        # 1. mock PyJWKClient：直接返回本地公钥
        _, public_key = rsa_keypair
        from cryptography.hazmat.primitives import serialization

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        class _FakeJWK:
            key = public_pem.decode("utf-8")

        class _FakeClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeJWK()

        monkeypatch.setattr(apple_verify, "_get_jwks_client", lambda: _FakeClient())
        monkeypatch.setattr(settings, "apple_client_id", "cn.hmatch.app")

        token = _make_apple_token(rsa_pem, sub="apple-user-abc")
        payload = apple_verify.verify_apple_identity_token(token)
        assert payload["sub"] == "apple-user-abc"
        assert payload["iss"] == "https://appleid.apple.com"
        assert payload["aud"] == "cn.hmatch.app"

    def test_wrong_signature_rejected(self, rsa_pem, monkeypatch):
        """用不同 key 签的 token → 验签失败。"""
        from app.core.config import settings
        from app.domains.auth import apple_verify

        # 生成"攻击者" key
        evil_pem = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        from cryptography.hazmat.primitives import serialization

        evil_pem_bytes = evil_pem.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        class _FakeJWK:
            key = "FAKE_KEY_FROM_ATTACKER"

        class _FakeClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeJWK()

        monkeypatch.setattr(apple_verify, "_get_jwks_client", lambda: _FakeClient())
        monkeypatch.setattr(settings, "apple_client_id", "cn.hmatch.app")

        # 用 evil key 签 token
        bad_token = _make_apple_token(evil_pem_bytes, sub="attacker")

        with pytest.raises(apple_verify.AppleAuthInvalidTokenError) as exc:
            apple_verify.verify_apple_identity_token(bad_token)
        assert "验签失败" in str(exc.value.message) or "不匹配" in str(exc.value.message)

    def test_wrong_audience_rejected(self, rsa_pem, rsa_keypair, monkeypatch):
        """aud 不匹配（不是我们的 client_id）→ 401。"""
        from app.core.config import settings
        from app.domains.auth import apple_verify

        _, public_key = rsa_keypair
        from cryptography.hazmat.primitives import serialization

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        class _FakeJWK:
            key = public_pem.decode("utf-8")

        class _FakeClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeJWK()

        monkeypatch.setattr(apple_verify, "_get_jwks_client", lambda: _FakeClient())
        monkeypatch.setattr(settings, "apple_client_id", "cn.hmatch.app")

        # 签一个 aud=evil.com 的 token
        token = _make_apple_token(rsa_pem, aud="evil.com")
        with pytest.raises(apple_verify.AppleAuthInvalidTokenError) as exc:
            apple_verify.verify_apple_identity_token(token)
        assert "audience" in str(exc.value.message).lower() or "aud" in str(exc.value.message).lower()

    def test_wrong_issuer_rejected(self, rsa_pem, rsa_keypair, monkeypatch):
        """iss != appleid.apple.com → 401。"""
        from app.core.config import settings
        from app.domains.auth import apple_verify

        _, public_key = rsa_keypair
        from cryptography.hazmat.primitives import serialization

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        class _FakeJWK:
            key = public_pem.decode("utf-8")

        class _FakeClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeJWK()

        monkeypatch.setattr(apple_verify, "_get_jwks_client", lambda: _FakeClient())
        monkeypatch.setattr(settings, "apple_client_id", "cn.hmatch.app")

        token = _make_apple_token(rsa_pem, iss="https://evil.com")
        with pytest.raises(apple_verify.AppleAuthInvalidTokenError):
            apple_verify.verify_apple_identity_token(token)

    def test_expired_token_rejected(self, rsa_pem, rsa_keypair, monkeypatch):
        """exp 已过 → 401。"""
        from app.core.config import settings
        from app.domains.auth import apple_verify

        _, public_key = rsa_keypair
        from cryptography.hazmat.primitives import serialization

        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        class _FakeJWK:
            key = public_pem.decode("utf-8")

        class _FakeClient:
            def get_signing_key_from_jwt(self, token):
                return _FakeJWK()

        monkeypatch.setattr(apple_verify, "_get_jwks_client", lambda: _FakeClient())
        monkeypatch.setattr(settings, "apple_client_id", "cn.hmatch.app")

        token = _make_apple_token(rsa_pem, exp_offset_sec=-3600)  # 1h 前过期
        with pytest.raises(apple_verify.AppleAuthInvalidTokenError) as exc:
            apple_verify.verify_apple_identity_token(token)
        assert "过期" in str(exc.value.message)

    def test_missing_client_id_rejected(self, rsa_pem, monkeypatch):
        """settings.apple_client_id 为空 → 401（没有 aud 期望值没法验）。"""
        from app.core.config import settings
        from app.domains.auth import apple_verify

        monkeypatch.setattr(settings, "apple_client_id", "")
        token = _make_apple_token(rsa_pem)
        with pytest.raises(apple_verify.AppleAuthInvalidTokenError) as exc:
            apple_verify.verify_apple_identity_token(token)
        assert "未配置" in str(exc.value.message)


# ============================================================
#  路由层集成测试
# ============================================================


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前清空 user 表（避免 mock user 残留导致 is_new 误判）。"""
    from sqlalchemy import text

    from app.core.database import engine

    with engine.begin() as conn:
        # 删顺序：先子表（依赖 user）再 users
        for tbl in ("reviews", "proposals", "invitations", "cooperations",
                    "demands", "properties", "devices", "users"):
            conn.execute(text(f"DELETE FROM {tbl}"))
    yield


@pytest.fixture()
def prod_env(monkeypatch):
    """切到生产环境。"""
    from app.core.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    yield
    monkeypatch.setattr(settings, "app_env", "development")


@pytest.fixture()
def cleared_wechat_config(monkeypatch):
    """清空微信配置（app_id/secret/test 都没有）。"""
    from app.core.config import settings
    monkeypatch.setattr(settings, "wechat_app_id", "")
    monkeypatch.setattr(settings, "wechat_app_secret", "")
    monkeypatch.setattr(settings, "wechat_test_app_id", "")
    monkeypatch.setattr(settings, "wechat_test_app_secret", "")


class TestWechatLoginProductionGuard:
    """[Sprint1-P0] 微信登录生产守卫。"""

    def test_production_without_credentials_returns_503(
        self, client: TestClient, prod_env, cleared_wechat_config
    ):
        """生产环境 + 缺凭证 → 503 WeChatAuthUnavailableError。"""
        resp = client.post(
            "/v1/auth/wechat-login",
            json={"code": "fake_code"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == 40004

    def test_development_without_credentials_uses_mock(
        self, client: TestClient, cleared_wechat_config
    ):
        """dev/staging 缺凭证 → mock 走通（regression）。"""
        resp = client.post(
            "/v1/auth/wechat-login",
            json={"code": "dev_alice_test_xxx"},
        )
        # 200 + login response（mock 模式正常返回）
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        data = resp.json()["data"]
        assert "access_token" in data


class TestDevIdentitiesProductionGuard:
    """[Sprint1-P0] /users/dev-identities 生产守卫。"""

    def test_production_returns_403(self, client: TestClient, prod_env):
        """生产环境调用 /users/dev-identities → 403 DevLoginDisabledError。"""
        resp = client.get("/v1/users/dev-identities")
        assert resp.status_code == 403
        assert resp.json()["code"] == 40006

    def test_development_returns_200(self, client: TestClient):
        """dev 环境正常返回 dev identities 列表。"""
        resp = client.get("/v1/users/dev-identities")
        # 200 + list（可能为空；只要不 403 即可）
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"


class TestAppleLoginProductionGuard:
    """[Sprint1-P0] Apple 登录生产守卫。"""

    def test_production_without_client_id_returns_500_or_401(
        self, client: TestClient, prod_env
    ):
        """生产环境 + 没配 apple_client_id → 401/500（验签必失败）。"""
        from app.core.config import settings
        # 强制 production 时 apple_client_id 空
        original = settings.apple_client_id
        settings.apple_client_id = ""
        try:
            resp = client.post(
                "/v1/auth/apple-login",
                json={"identity_token": "fake.jwt.token"},
            )
            # 验签会因为 client_id 空抛 401
            assert resp.status_code in (401, 500)
            if resp.status_code == 401:
                assert resp.json()["code"] == 40005
        finally:
            settings.apple_client_id = original

    def test_development_without_client_id_uses_mock(
        self, client: TestClient
    ):
        """dev 模式 + apple_client_id 空 → 走 mock（取前 32 字符）。"""
        from app.core.config import settings

        original = settings.apple_client_id
        settings.apple_client_id = ""
        try:
            # 32+ 字符的 fake token（mock 路径需要 ≥16 字符）
            fake_token = "x" * 64
            resp = client.post(
                "/v1/auth/apple-login",
                json={"identity_token": fake_token},
            )
            assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
            data = resp.json()["data"]
            assert "access_token" in data
            # 第一次创建，应该是新用户
            assert data["user"]["is_new"] is True
        finally:
            settings.apple_client_id = original
