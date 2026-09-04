#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ci_assert.py —— tv.txt / tv.m3u 断言（供 GitHub Actions 调用）。

用法：
    python scripts/ci_assert.py [tv.txt]

退出码：
    0 = 通过（或仅有警告）
    1 = 存在阻断级违规

本版断言（不重新分组模式 —— 分组来自上游源，不再对组内容做关键词断言）：
    1. 名称唯一形态（阻断）：非茂哥TV 组内不允许残留 canonical 别名写法。
    2. 茂哥TV 不变量（阻断）：分组存在、非空、置顶第一、顺序与 mgou_tv.txt 一致。
    3. 双格式一致性（阻断）：tv.m3u 与 tv.txt 的组名 / 条目 / 顺序完全一致。
    4. 环境警告（非阻断）：上游全挂时仅有茂哥TV；CI_STRICT=1 可升级为阻断。
"""
import os
import re
import sys

from collections import OrderedDict

from canonical import canonical_name_keep_label

DEFAULT = "tv.txt"
STRICT = os.environ.get("CI_STRICT", "0").lower() in ("1", "true", "yes")
MGOU_FILE = "mgou_tv.txt"
MGOU_GROUP = "茂哥TV"


def warn(msg: str):
    _WARN_MSGS.append(msg)


_WARN_MSGS = []


def _load_txt(path: str):
    """返回 (OrderedDict[group] -> [name...], [(group, name, url)...] 顺序条目)。"""
    if not os.path.exists(path):
        print(f"[FATAL] 未找到 {path}", file=sys.stderr)
        sys.exit(2)
    groups = OrderedDict()
    entries = []
    cur = None
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("#genre#"):
            cur = line[:-len("#genre#")].strip().rstrip(",").strip()
            groups.setdefault(cur, [])
            continue
        if "," not in line:
            continue
        nm, url = (x.strip() for x in line.split(",", 1))
        if cur:
            groups[cur].append(nm)
            entries.append((cur, nm, url))
    return groups, entries


def _load_m3u(path: str):
    """解析 m3u 为 [(group, name, url)...]（与 write_m3u 的写出格式对应）。"""
    entries = []
    cur_group, pending = "", None
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = re.search(r"""group-title\s*=\s*["']([^"']*)["']""", line, re.I)
            cur_group = m.group(1) if m else ""
            pending = line.partition(",")[2].strip()
        elif line.startswith("#"):
            continue
        elif pending is not None:
            entries.append((cur_group, pending, line))
            pending = None
    return entries


def _load_mgou_names():
    """受版本控制的置顶节目名（顺序即展示顺序）。"""
    if not os.path.exists(MGOU_FILE):
        return []
    names, started = [], False
    for raw in open(MGOU_FILE, encoding="utf-8", errors="ignore"):
        line = raw.strip()
        if not line:
            continue
        if line.endswith("#genre#"):
            started = line[:-len("#genre#")].strip().rstrip(",").strip() == MGOU_GROUP
            continue
        if started and "," in line:
            names.append(line.split(",", 1)[0].strip())
    return names


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    groups, entries = _load_txt(path)
    failures = []

    # 1. 名称唯一形态（阻断级）：产物里不允许残留任何别名写法
    alias_left = []
    for g, names in groups.items():
        if g == MGOU_GROUP:
            continue  # 人工维护，豁免改名
        for nm in names:
            if canonical_name_keep_label(nm) != nm:
                alias_left.append(f"{g}: {nm} -> {canonical_name_keep_label(nm)}")
    if alias_left:
        shown = alias_left[:20]
        failures.append("[名称规范] 仍存在未归一的别名写法"
                        f"（共 {len(alias_left)} 处，示例：{'；'.join(shown)}）")

    # 2. 不变量：茂哥TV 必须存在、非空、置顶第一、顺序不变（阻断级）
    if MGOU_GROUP not in groups:
        failures.append("[不变量] 缺少「茂哥TV」分组")
    elif not groups[MGOU_GROUP]:
        failures.append("[不变量] 「茂哥TV」分组为空")
    else:
        if next(iter(groups), None) != MGOU_GROUP:
            failures.append("[不变量] 「茂哥TV」未置顶（必须在第一个分组）")
        want = _load_mgou_names()
        got = groups[MGOU_GROUP]
        if want and len(got) < len(want):
            failures.append(f"[不变量] 「茂哥TV」条目缺失 {len(got)}/{len(want)} 条")
        elif want and got[:len(want)] != want:
            failures.append(f"[不变量] 「茂哥TV」顺序被改动：{got[:len(want)]}")

    # 3. 双格式一致性（阻断级）：tv.m3u 必须与 tv.txt 完全对应
    m3u_path = path[:-len(".txt")] + ".m3u" if path.endswith(".txt") else path + ".m3u"
    if not os.path.exists(m3u_path):
        failures.append(f"[双格式] 缺少 {m3u_path}（normalize_tv.py 应同步产出）")
    else:
        m3u_entries = _load_m3u(m3u_path)
        if m3u_entries != entries:
            diff_at = next((i for i, (a, b) in enumerate(zip(entries, m3u_entries)) if a != b), None)
            failures.append(
                f"[双格式] {m3u_path} 与 {path} 不一致"
                f"（txt {len(entries)} 条 / m3u {len(m3u_entries)} 条"
                f"{f'，首个差异在第 {diff_at + 1} 条' if diff_at is not None else ''}）")

    # 4. 环境警告（非阻断级）
    total = sum(len(v) for v in groups.values())
    if total <= len(groups.get(MGOU_GROUP, [])):
        msg = "[环境] 除茂哥TV 外无任何频道（上游源可能全部不可用）"
        (failures if STRICT else _WARN_MSGS).append(msg)

    print("=" * 60)
    if failures:
        print(f"CI ASSERT FAILED ({len(failures)} 项阻断)")
        print("=" * 60)
        for f in failures:
            print("  - " + f)
        for w in _WARN_MSGS:
            print(f"  ! {w} (warn)")
        sys.exit(1)

    print("CI ASSERT PASSED")
    print("=" * 60)
    print(f"  分组数        : {len(groups)}")
    print(f"  总条目        : {total}")
    print(f"  双格式        : tv.txt 与 tv.m3u 完全一致")
    print(f"  名称规范      : 无别名残留（CCTV / CGTN / CETV / CHC 均为唯一形态）")
    for w in _WARN_MSGS:
        print(f"  ! {w} (warn, 非阻断；CI_STRICT=1 可升级为阻断)")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
