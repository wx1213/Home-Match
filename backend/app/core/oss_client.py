"""阿里云 OSS 客户端封装。

设计要点：
- ``get_bucket()`` 用 ``lru_cache`` 单例，避免每次请求新建连接
- ``upload_bytes()`` 是上传入口；catch oss2 错误统一转 UploadError，调用方不用关心 SDK
- 路径前缀 ``uploads/`` 跟 local 模式保持一致
- URL 优先用 ``upload_cdn_base``（CDN 域名），fallback 用 bucket endpoint

什么时候启用：
- 把 ``UPLOAD_MODE=oss`` + 4 个 OSS 凭证 env（access_key/secret/endpoint/bucket）配齐
- local 模式不会触发本模块（节省 oss2 import 开销也不会泄漏到测试）

错误降级：
- oss2 错误 → ``UploadError``（400），message 描述具体失败原因
- 未配置凭证 → ``UploadError("OSS 未配置...")``，调用方知道是 ops 问题
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import get_logger

if TYPE_CHECKING:
    import oss2

logger = get_logger(__name__)


class OssNotConfiguredError(AppError):
    """OSS 配置缺失（ops 问题，非用户问题）。"""

    code = 50002
    message = "OSS 未配置"
    http_status = 503


class OssUploadError(AppError):
    """OSS 上传失败（网络 / 权限 / 服务端错误）。"""

    code = 50003
    message = "OSS 上传失败"
    http_status = 502


def _validate_oss_settings() -> None:
    """启动时检查 4 个必填字段；缺一不可。"""
    missing = []
    if not settings.oss_access_key_id:
        missing.append("OSS_ACCESS_KEY_ID")
    if not settings.oss_access_key_secret:
        missing.append("OSS_ACCESS_KEY_SECRET")
    if not settings.oss_endpoint:
        missing.append("OSS_ENDPOINT")
    if not settings.oss_bucket:
        missing.append("OSS_BUCKET")
    if missing:
        raise OssNotConfiguredError(
            f"OSS 配置缺失: {', '.join(missing)}",
            detail={"missing": missing},
        )


@lru_cache(maxsize=1)
def get_bucket() -> oss2.Bucket:
    """返回 oss2.Bucket 单例。首次调用时建连。

    ``lru_cache`` 是进程级单例；测试时用 ``get_bucket.cache_clear()`` 重置。
    """
    _validate_oss_settings()

    import oss2  # 延迟 import，让 local 模式跑得起来即使没装 oss2

    auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
    # endpoint 允许传完整 https:// URL 或纯域名；oss2 内部会补 scheme
    bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket)
    logger.info(
        "OSS bucket initialized",
        extra={"bucket": settings.oss_bucket, "endpoint": settings.oss_endpoint},
    )
    return bucket


def build_public_url(filename: str) -> str:
    """构造 OSS 文件的可访问 URL。

    优先级：CDN > bucket.endpoint
    路径前缀 ``uploads/`` 跟 local 模式 ``/uploads/...`` 对齐。
    """
    key = f"uploads/{filename}"
    if settings.upload_cdn_base:
        return f"{settings.upload_cdn_base.rstrip('/')}/{key}"
    # endpoint 可能带 scheme 也可能不带，统一加 https://
    endpoint = settings.oss_endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"https://{endpoint}"
    # OSS 公网 URL 格式：https://{bucket}.{endpoint-host}/{key}
    # endpoint 形如 https://oss-cn-beijing.aliyuncs.com → bucket 拼到 host 前
    from urllib.parse import urlparse

    parsed = urlparse(endpoint)
    return f"{parsed.scheme}://{settings.oss_bucket}.{parsed.netloc}/{key}"


def upload_bytes(
    filename: str,
    content: bytes,
    content_type: str,
) -> str:
    """上传字节流到 OSS。

    Args:
        filename: uuid + 后缀，不含路径前缀（``uploads/`` 由本函数添加）
        content: 文件字节流
        content_type: MIME（OSS Object 的 Content-Type 头）

    Returns:
        公网可访问的 URL（CDN 或 bucket endpoint）

    Raises:
        OssNotConfiguredError: 4 个配置项缺失
        OssUploadError: oss2 抛错（网络/权限/服务端）
    """
    bucket = get_bucket()
    key = f"uploads/{filename}"

    try:
        # put_object 是同步阻塞调用；MVP 量级（每秒 < 10 次）可接受。
        # 如果 QPS 起来，改用 RQ 异步任务（上传完再回写 URL）。
        result = bucket.put_object(
            key,
            content,
            headers={"Content-Type": content_type},
        )
        # oss2 用 HTTP status code 判断成功，2xx 才算
        if not (200 <= result.status < 300):
            raise OssUploadError(
                f"OSS 上传失败 (status={result.status})",
                detail={"status": result.status, "key": key},
            )
    except OssUploadError:
        raise
    except Exception as e:
        # oss2 自己的异常（OssError / ServerError / ClientError）+ 网络异常
        # 统一转 OssUploadError，调用方拿到 400 而非 500
        exc_module = getattr(e.__class__, "__module__", "")
        is_oss_exc = "oss2" in exc_module
        logger.error(
            "OSS upload failed",
            extra={
                "key": key,
                "error_type": e.__class__.__name__,
                "is_oss_exc": is_oss_exc,
                "error": str(e),
            },
        )
        raise OssUploadError(
            f"OSS 上传失败: {e}",
            detail={"key": key, "error_type": e.__class__.__name__},
        ) from e

    url = build_public_url(filename)
    logger.info(
        "OSS upload ok",
        extra={"key": key, "url": url, "size": len(content)},
    )
    return url
