"""贝壳链接解析测试（P0 任务 1：B1 commit）。

覆盖：
- parse_beike_url() 正则解析各种合法 / 非法 URL
- POST /v1/ai/parse-beike-url 端点
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agents.beike_parser import (
    URL_TYPE_BUYHOUSE,
    URL_TYPE_ERSHOUFANG,
    URL_TYPE_LOUPAN,
    URL_TYPE_XINFANG,
    parse_beike_url,
)
from app.core.security import create_access_token


# ============================================================
#  parse_beike_url() 纯函数
# ============================================================

class TestParseBeikeUrl:
    """parse_beike_url 各种 URL 模式解析。"""

    def test_empty_url_invalid(self):
        r = parse_beike_url("")
        assert r.valid is False
        assert "空" in r.reason

    def test_none_url_invalid(self):
        r = parse_beike_url(None)  # type: ignore[arg-type]
        assert r.valid is False

    def test_non_beike_domain_invalid(self):
        r = parse_beike_url("https://www.zhihu.com/question/12345")
        assert r.valid is False
        assert "ke.com" in r.reason or "贝壳" in r.reason

    def test_unsupported_path_invalid(self):
        r = parse_beike_url("https://bj.ke.com/community/abc/123")
        assert r.valid is False
        assert "路径" in r.reason

    # ----- 4 类合法 URL -----

    def test_ershoufang_bj(self):
        r = parse_beike_url("https://bj.ke.com/ershoufang/12345.html")
        assert r.valid is True
        assert r.url_type == URL_TYPE_ERSHOUFANG
        assert r.house_id == "12345"
        assert r.city == "bj"

    def test_ershoufang_no_city(self):
        r = parse_beike_url("https://ke.com/ershoufang/abc123.html")
        assert r.valid is True
        assert r.url_type == URL_TYPE_ERSHOUFANG
        assert r.house_id == "abc123"
        assert r.city is None

    def test_loupan_with_prefix(self):
        r = parse_beike_url("https://sh.ke.com/loupan/p_xyz789/")
        assert r.valid is True
        assert r.url_type == URL_TYPE_LOUPAN
        assert r.house_id == "p_xyz789"
        assert r.city == "sh"

    def test_buyhouse(self):
        r = parse_beike_url("https://ke.com/buyhouse/q123")
        assert r.valid is True
        assert r.url_type == URL_TYPE_BUYHOUSE
        assert r.house_id == "q123"

    def test_xinfang(self):
        r = parse_beike_url("https://gz.ke.com/xinfang/n456.html")
        assert r.valid is True
        assert r.url_type == URL_TYPE_XINFANG
        assert r.house_id == "n456"
        assert r.city == "gz"

    # ----- 域名兼容 -----

    def test_beike_com_domain(self):
        r = parse_beike_url("https://bj.beike.com/ershoufang/abc.html")
        assert r.valid is True
        assert r.url_type == URL_TYPE_ERSHOUFANG

    def test_fang_ke_com_legacy_domain(self):
        r = parse_beike_url("https://bj.fang.ke.com/ershoufang/legacy1.html")
        assert r.valid is True
        assert r.url_type == URL_TYPE_ERSHOUFANG

    def test_no_scheme(self):
        """不带 https:// 也能解析。"""
        r = parse_beike_url("ke.com/ershoufang/123.html")
        assert r.valid is True
        assert r.house_id == "123"

    def test_with_query_string(self):
        """URL 带 query string 不影响解析。"""
        r = parse_beike_url("https://bj.ke.com/ershoufang/123.html?utm_source=test")
        assert r.valid is True
        assert r.house_id == "123"

    def test_with_fragment(self):
        """URL 带 fragment 不影响解析。"""
        r = parse_beike_url("https://bj.ke.com/ershoufang/123.html#anchor")
        assert r.valid is True
        assert r.house_id == "123"

    def test_uppercase_url(self):
        """URL 大小写不敏感。"""
        r = parse_beike_url("HTTPS://BJ.KE.COM/ERSHOUFANG/UPPER1.HTML")
        assert r.valid is True
        assert r.url_type == URL_TYPE_ERSHOUFANG
        assert r.house_id == "UPPER1"
        assert r.city == "bj"


# ============================================================
#  POST /v1/ai/parse-beike-url 端点
# ============================================================

class TestParseBeikeUrlEndpoint:
    """POST /v1/ai/parse-beike-url 端点集成测试。"""

    @pytest.fixture(autouse=True)
    def _setup_db(self):
        from app.core.database import Base, SessionLocal, engine
        from app.models import (  # noqa: F401
            cooperation, demand, invitation, property, proposal, review, user,
        )
        from app.models.device import Device  # noqa: F401
        from app.models.user import User, UserStatus

        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # 创建测试 user id=1（get_current_user 需要查 user 表）
        with SessionLocal() as session:
            session.add(User(
                id=1, name="test_beike", is_verified=True,
                status=UserStatus.ACTIVE, credit_score=80.0,
                rating_avg=4.0, rating_count=0,
            ))
            session.commit()
        yield

    @pytest.fixture()
    def auth_header(self):
        """JWT for test user id=1（其他 fixture 不用 user，这里简化）。"""
        return {"Authorization": f"Bearer {create_access_token(1)}"}

    def test_valid_url_returns_parsed(
        self, client: TestClient, auth_header: dict
    ):
        """合法 URL → 200 + 解析结果。"""
        r = client.post(
            "/v1/ai/parse-beike-url",
            headers=auth_header,
            json={"url": "https://bj.ke.com/ershoufang/12345.html"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["valid"] is True
        assert data["url_type"] == "ershoufang"
        assert data["house_id"] == "12345"
        assert data["city"] == "bj"

    def test_invalid_url_returns_validation_error(
        self, client: TestClient, auth_header: dict
    ):
        """非贝壳 URL → 10001 ValidationError。"""
        r = client.post(
            "/v1/ai/parse-beike-url",
            headers=auth_header,
            json={"url": "https://www.zhihu.com/question/12345"},
        )
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == 10001
        assert "贝壳" in body["message"] or "ke.com" in body["message"]

    def test_unsupported_path_returns_validation_error(
        self, client: TestClient, auth_header: dict
    ):
        """贝壳域名但不支持的路径 → 10001。"""
        r = client.post(
            "/v1/ai/parse-beike-url",
            headers=auth_header,
            json={"url": "https://bj.ke.com/community/abc"},
        )
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == 10001

    def test_no_auth_returns_401(self, client: TestClient):
        """无 JWT → 401 InvalidTokenError。"""
        r = client.post(
            "/v1/ai/parse-beike-url",
            json={"url": "https://bj.ke.com/ershoufang/12345.html"},
        )
        assert r.status_code == 401
        assert r.json()["code"] == 20003

    def test_empty_url_returns_validation_error(
        self, client: TestClient, auth_header: dict
    ):
        """空 URL → 10001。"""
        r = client.post(
            "/v1/ai/parse-beike-url",
            headers=auth_header,
            json={"url": ""},
        )
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == 10001