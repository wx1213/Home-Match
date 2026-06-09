"""Mock 用户名生成器 - 百家姓 + 常见名。

MVP 阶段没有真实微信 unionid/昵称时，用本工具给新用户随机取一个
"看起来像真人"的中文名，提升演示效果。
"""

from __future__ import annotations

import hashlib

# 百家姓前 60 姓（按 2019 年人口普查频次排序）
_BAIJIAXING = [
    "王", "李", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴",
    "徐", "孙", "朱", "马", "胡", "郭", "林", "何", "高", "梁",
    "郑", "罗", "宋", "谢", "唐", "韩", "曹", "许", "邓", "萧",
    "冯", "曾", "程", "蔡", "彭", "潘", "袁", "于", "董", "余",
    "苏", "叶", "吕", "魏", "蒋", "田", "杜", "丁", "沈", "姜",
    "范", "江", "傅", "钟", "卢", "汪", "戴", "崔", "任", "陆",
]

# 常见单字名（按使用频次）
_MINGZI_SINGLE = [
    "伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋",
    "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "霞", "平",
    "刚", "桂英", "鹏", "华", "婷", "慧", "倩", "建华", "文", "凯",
    "建国", "宇", "浩然", "欣", "怡", "思远", "子轩", "梓涵", "雨桐", "可昕",
    "嘉怡", "诗涵", "一鸣", "泽", "辰", "昊", "睿", "璇", "雅", "琪",
]

# 常见双字名（姓+双字）
_MINGZI_DOUBLE = [
    "子轩", "梓涵", "雨桐", "可昕", "嘉怡", "诗涵", "一鸣", "浩然", "思远", "欣怡",
    "建国", "建华", "志强", "晓明", "佳琪", "雅琪", "嘉辉", "雨涵", "雨泽", "俊熙",
]


def _seed_from_string(s: str) -> int:
    """把字符串转成稳定的随机种子（保证同一 code 拿同一名字）。"""
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)


def generate_mock_name(seed_source: str) -> tuple[str, str]:
    """根据 code 稳定生成 (name, display_name)。

    Args:
        seed_source: 任意字符串（一般用 wechat code）

    Returns:
        (name, display_name) — name 是真实姓+名，display_name 是展示名
    """
    seed = _seed_from_string(seed_source)
    surname = _BAIJIAXING[seed % len(_BAIJIAXING)]
    # 60% 用双字名，40% 用单字名
    if seed % 10 < 6:
        first_char = _MINGZI_DOUBLE[(seed // 10) % len(_MINGZI_DOUBLE)]
        display = _MINGZI_SINGLE[(seed // 100) % len(_MINGZI_SINGLE)]
    else:
        first_char = _MINGZI_SINGLE[(seed // 10) % len(_MINGZI_SINGLE)]
        display = _MINGZI_DOUBLE[(seed // 100) % len(_MINGZI_DOUBLE)]

    name = f"{surname}{first_char}"  # 全名（脱敏前用）
    display_name = f"{surname}{display}"  # 展示名
    return name, display_name
