from __future__ import annotations

"""敏感字段加密 - AES-256-GCM（手机号）+ HMAC-SHA256（索引用哈希）。

参考 D-011：手机号 AES-256 加密存储，索引用 HMAC-SHA256 哈希。
"""

import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_aes_key() -> bytes:
    """从配置读取 32 字节 AES key。

    配置支持两种格式:
    - base64:xxxxx  （base64 编码）
    - 直接 32 字节字符串
    """
    key = settings.phone_encryption_key
    if key.startswith("base64:"):
        return base64.b64decode(key[7:])
    # 兜底：取 SHA-256（不推荐，但避免启动失败）
    return hashlib.sha256(key.encode()).digest()


def _get_hmac_key() -> bytes:
    """HMAC 索引用 key。"""
    return settings.phone_hash_key.encode("utf-8")


def encrypt_phone(phone: str) -> str:
    """加密手机号。

    返回格式: base64(iv) + ":" + base64(ciphertext) + ":" + base64(tag)
    """
    aes_key = _get_aes_key()
    aesgcm = AESGCM(aes_key)
    iv = os.urandom(12)  # 12 字节（GCM 标准）
    ciphertext_with_tag = aesgcm.encrypt(iv, phone.encode("utf-8"), None)

    # GCM 模式下，ciphertext 末尾 16 字节是 tag
    ciphertext = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]

    return (
        f"{base64.b64encode(iv).decode()}:"
        f"{base64.b64encode(ciphertext).decode()}:"
        f"{base64.b64encode(tag).decode()}"
    )


def decrypt_phone(encrypted: str) -> str:
    """解密手机号。"""
    try:
        iv_b64, ct_b64, tag_b64 = encrypted.split(":")
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(ct_b64)
        tag = base64.b64decode(tag_b64)
        ciphertext_with_tag = ciphertext + tag

        aes_key = _get_aes_key()
        aesgcm = AESGCM(aes_key)
        plaintext = aesgcm.decrypt(iv, ciphertext_with_tag, None)
        return plaintext.decode("utf-8")
    except Exception as e:
        logger.error("Phone decryption failed", extra={"error": str(e)})
        raise ValueError("手机号解密失败") from e


def hash_phone(phone: str) -> str:
    """手机号索引用 HMAC-SHA256 哈希（精确查询用）。"""
    return hmac.new(_get_hmac_key(), phone.encode("utf-8"), hashlib.sha256).hexdigest()


def mask_phone(phone: str) -> str:
    """手机号脱敏：138****8000。"""
    if len(phone) != 11:
        return phone
    return f"{phone[:3]}****{phone[7:]}"
