#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""output.py —— 产物写出：tv.txt + tv.m3u 双格式（aggregate / normalize 共用）。
分组结构统一传入：[(组名, [(频道名, 地址), ...]), ...]，顺序即写出顺序。
order_groups() 负责组间排队：「茂哥TV」钉在首位，其余
央视 → 卫视 → 地方 → 香港 → 台湾/澳门 → 体育 → 影视 → 新闻 → 少儿 → 其余（同档保持出现先后）。

is_central_channel() 判断频道名是否属于央视（CCTV/CGTN/CETV/CHC），
用于将所有央视频道从多个上游组合并到单一「央视频道」组。
merge_group_name() 将上游含关键词的组名合并到统一分组名。

组名 / 频道名里若混入逗号、引号、换行，会破坏 txt / m3u 行结构，
写出前统一清洗（逗号 → 全角，引号 → 单引号）。
"""

import re

M3U_HEAD = "#EXTM3U"
CENTRAL_GROUP = "央视频道"
_MGOU_GROUP = "茂哥TV"
_CENTRAL_RE = re.compile(r"^(CCTV|央视|CGTN|CETV|CHC|中国教育)", re.I)


def is_central_channel(name: str) -> bool:
    """判断频道名是否属于央视（CCTV/CGTN/CETV/CHC/中国教育）。"""
    return bool(_CENTRAL_RE.match(name or ""))


# ==================== 分组合并：按关键词将上游组名归并 ====================
# 顺序很重要：先匹配更具体的关键词（港澳台），再匹配更宽泛的（香港、台湾）
_GROUP_MERGE_RULES = [
    ("港澳台", "香港频道"),
    ("港台", "香港频道"),
    ("央视", "央视频道"),
    ("卫视", "卫视频道"),
    ("地方", "地方频道"),
    ("香港", "香港频道"),
    ("台湾", "台湾频道"),
    ("澳门", "澳门频道"),
]


def merge_group_name(group: str) -> str:
    """将上游组名合并到统一分组名。

    · 含「央视」→ 央视频道；含「卫视」→ 卫视频道；含「地方」→ 地方频道
    · 含「香港」/「港澳台」/「港台」→ 香港频道；含「台湾」→ 台湾频道；含「澳门」→ 澳门频道
    · 「茂哥TV」「其他」「未分组」等保留原名，不合并
    · 其余组名原样返回
    """
    g = (group or "").strip()
    if not g or g == _MGOU_GROUP or g in ("其他", "其他频道", "未分组"):
        return g
    for kw, target in _GROUP_MERGE_RULES:
        if kw in g:
            return target
    return g


# ==================== 分组分档排序 ====================
# 央视→卫视→地方→香港→台湾/澳门→体育→影视→新闻→少儿→其余按上游顺序
_GROUP_TIERS = (
    (1, ("央视", "中央", "cctv", "cgtn")),                          # 央视
    (2, ("卫视",)),                                                 # 卫视
    (3, ("地方", "省市", "省台", "省级")),                           # 地方
    (4, ("香港",)),                                                 # 香港
    (5, ("台湾", "澳门")),                                          # 台湾/澳门
    (6, ("体育",)),                                                 # 体育
    (7, ("电影", "影视", "轮播")),                                   # 影视
    (8, ("新闻", "new", "资讯")),                                   # 新闻
    (9, ("少儿", "卡通", "动漫", "儿童")),                          # 少儿
)


def group_tier(name: str) -> int:
    """组名分档排序号（越小越靠前）。"""
    low = (name or "").lower()
    for tier, kws in _GROUP_TIERS:
        if any(k in low for k in kws):
            return tier
    return 99


def order_groups(groups, pin_first=()):
    """分组按档稳定排序。

    groups: [(组名, [(频道名, 地址), ...]), ...]
    pin_first 中的组（如「茂哥TV」）钉在最前、组内顺序不变；
    其余组只调组间顺序，组内条目顺序不动。
    """
    pin = tuple(pin_first)
    pinned = [g for g in groups if g[0] in pin]
    rest = [g for g in groups if g[0] not in pin]
    rest.sort(key=lambda g: group_tier(g[0]))  # 同档保持原顺序（sorted 稳定）
    return pinned + rest


def _sanitize(s: str) -> str:
    s = (s or "").strip()
    return (s.replace(",", "，").replace('"', "'")
             .replace("\r", " ").replace("\n", " ").strip())


def write_txt(groups, path: str):
    """写 tv.txt：分组头「组名,#genre#」，条目「频道名,地址」，组间空行。"""
    blocks = []
    for g, items in groups:
        if not items:
            continue  # 空组不写出（无效组源自然消失）
        lines = [f"{_sanitize(g)},#genre#"]
        lines += [f"{_sanitize(nm)},{url.strip()}" for nm, url in items]
        blocks.append("\n".join(lines))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(blocks) + ("\n" if blocks else ""))


def write_m3u(groups, path: str):
    """写 tv.m3u：与 tv.txt 同一组名、同一条目、同一顺序。"""
    lines = [M3U_HEAD]
    for g, items in groups:
        if not items:
            continue
        gs = _sanitize(g)
        for nm, url in items:
            ns = _sanitize(nm)
            lines.append(f'#EXTINF:-1 tvg-name="{ns}" group-title="{gs}",{ns}')
            lines.append(url.strip())
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
