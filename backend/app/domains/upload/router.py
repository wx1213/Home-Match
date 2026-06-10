"""Upload 域 - 文件上传接口（MVP：本地存储 + 静态托管）。

MVP 阶段：
- local 模式：存到 `upload_dir`（默认 ./uploads），通过 FastAPI StaticFiles 暴露
- oss 模式：上传到阿里云 OSS（settings 配齐后启用）

设计要点（[D-010] + [D-017]）：
- 白名单 MIME（防上传恶意文件）
- 文件名 = uuid4 + 原后缀（防路径冲突）
- 限制单文件大小（防 OOM）
- 水印：M2 接入，本期只做存储
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ValidationError
from app.core.logging import get_logger
from app.domains.auth.dependencies import get_current_user
from app.models.user import User
from app.schemas.common import APIResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/upload", tags=["文件上传"])


# ============================================================
#  错误码
# ============================================================

class UploadError(AppError):
    """上传相关错误（400）。"""
    code = 50001
    message = "上传失败"
    http_status = 400


# ============================================================
#  Helpers
# ============================================================

def _ensure_upload_dir() -> Path:
    """确保上传目录存在，返回 Path 对象。"""
    upload_path = Path(settings.upload_dir).resolve()
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def _check_upload_constraints(file: UploadFile) -> None:
    """检查文件大小 + MIME 白名单。"""
    # 1. MIME 白名单
    if file.content_type not in settings.upload_allowed_types:
        raise UploadError(
            f"不支持的文件类型: {file.content_type}",
            detail={
                "content_type": file.content_type,
                "allowed": settings.upload_allowed_types,
            },
        )

    # 2. 文件大小（content_length 头不一定有，部分客户端不发）
    #    主要靠读流时 count 字节


def _build_public_url(filename: str) -> str:
    """构造文件可访问的 URL。"""
    if settings.upload_mode == "oss":
        # OSS 模式：CDN 或 endpoint
        base = settings.upload_cdn_base or f"https://{settings.oss_bucket}.{settings.oss_endpoint}"
        return f"{base.rstrip('/')}/uploads/{filename}"
    # local 模式：app_base_url + /uploads/filename
    return f"{settings.app_base_url.rstrip('/')}/uploads/{filename}"


# ============================================================
#  上传图片
# ============================================================

@router.post(
    "/image",
    response_model=APIResponse[dict],
    summary="上传图片（房源/头像/评价）",
)
async def upload_image(
    file: UploadFile = File(..., description="图片文件"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    """上传单张图片，返回访问 URL。

    MVP 流程（local 模式）：
    1. 校验 MIME 白名单
    2. 流式读取 + 限制大小（防 OOM）
    3. 生成 uuid 文件名 + 保留原后缀
    4. 存到 upload_dir
    5. 返回 {url, filename, size}
    """
    _check_upload_constraints(file)

    # 1. 读取到 bytes（带大小限制）
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()
    size = len(content)
    if size == 0:
        raise UploadError("空文件")
    if size > max_bytes:
        raise UploadError(
            f"文件超过 {settings.max_upload_size_mb}MB",
            detail={"size": size, "limit": max_bytes},
        )

    # 2. 生成文件名
    suffix = Path(file.filename or "").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        suffix = ".jpg"  # 兜底
    filename = f"{uuid.uuid4().hex}{suffix}"

    # 3. 保存
    if settings.upload_mode == "local":
        upload_path = _ensure_upload_dir()
        target = upload_path / filename
        with target.open("wb") as f:
            f.write(content)
        url = _build_public_url(filename)
        logger.info(
            "Image uploaded (local)",
            extra={
                "user_id": user.id,
                "stored_filename": filename,  # ⚠️ 不要用 "filename"，会跟 LogRecord.filename 冲突
                "size": size,
                "content_type": file.content_type,
            },
        )
    else:
        # OSS 模式（M2）：这里替换为 oss2.bucket.put_object
        # 本期 MVP 暂不实现，强制走 local
        raise UploadError("OSS 模式尚未实现，请用 UPLOAD_MODE=local")

    return APIResponse(data={
        "url": url,
        "filename": filename,
        "size": size,
        "content_type": file.content_type,
    })


@router.post(
    "/images",
    response_model=APIResponse[list[dict]],
    summary="批量上传图片（最多 9 张/次）",
)
async def upload_images(
    files: list[UploadFile] = File(..., description="多张图片"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[dict]]:
    """批量上传，最多 9 张/次（与房源封面图数匹配）。"""
    if not files:
        raise ValidationError("至少上传 1 张图")
    if len(files) > 9:
        raise ValidationError("单次最多 9 张图")

    results = []
    errors = []
    for f in files:
        try:
            result = await upload_image(file=f, db=db, user=user)
            results.append(result.data)
        except AppError as e:
            errors.append({"filename": f.filename, "error": e.message})
        except Exception as e:
            errors.append({"filename": f.filename, "error": str(e)})

    if not results and errors:
        raise UploadError(
            "所有图片上传失败",
            detail={"errors": errors},
        )

    return APIResponse(
        data=results,
        message=f"成功 {len(results)}/{len(files)} 张" if errors else f"成功 {len(results)} 张",
    )
