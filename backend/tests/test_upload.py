"""P0 上传接口测试。"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.models.user import User, UserStatus


# 1x1 透明 PNG（最小有效 PNG）
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c63000100000005000100" "0d0a2db40000000049454e44ae426082"
)


# ============================================================
#  Fixtures
# ============================================================

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    from app.models import (  # noqa: F401
        cooperation,
        demand,
        invitation,
        proposal,
        property,
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


# ============================================================
#  Tests
# ============================================================

class TestUploadImage:
    """P0 上传图片基础流程。"""

    def test_upload_png_returns_200_and_url(
        self, client: TestClient, auth_user, tmp_path, monkeypatch
    ):
        """上传 1x1 PNG 返 200 + 包含 url/filename/size。"""
        from pathlib import Path
        # 临时把 upload_dir 改到 tmp_path
        monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
        # 重新建一下目录（因为 main.py mount 时已经 mkdir 了）
        tmp_path.mkdir(exist_ok=True)

        resp = client.post(
            "/v1/upload/image",
            files=_png_upload(),
            headers=auth_user["headers"],
        )
        assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
        data = resp.json()["data"]
        assert "url" in data
        assert "filename" in data
        assert data["size"] == len(PNG_BYTES)
        assert data["content_type"] == "image/png"
        # 文件应该存在
        uploaded = Path(str(tmp_path)) / data["filename"]
        assert uploaded.exists(), f"file not found: {uploaded}"
        assert uploaded.read_bytes() == PNG_BYTES

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


class TestUploadMultiple:
    """P0 批量上传。"""

    def test_upload_3_images_succeeds(
        self, client: TestClient, auth_user, tmp_path, monkeypatch
    ):
        """批量传 3 张都成功。"""
        from pathlib import Path
        monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
        tmp_path.mkdir(exist_ok=True)

        files = [
            ("files", (f"img{i}.png", io.BytesIO(PNG_BYTES), "image/png"))
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
