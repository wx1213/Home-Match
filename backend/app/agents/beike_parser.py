"""贝壳链接解析（[D-009] MVP 降级：仅 URL 校验 + 房源 ID 提取）。

MVP 决策：
- 不调 LLM 解析页面内容（D-009 明确禁止，反爬 + 法律风险）
- 不做 HTTP HEAD 可达性检查（Cloudflare 拦截，无意义）
- 仅用正则：
  - 域名校验：`ke.com` / `beike.com` / `fang.ke.com`
  - 路径段提取：ershoufang / loupan / buyhouse / xinfang
  - 房源 ID 提取：路径第二段

支持 URL 模式（实测）：
- 二手房：`https://bj.ke.com/ershoufang/12345.html` 或 `https://ke.com/ershoufang/12345/`
- 新房/楼盘：`https://bj.ke.com/loupan/p_abc123/`
- 购房需求：`https://ke.com/buyhouse/...`
- 城市前缀：bj / sh / gz / sz / 等
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 域名白名单（贝壳系：ke.com / beike.com / 老域名 fang.ke.com）
DOMAIN_RE = re.compile(
    r"^(?:https?://)?(?:[a-z]+\.)?(?:ke\.com|beike\.com|fang\.ke\.com)(?:/|$)",
    re.IGNORECASE,
)

# 路径段提取（[D-009] MVP 只识别 4 类 URL）
PATH_RE = re.compile(
    r"^/?(ershoufang|loupan|buyhouse|xinfang)/([^/?#]+?)(?:\.html)?/?$",
    re.IGNORECASE,
)

# city 前缀提取（如 bj.ke.com / sh.ke.com / gz.ke.com）
CITY_RE = re.compile(
    r"^(?:https?://)?([a-z]+)\.(?:ke|beike)\.com",
    re.IGNORECASE,
)

# 支持的 URL 类型常量
URL_TYPE_ERSHOUFANG = "ershoufang"  # 二手房
URL_TYPE_LOUPAN = "loupan"          # 新房 / 楼盘
URL_TYPE_BUYHOUSE = "buyhouse"      # 购房需求
URL_TYPE_XINFANG = "xinfang"         # 新房（同 loupan）

URL_TYPE_LABELS: dict[str, str] = {
    URL_TYPE_ERSHOUFANG: "二手房",
    URL_TYPE_LOUPAN: "楼盘",
    URL_TYPE_BUYHOUSE: "购房需求",
    URL_TYPE_XINFANG: "新房",
}


@dataclass(frozen=True)
class BeikeParseResult:
    """贝壳链接解析结果。

    valid=False 时 reason 有值；valid=True 时 url_type + house_id + city 至少一个有值。
    """

    valid: bool
    url_type: str | None = None      # ershoufang / loupan / buyhouse / xinfang
    house_id: str | None = None      # 路径第二段（房源 ID）
    city: str | None = None          # bj / sh / gz / 等；根域名时为 None
    reason: str | None = None        # 失败原因（用户友好文案）

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "url_type": self.url_type,
            "house_id": self.house_id,
            "city": self.city,
            "reason": self.reason,
        }


def parse_beike_url(url: str) -> BeikeParseResult:
    """解析贝壳 URL。MVP 仅 regex 校验，不调 LLM 不抓页面。

    Returns:
        BeikeParseResult - 永远不抛异常，所有错误以 valid=False 返回
    """
    if not url or not isinstance(url, str):
        return BeikeParseResult(valid=False, reason="链接为空")

    url = url.strip()

    # 1. 域名白名单
    if not DOMAIN_RE.match(url):
        return BeikeParseResult(
            valid=False,
            reason="不是贝壳系链接（仅支持 ke.com / beike.com / fang.ke.com）",
        )

    # 2. 提取城市前缀
    city = None
    city_match = CITY_RE.match(url)
    if city_match:
        city = city_match.group(1).lower()

    # 3. 提取路径段
    # 去掉 scheme 和域名，拿路径部分
    path = _extract_path(url)
    path_match = PATH_RE.match(path)
    if not path_match:
        return BeikeParseResult(
            valid=False,
            reason="路径格式不支持（仅支持 ershoufang / loupan / buyhouse / xinfang）",
        )

    url_type = path_match.group(1).lower()
    house_id = path_match.group(2).strip()

    return BeikeParseResult(
        valid=True,
        url_type=url_type,
        house_id=house_id,
        city=city,
        reason=None,
    )


def _extract_path(url: str) -> str:
    """从 URL 提取 path 部分（去 scheme + domain + query + fragment）。"""
    # 去掉 scheme
    if "://" in url:
        url = url.split("://", 1)[1]
    # 去掉域名（找第一个 /）
    slash_idx = url.find("/")
    if slash_idx >= 0:
        path = url[slash_idx:]
    else:
        path = "/"
    # 去掉 query / fragment
    if "?" in path:
        path = path.split("?", 1)[0]
    if "#" in path:
        path = path.split("#", 1)[0]
    return path