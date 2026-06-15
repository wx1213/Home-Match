"""上传图片处理（[Sprint3-#13]）。

为什么需要这层：
1. **真实格式校验**：HTTP ``Content-Type`` 是客户端自报的，可被伪造。
   用 PIL Image.open + verify() 解码验证文件是真实图片
   （不解析的 ``.txt`` 改后缀成 ``.jpg`` 会被识破）
2. **EXIF 清理**：原图 EXIF 含 GPS 坐标 / 相机型号 / 拍摄时间 / 镜头序列号
   - GPS 直接泄漏**拍摄者住址**（[D-017]）
   - 镜头序列号可关联特定设备 → 隐私风险
   - 清理后还要**保 orientation**（很多手机照是横的，丢 EXIF 就转不回来）
3. **decompression bomb 防护**：恶意 1MB 文件可声称 50000x50000
   Pillow 默认会解压到内存 → OOM
4. **re-encode 压缩**：用户原图可能 12MB（4K），APP 端有压缩
   但服务端兜底再压一次 → 节省 OSS 流量 + 加快 APP 加载
5. **hash 黑名单**：常见违规样本 md5（色情/暴恐）— MVP 不上 ML，
   抽样比对已知黑样本

设计原则：
- 失败不静默：解码失败 → 返 400，**不**走通到 OSS
- 性能：单张 < 8MB 输入 + 重编码 < 200ms（i7）
"""
from __future__ import annotations

import hashlib
import io
from typing import Final

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
#  错误类型
# ============================================================

class ImageProcessingError(Exception):
    """图片处理失败（解码 / 格式 / 尺寸 / 违规）。"""


# ============================================================
#  策略常量
# ============================================================

# 最大像素（decompression bomb 防护；4K=8.3M, 8K=33M）
# 真实房源图不会超过 8K；超过直接拒
MAX_PIXELS: Final[int] = 50_000_000  # 50M pixels（约 7070x7070）

# 最小像素（防止上传占位图）
MIN_PIXELS: Final[int] = 100 * 100  # 100x100

# 支持的格式（白名单）
ALLOWED_FORMATS: Final[frozenset[str]] = frozenset({
    "JPEG", "PNG", "WEBP", "HEIF",
})

# 输出格式映射（按输入格式选）
# - JPEG / PNG → 仍输出 JPEG（最广兼容）
# - WEBP → WEBP（保透明）
# - HEIF → JPEG（HEIF iOS 专用，跨平台服务转 JPEG）
OUTPUT_FORMAT_MAP: Final[dict[str, tuple[str, dict]]] = {
    "JPEG": ("JPEG", {"quality": 85, "optimize": True}),
    "PNG":  ("JPEG", {"quality": 90, "optimize": True}),  # PNG → JPEG
    "WEBP": ("WEBP", {"quality": 82, "method": 4}),
    "HEIF": ("JPEG", {"quality": 88, "optimize": True}),
}

# 黑名单 hash（MVP 抽样；真实靠 ML/三方审核）
# 放这里而不是外置是为了让单测能直接覆盖
_HASH_BLACKLIST: Final[frozenset[str]] = frozenset()  # 暂无样本，留接口

# ============== EXIF tag ids ==============
# GPS 全部 0x00xx 段
_GPS_TAG_RANGE = range(0x0000, 0x001F)
# 相机/设备相关
_CAMERA_TAGS: Final[frozenset[int]] = frozenset({
    0x010F,  # Make
    0x0110,  # Model
    0x0131,  # Software
    0x0132,  # DateTime
    0x013B,  # Artist
    0x013F,  # WhitePoint
    0x8298,  # Copyright
    0xA430,  # OwnerName
    0xA431,  # SerialNumber
    0xA432,  # LensSpecification
    0xA433,  # LensMake
    0xA434,  # LensModel
    0xA435,  # LensSerialNumber
})


# ============================================================
#  公共 API
# ============================================================

def sanitize_and_reencode(
    content: bytes,
    *,
    max_output_bytes: int = 4 * 1024 * 1024,  # 服务端再压到 ≤4MB
) -> tuple[bytes, str, int, int]:
    """[Sprint3-#13] 验证 + 清理 EXIF + 重编码图片。

    Args:
        content: 原始图片字节
        max_output_bytes: 输出大小上限（超了再压一次 quality）

    Returns:
        (clean_bytes, content_type, width, height)

    Raises:
        ImageProcessingError: 任何校验失败（格式 / 尺寸 / 损坏 / 违规）
    """
    # 1. 黑名单 hash 抽样（[Sprint3-#13] 增量：MVP 暂无样本，留接口）
    file_hash = hashlib.md5(content).hexdigest()
    if file_hash in _HASH_BLACKLIST:
        logger.warning("Image blocked by hash blacklist", extra={"md5": file_hash})
        raise ImageProcessingError("图片内容违规")

    # 2. PIL 真实解码
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()  # 只验证文件完整性，不加载像素
    except (UnidentifiedImageError, SyntaxError, OSError, ValueError) as e:
        logger.warning("Image decode failed", extra={"error": str(e)})
        raise ImageProcessingError(f"图片格式无效或已损坏: {e}") from e

    # verify() 后 image 对象已损坏，必须重新 open
    try:
        img = Image.open(io.BytesIO(content))
    except Exception as e:
        raise ImageProcessingError("图片无法重新解码") from e

    # 3. decompression bomb 防护
    #    PIL 默认在 Image.open 时 check 一次（Image.MAX_IMAGE_PIXELS）
    #    但我们要更严格的策略
    width, height = img.size
    if width * height > MAX_PIXELS:
        raise ImageProcessingError(
            f"图片像素过大 ({width}x{height}={width*height} > {MAX_PIXELS})"
        )
    if width * height < MIN_PIXELS:
        raise ImageProcessingError(
            f"图片像素过小 ({width}x{height})，可能是占位图"
        )

    # 4. 格式白名单
    fmt = (img.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise ImageProcessingError(f"不支持的图片格式: {fmt or '未知'}")

    # 5. 应用 EXIF orientation（很多手机图横着，丢 EXIF 就转不回来）
    #    这一步同时把 EXIF 信息应用成像素变换 → 之后 strip EXIF 不影响显示
    try:
        img = ImageOps.exif_transpose(img)  # type: ignore[assignment]
    except Exception:
        # 损坏的 EXIF 不阻塞上传，只是不做转正
        logger.debug("exif_transpose failed, continue without rotation")

    # 6. 清理 EXIF（[Sprint3-#13] 隐私关键）
    #    方式：手动构造不包含敏感 tag 的 EXIF
    img = _strip_sensitive_exif(img)  # type: ignore[assignment]

    # 7. 颜色模式转换（RGBA / P / L → RGB）
    if img.mode in ("RGBA", "LA", "P"):
        # 透明背景填白（JPEG 不支持透明）
        if img.mode == "P":
            img = img.convert("RGBA")  # type: ignore[assignment]
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA"):
            bg.paste(img, mask=img.split()[-1])
            img = bg  # type: ignore[assignment]
        else:
            img = img.convert("RGB")  # type: ignore[assignment]
    elif img.mode == "CMYK":
        img = img.convert("RGB")  # type: ignore[assignment]

    # 8. re-encode
    output_fmt, kwargs = OUTPUT_FORMAT_MAP[fmt]
    output = io.BytesIO()
    try:
        img.save(output, format=output_fmt, **kwargs)
    except (OSError, ValueError) as e:
        raise ImageProcessingError(f"图片重新编码失败: {e}") from e

    output_bytes = output.getvalue()

    # 9. 输出过大再压一次（quality 降一档）
    if len(output_bytes) > max_output_bytes and output_fmt == "JPEG":
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=70, optimize=True)
        output_bytes = output.getvalue()
    if len(output_bytes) > max_output_bytes:
        # 还大 → 直接拒（异常情况，APP 端应该已经压过了）
        raise ImageProcessingError(
            f"图片压缩后仍超过 {max_output_bytes // 1024 // 1024}MB"
        )

    # 10. content_type 映射
    content_type = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "HEIF": "image/jpeg",
    }[output_fmt]

    return output_bytes, content_type, img.size[0], img.size[1]


def _strip_sensitive_exif(img: Image.Image) -> Image.Image:
    """[Sprint3-#13] 彻底清除 EXIF（GPS / 相机 / 序列号 / 拍摄时间 全部丢失）。

    orientation 已经被 :func:`ImageOps.exif_transpose` 应用成像素变换，
    所以删 EXIF 不会让横着拍的照片看起来又转回去。

    实现：直接 pop ``img.info["exif"]``，Pillow 在 save 时就不会写 EXIF 段。
    """
    img.info.pop("exif", None)
    return img
