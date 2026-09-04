#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""normalize_tv.py —— tv.txt / tv.m3u 最后一道关卡：归一 / 去重 / 排序 / 校验 / 双格式产出。

本版（不重新分组模式）：
    1. 分组原样保留：上游组叫什么，产物就叫什么，不做任何关键词归类、不错组纠偏。
    2. 茂哥TV 强制置顶（条目顺序由 mgou_tv.txt 人工维护，不受排序影响）。
    3. 频道名归一（canonical）+ 同组去重 + 清晰度标签折叠（均在组内进行，不改组名）。
    4. 同步产出 tv.txt 与 tv.m3u（组名、条目、顺序完全一致）。
"""
import os
import re
import sys

from collections import OrderedDict

from canonical import canonical_name, canonical_name_keep_label, split_clarity
from output import write_txt, write_m3u

OUTPUT = "tv.txt"
MGOU_GROUP = "茂哥TV"
VALID_SCHEMES = ("http://", "https://", "rtp://", "rtsp://", "udp://")
DIRTY = ('"', "group-title=", "tvg-logo=", "tvg-name=", "tvg-id=", "response-time=", "#EXT")
_CCTV = re.compile(r"CCTV[- ]?(\d+)")

# 顺序由人工维护、规范化阶段不得重排 / 不得改名的分组
KEEP_ORDER_GROUPS = (MGOU_GROUP,)


def is_genre(line: str) -> bool:
    return line.endswith("#genre#") or line.endswith("#genre#,")


def _sort_key(name: str):
    m = _CCTV.search(name)
    if m:
        return (0, int(m.group(1)), 1 if "+" in name else 0, name.lower())
    return (1, 0, 0, name.lower())


def build(path: str = OUTPUT):
    if not os.path.exists(path):
        print(f"[FATAL] 未找到 {path}，请先运行 aggregate.py", file=sys.stderr)
        sys.exit(1)

    buckets = OrderedDict()
    seen, dropped = set(), 0
    current = None
    for line in open(path, encoding="utf-8", errors="ignore").read().splitlines():
        line = line.strip()
        if not line:
            continue
        if is_genre(line):
            header = line.rstrip(",")
            current = header[:-len("#genre#")].strip().rstrip(",").strip()
            current = current.replace(",", "，").strip() or "未分组"
            buckets.setdefault(current, [])
            continue
        if line.startswith("#") or "," not in line:
            dropped += 1
            continue
        name, url = (x.strip() for x in line.split(",", 1))
        if not name or not url or not url.startswith(VALID_SCHEMES):
            dropped += 1
            continue
        if any(m in name for m in DIRTY):
            dropped += 1
            continue
        if current is None:
            current = "未分组"
            buckets.setdefault(current, [])

        # ★ 归一放在去重之前：否则「CCTV-1」与「CCTV-1 综合」是两条 key，
        #   永远合并不掉 —— 这正是去重形同虚设的根因。
        if current not in KEEP_ORDER_GROUPS:
            name = canonical_name_keep_label(name)

        key = (current, name, url)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        buckets[current].append((name, url))

    # ---- 茂哥TV 强制置顶（其余分组保持文件中的先后顺序）----
    groups = []
    if MGOU_GROUP in buckets:
        groups.append((MGOU_GROUP, buckets.pop(MGOU_GROUP)))
    groups += list(buckets.items())

    # ---- 组内：清晰度标签折叠 + 排序（茂哥TV 除外，顺序人工维护）----
    folded = 0
    final = []
    for g, items in groups:
        if g not in KEEP_ORDER_GROUPS:
            bare = {nm for nm, _ in items if not split_clarity(nm)[1]}
            merged, seen2 = [], set()
            for nm, url in items:
                if split_clarity(nm)[1]:
                    base = canonical_name(nm)
                    if base in bare:
                        if base != nm:
                            folded += 1
                        nm = base
                key = (nm, url)
                if key in seen2:
                    dropped += 1
                    continue
                seen2.add(key)
                merged.append((nm, url))
            items = sorted(merged, key=lambda nu: _sort_key(nu[0]))
        final.append((g, items))
    if folded:
        print(f"[FIX] 清晰度标签折叠 {folded} 条（与同名裸频道合并）")
    return final, dropped


def verify(lines):
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s or is_genre(s):
            continue
        if "," not in s:
            print(f"[FAIL] 第 {i} 行无逗号: {s[:120]}")
            return False
        name, url = (x.strip() for x in s.split(",", 1))
        if not name or not url:
            print(f"[FAIL] 第 {i} 行缺名称/地址: {s[:120]}")
            return False
        if not url.startswith(VALID_SCHEMES):
            print(f"[FAIL] 第 {i} 行地址非法: {s[:120]}")
            return False
    return True


def normalize(path: str = OUTPUT):
    groups, dropped = build(path)
    out = []
    for gi, (g, items) in enumerate(groups):
        if gi > 0:
            out.append("")
        out.append(f"{g},#genre#")
        out += [f"{nm},{url}" for nm, url in items]
    if not verify(out):
        print("存在非标准行，未写入", file=sys.stderr)
        sys.exit(1)
    m3u_path = path[:-len(".txt")] + ".m3u" if path.endswith(".txt") else path + ".m3u"
    write_txt(groups, path)
    write_m3u(groups, m3u_path)
    genres = sum(1 for g, items in groups if items)
    items_n = sum(len(items) for _, items in groups)
    print(f"[DONE] {path} + {m3u_path}: {genres} 分组, {items_n} 条（丢弃 {dropped}）")


if __name__ == "__main__":
    normalize()
