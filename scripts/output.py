#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""output.py —— 产物写出：tv.txt + tv.m3u 双格式（aggregate / normalize 共用）。

分组结构统一传入：[(组名, [(频道名, 地址), ...]), ...]，顺序即写出顺序
（调用方保证「茂哥TV」在首位）。

组名 / 频道名里若混入逗号、引号、换行，会破坏 txt / m3u 行结构，
写出前统一清洗（逗号 → 全角，引号 → 单引号）。
"""

M3U_HEAD = "#EXTM3U"


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
