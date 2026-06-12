"""Apple identity_token JWT 验签。

Apple Sign-In 流程（[D-013] iOS 上架合规必选）：
1. iOS SDK 拿到 ``identity_token``（JWT 格式，RS256 签名）
2. 后端验证 4 件事：
   - 签名：拿 header.kid 去 Apple JWKS (https://appleid.apple.com/auth/keys) 拉公钥
   - iss == ``https://appleid.apple.com``
   - aud == 我们的 ``client_id``（iOS app bundle id = settings.apple_client_id）
   - exp 未过期
3. 用 payload.sub（Apple 唯一用户 id）当 apple_user_id

安全要点：
- 公钥从 Apple JWKS 拉，本地缓存（避免每次都拉外网）
- ``sub`` 是稳定 id，**不要**用 ``identity_token[:32]`` 当 id（之前 MVP 简化方案）
- ``nonce`` 可选校验（前端要传过来才能校验；本期先把 4 件套做硬，nonce 留给 P1）

参考：
- https://developer.apple.com/documentation/sign_in_with_apple/sign_in_with_apple_rest_api/verifying_a_user
- https://developer.apple.com/documentation/sign_in_with_apple/fetch_apple_s_public_key_for_verifying_an_identity_token
"""
from __future__ import annotations

from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.core.errors import AppleAuthInvalidTokenError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Apple JWKS endpoint — 公钥在 RS256 JWT 的 header.kid 下检索
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

# JWKS client 单例（PyJWKClient 内部带 LRU 缓存）
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """懒加载 JWKS client。"""
    global _jwks_client
    if _jwks_client is None:
        # PyJWKClient 内部用 urllib 拉 JWKS 并按 kid 缓存公钥
        # 默认 cache_keys=True，cache_jwk_set=True（5 分钟刷新）
        _jwks_client = PyJWKClient(APPLE_JWKS_URL)
    return _jwks_client


def reset_jwks_client_for_testing() -> None:
    """测试用：清掉 module 级 client 单例。"""
    global _jwks_client
    _jwks_client = None


def verify_apple_identity_token(
    identity_token: str,
    client_id: str | None = None,
) -> dict[str, Any]:
    """验签 Apple identity_token，返回 payload（包含 sub/email/email_verified 等）。

    Args:
        identity_token: iOS 端发来的 JWT（RS256）
        client_id: 期望的 aud（iOS bundle id）；默认用 ``settings.apple_client_id``

    Returns:
        payload dict（含 sub 字段 = Apple 唯一用户 id）

    Raises:
        AppleAuthInvalidTokenError: 验签失败（签名/aud/iss/exp 任一不通过）
    """
    expected_aud = client_id or settings.apple_client_id
    if not expected_aud:
        raise AppleAuthInvalidTokenError(
            "Apple client_id 未配置",
            detail={"reason": "settings.apple_client_id is empty"},
        )

    try:
        # 1. 拿 header.kid 找公钥
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(identity_token)

        # 2. 验签 + 解析（同时校验 exp）
        #    algorithms 锁死 ["RS256"]（Apple 只用 RS256）——防止 alg=none 攻击
        #    audience 和 issuer 一起验
        payload = jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=expected_aud,
            issuer=APPLE_ISSUER,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise AppleAuthInvalidTokenError(
            "Token 已过期",
            detail={"reason": str(e)},
        ) from e
    except jwt.InvalidAudienceError as e:
        raise AppleAuthInvalidTokenError(
            f"audience 不匹配（期望 {expected_aud}）",
            detail={"reason": str(e)},
        ) from e
    except jwt.InvalidIssuerError as e:
        raise AppleAuthInvalidTokenError(
            f"issuer 不匹配（期望 {APPLE_ISSUER}）",
            detail={"reason": str(e)},
        ) from e
    except jwt.PyJWTError as e:
        # 签名失败 / kid 找不到 / 格式错 等
        raise AppleAuthInvalidTokenError(
            "Apple 身份令牌验签失败",
            detail={"reason": str(e), "type": e.__class__.__name__},
        ) from e
    except (httpx.HTTPError, Exception) as e:
        # JWKS 拉取失败（网络）也归为验签失败 —— 不允许在网络异常时把用户当合法
        logger.error(
            "Apple JWKS fetch failed",
            extra={"error": str(e), "type": e.__class__.__name__},
        )
        raise AppleAuthInvalidTokenError(
            "Apple 身份令牌验签服务不可用",
            detail={"reason": str(e), "type": e.__class__.__name__},
        ) from e

    # 防御性检查：sub 必须非空
    sub = payload.get("sub")
    if not sub:
        raise AppleAuthInvalidTokenError(
            "Token 缺少 sub 字段",
            detail={"reason": "empty sub"},
        )

    return payload


def extract_apple_user_id(identity_token: str) -> str:
    """便捷：验签后直接拿 sub。"""
    payload = verify_apple_identity_token(identity_token)
    sub = payload["sub"]
    # type ignore: sub 在 verify 里已经保证非空
    return str(sub)


# 用于开发期测试：允许用无签名 mock token
def is_dev_mode() -> bool:
    """开发/staging 环境允许 mock；生产强制验签。"""
    return not settings.is_production


def mock_extract_user_id_for_dev(identity_token: str) -> str:
    """仅 dev/staging 使用：直接用 token 前 32 位当 id（MVP 简化方案）。

    生产环境不允许走这条路径（router 层会拦截）。
    """
    if not identity_token or len(identity_token) < 16:
        raise AppleAuthInvalidTokenError(
            "identity_token 长度不足",
            detail={"reason": "too short", "len": len(identity_token) if identity_token else 0},
        )
    # 之前用前 32 字符；保持兼容
    return identity_token[:32]
