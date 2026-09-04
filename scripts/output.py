#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""output.py —— 产物写出：tv.txt + tv.m3u 双格式（aggregate / normalize 共用）。
分组结构统一传入：[(组名, [(频道名, 地址), ...]), ...]，顺序即写出顺序。
order_groups() 负责组间排队：「茂哥TV」钉在首位，其余
央视 → 卫视 → 地方 → 港澳台/国际 → 其他（同档保持出现先后，组内顺序不动）。

组名 / 频道名里若混入逗号、引号、换行，会破坏 txt / m3u 行结构，
写出前统一清洗（逗号 → 全角，引号 → 单引号）。
"""

M3U_HEAD = "#EXTM3U"

# ==================== 分组分档排序：央视 → 卫视 → 地方 → 港澳台/国际 → 其他 ====================
# 只按「组名关键词」分档、不改组名（不重新分组）；同档内保持出现先后（稳定排序）。
# 「茂哥TV」由调用方钉在首位（pin_first），不参与分档。
_GROUP_TIERS = (
    (1, ("央视", "中央", "cctv", "cgtn")),                          # 中央
    (2, ("卫视",)),                                                 # 卫视
    (3, ("地方", "省市", "省台", "省级")),                           # 地方
    (4, ("港澳", "香港", "澳门", "台湾", "国际", "境外", "海外")),    # 港澳台 / 国际
)


def group_tier(name: str) -> int:
    """组名分档：1 央视 / 2 卫视 / 3 地方 / 4 港澳台国际 / 9 其他。"""
    low = (name or "").lower()
    for tier, kws in _GROUP_TIERS:
        if any(k in low for k in kws):
            return tier
    return 9


def order_groups(groups, pin_first=()):
    """分组按档稳定排序（央视→卫视→地方→港澳台/国际→其他）。

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
