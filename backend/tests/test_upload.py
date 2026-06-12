"""P0 上传接口测试。"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserStatus


# 最小有效 PNG（200x200 纯色，PIL 构造）
# 注：历史上 1x1 透明 PNG_BYTES 是手写字节（"89504e470d0a..."），
# 但 IDAT 校验和有错，image_processor 校验时会判格式损坏。
# 现在统一用 PIL 构造的合法 PNG。
def _make_png(width: int = 200, height: int = 200) -> bytes:
    """构造指定尺寸的纯色 PNG（[Sprint3-#13] 测试用真实图）。"""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PNG_BYTES = _make_png(200, 200)  # 兼容老测试引用
PNG_BYTES_LARGE = _make_png(200, 200)


def _large_png_upload(name: str = "test_large.png") -> dict:
    return {"file": (name, io.BytesIO(PNG_BYTES_LARGE), "image/png")}


# ============================================================
#  Fixtures
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    from app.models import (  # noqa: F401
        cooperation,
        demand,
        invitation,
        property,
        proposal,
        review,
        user,
    )
    from app.models.device import Device  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def auth_user():
    """P1-3: 用 file-based SQLite + 直接 INSERT。"""
    from datetime import datetime, timezone
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(__import__('sqlalchemy').text(f"DELETE FROM {table.name}"))
        db.add(User(
            id=99, name="Uploader", display_name="Uploader先生",
            status=UserStatus.ACTIVE, is_verified=True,
            credit_score=80.0, rating_avg=4.0, rating_count=0,
            last_login_at=datetime.now(timezone.utc),
        ))
        db.commit()
    return {"user_id": 99, "headers": {"Authorization": f"Bearer {create_access_token(99)}"}}


def _png_upload(name: str = "test.png") -> dict:
    return {"file": (name, io.BytesIO(PNG_BYTES), "image/png")}


def _large_png_upload_bytes() -> bytes:
    return PNG_BYTES_LARGE


# ============================================================
#  Tests
# ============================================================

class TestUploadImage:
    """P0 上传图片基础流程。"""

    def test_upload_png_returns_200_and_url(
        self, client: TestClient, auth_user, tmp_path, monkeypatch
    ):
        """上传 ≥100x100 真实 PNG 返 200 + 包含 url/filename/size/width/height。"""
        from pathlib import Path

        # 临时把 upload_dir 改到 tmp_path
        monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
        # 重新建一下目录（因为 main.py mount 时已经 mkdir 了）
        tmp_path.mkdir(exist_ok=True)

        # [Sprint3-#13] 用 ≥100x100 真实 PNG（1x1 会被 MIN_PIXELS 拒）
        large_png = _make_png(200, 200)
        resp = client.post(
            "/v1/upload/image",
            files={"file": ("test.png", io.BytesIO(large_png), "image/png")},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        data = resp.json()["data"]
        assert "url" in data
        assert "filename" in data
        # [Sprint3-#13] 新增 width/height
        assert data["width"] == 200
        assert data["height"] == 200
        # [Sprint3-#13] PNG re-encode 成 JPEG（OUTPUT_FORMAT_MAP）
        assert data["content_type"] == "image/jpeg"
        assert data["filename"].endswith(".jpg")
        # 文件存在 + 是 JPEG 格式
        uploaded = Path(str(tmp_path)) / data["filename"]
        assert uploaded.exists(), f"file not found: {uploaded}"
        with Image.open(uploaded) as img:
            assert img.format == "JPEG"
            assert img.size == (200, 200)

    def test_upload_rejects_bad_mime(
        self, client: TestClient, auth_user
    ):
        """上传 text/plain 返 400 UploadError。"""
        resp = client.post(
            "/v1/upload/image",
            files={"file": ("evil.txt", io.BytesIO(b"not an image"), "text/plain")},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 50001

    def test_upload_rejects_oversize(
        self, client: TestClient, auth_user, monkeypatch
    ):
        """超过 max_upload_size_mb 返 400。"""
        # 临时改成 0 byte 上限（任何非空文件都超）
        monkeypatch.setattr(settings, "max_upload_size_mb", 0)
        resp = client.post(
            "/v1/upload/image",
            files=_png_upload(),
            headers=auth_user["headers"],
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 50001

    def test_upload_rejects_empty_file(
        self, client: TestClient, auth_user
    ):
        """空文件返 400。"""
        resp = client.post(
            "/v1/upload/image",
            files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
            headers=auth_user["headers"],
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 50001

    def test_upload_requires_auth(self, client: TestClient):
        """未带 token 返 401。"""
        resp = client.post("/v1/upload/image", files=_png_upload())
        assert resp.status_code == 401


class TestUploadOss:
    """OSS 模式集成（不打真实 OSS，mock bucket）。"""

    def test_oss_mode_uses_oss_client(
        self, client: TestClient, auth_user, monkeypatch
    ):
        """UPLOAD_MODE=oss → 走 oss_client.upload_bytes，不写本地磁盘。"""
        from app.core import oss_client

        monkeypatch.setattr(settings, "upload_mode", "oss")
        monkeypatch.setattr(settings, "oss_access_key_id", "fake-ak")
        monkeypatch.setattr(settings, "oss_access_key_secret", "fake-sk")
        monkeypatch.setattr(settings, "oss_endpoint", "oss-cn-beijing.aliyuncs.com")
        monkeypatch.setattr(settings, "oss_bucket", "hmatch-test")

        captured: dict = {}

        def fake_upload(filename: str, content: bytes, content_type: str) -> str:
            captured["filename"] = filename
            captured["size"] = len(content)
            captured["content_type"] = content_type
            return f"https://hmatch-test.oss-cn-beijing.aliyuncs.com/uploads/{filename}"

        monkeypatch.setattr(oss_client, "upload_bytes", fake_upload)
        # router 是 `from app.core.oss_client import upload_bytes as oss_upload_bytes`
        # 但用的是局部 import，所以 monkeypatch oss_client 模块本身就行
        # （上面那行 import 在 router 里是函数内的，每次调用都会重新查 module attr）

        resp = client.post(
            "/v1/upload/image",
            files=_png_upload(),
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        data = resp.json()["data"]
        assert data["url"].startswith("https://hmatch-test.oss-cn-beijing.aliyuncs.com/uploads/")
        # [Sprint3-#13] re-encode 后是 JPEG，所以 captured size < 原 PNG size
        assert captured["size"] < len(PNG_BYTES), (
            f"re-encode 没生效: {captured['size']} vs {len(PNG_BYTES)}"
        )
        assert captured["content_type"] == "image/jpeg"
        assert captured["filename"] == data["filename"]

    def test_oss_missing_config_returns_503(
        self, client: TestClient, auth_user, monkeypatch
    ):
        """UPLOAD_MODE=oss 但凭证缺失 → OssNotConfiguredError(503)。"""
        from app.core import oss_client

        monkeypatch.setattr(settings, "upload_mode", "oss")
        # 故意清空凭证（模拟 ops 没配齐）
        monkeypatch.setattr(settings, "oss_access_key_id", "")
        monkeypatch.setattr(settings, "oss_access_key_secret", "")
        # 清掉 bucket 单例缓存，让 _validate_oss_settings 重新跑
        oss_client.get_bucket.cache_clear()

        resp = client.post(
            "/v1/upload/image",
            files=_png_upload(),
            headers=auth_user["headers"],
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == 50002
        assert "OSS_ACCESS_KEY_ID" in body["detail"]["missing"]

    def test_oss_upload_failure_returns_502(
        self, client: TestClient, auth_user, monkeypatch
    ):
        """OSS put_object 失败 → OssUploadError(502)，不泄漏 SDK 异常。"""
        from app.core import oss_client

        monkeypatch.setattr(settings, "upload_mode", "oss")
        monkeypatch.setattr(settings, "oss_access_key_id", "fake-ak")
        monkeypatch.setattr(settings, "oss_access_key_secret", "fake-sk")
        monkeypatch.setattr(settings, "oss_endpoint", "oss-cn-beijing.aliyuncs.com")
        monkeypatch.setattr(settings, "oss_bucket", "hmatch-test")

        # mock bucket put_object 直接抛
        class _FakeBucket:
            def put_object(self, key, content, headers=None):
                raise RuntimeError("network unreachable")

        oss_client.get_bucket.cache_clear()
        monkeypatch.setattr(oss_client, "get_bucket", lambda: _FakeBucket())

        resp = client.post(
            "/v1/upload/image",
            files=_png_upload(),
            headers=auth_user["headers"],
        )
        assert resp.status_code == 502
        assert resp.json()["code"] == 50003

    def test_oss_url_uses_cdn_when_configured(
        self, monkeypatch
    ):
        """配置了 upload_cdn_base 时，URL 用 CDN 域名而非 bucket endpoint。"""
        from app.core import oss_client

        monkeypatch.setattr(settings, "oss_bucket", "hmatch-test")
        monkeypatch.setattr(settings, "oss_endpoint", "oss-cn-beijing.aliyuncs.com")
        monkeypatch.setattr(settings, "upload_cdn_base", "https://cdn.homematch.cn")

        url = oss_client.build_public_url("abc.jpg")
        assert url == "https://cdn.homematch.cn/uploads/abc.jpg"

    def test_oss_url_falls_back_to_endpoint(
        self, monkeypatch
    ):
        """没配 CDN 时，URL 用 ``{bucket}.{endpoint-host}/{key}`` 格式。"""
        from app.core import oss_client

        monkeypatch.setattr(settings, "oss_bucket", "hmatch-test")
        monkeypatch.setattr(settings, "oss_endpoint", "oss-cn-beijing.aliyuncs.com")
        monkeypatch.setattr(settings, "upload_cdn_base", "")

        url = oss_client.build_public_url("abc.jpg")
        assert url == "https://hmatch-test.oss-cn-beijing.aliyuncs.com/uploads/abc.jpg"


class TestUploadMultiple:
    """P0 批量上传。"""

    def test_upload_3_images_succeeds(
        self, client: TestClient, auth_user, tmp_path, monkeypatch
    ):
        """批量传 3 张都成功。"""
        from pathlib import Path

        monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
        tmp_path.mkdir(exist_ok=True)

        # [Sprint3-#13] 必须用 ≥100x100 真实图（image_processor 校验）
        large = _make_png(200, 200)
        files = [
            ("files", (f"img{i}.png", io.BytesIO(large), "image/png"))
            for i in range(3)
        ]
        resp = client.post(
            "/v1/upload/images",
            files=files,
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200, f"{resp.text}"
        data = resp.json()["data"]
        assert len(data) == 3
        # 3 个文件都生成了
        for d in data:
            assert (Path(str(tmp_path)) / d["filename"]).exists()

    def test_upload_rejects_too_many(
        self, client: TestClient, auth_user
    ):
        """超过 9 张返 400。"""
        files = [
            ("files", (f"img{i}.png", io.BytesIO(PNG_BYTES), "image/png"))
            for i in range(10)
        ]
        resp = client.post(
            "/v1/upload/images",
            files=files,
            headers=auth_user["headers"],
        )
        assert resp.status_code == 400
