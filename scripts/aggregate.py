#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aggregate.py —— 多源聚合（不重新分组）+ 剔除无效源 + 茂哥TV 置顶，产出 tv.txt / tv.m3u。

本版核心逻辑（相对旧版的关键变化）：
    ★ 不再按关键词重新分组：频道沿用上游源自己的分组
      （txt 的「组名,#genre#」头 / m3u 的 group-title 属性），
      上游叫什么组，产物就叫什么组。
    ★ 跨源组名冲突时按出现顺序加序号区分：
      第二个同名组 →「组名2」，第三个 →「组名3」……
    ★ 组名黑名单：group_blacklist.txt 命中的分组整组剔除。
    ★ 频道名黑名单：name_blacklist.txt 命中的节目整条剔除。
    ★ 无效源剔除：validate_lite.py 并发探测，连接失败 / 404 / 410 判死剔除。
    ★ 茂哥TV 置顶不变：mgou_tv.txt 完全隔离，不参与黑名单 / 探测 / 剔除 / 排序。
    ★ 自动识别 txt / m3u：按内容探测格式，无需在 sources.txt 标注类型。
    ★ 双格式产出：tv.txt 与 tv.m3u 同步写出（组名、条目、顺序完全一致）。

后期可变量（改哪里）：
    · 上游源列表         sources.txt（仓库根目录，一行一个 URL）
    · 置顶节目           mgou_tv.txt（仓库根目录，格式「节目名,地址」）
    · 组名黑名单         group_blacklist.txt（仓库根目录，每行一个组名）
    · 频道名黑名单       name_blacklist.txt（仓库根目录，每行一个频道名）
    · 运行参数           .github/workflows/live-aggregator.yml 各 step 的 env（含注释）
    · 探测参数           scripts/validate_lite.py 顶部注释
"""
import os
import re
import sys
import time
import urllib.request
from collections import OrderedDict

from canonical import canonical_name_keep_label
from output import write_txt, write_m3u
from validate_lite import validate_urls
from speed_test_lite import speed_test as lite_speed_test, speed_sort_key
from probe_resolution import probe_batch, relabel_name

SOURCES_FILE = "sources.txt"             # ★ 上游源列表（可修改：仓库根目录 sources.txt）
MGOU_FILE = "mgou_tv.txt"                # ★ 茂哥TV 置顶节目（可修改：仓库根目录 mgou_tv.txt）
GROUP_BLACKLIST_FILE = os.environ.get("GROUP_BLACKLIST", "group_blacklist.txt")
NAME_BLACKLIST_FILE = os.environ.get("NAME_BLACKLIST", "name_blacklist.txt")
OUTPUT = "tv.txt"
RAW_OUTPUT = "tv_raw.txt"
MGOU_GROUP = "茂哥TV"
UNGROUPED = "未分组"

REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "20"))
MAX_RETRY = int(os.environ.get("MAX_RETRY", "2"))
PROBE_WORKERS = int(os.environ.get("PROBE_WORKERS", "8"))
USER_AGENT = "Mozilla/5.0 (compatible; IPTV-Aggregator/2.0)"

MIN_HEIGHT = int(os.environ.get("MIN_HEIGHT", "720"))

VALID_SCHEMES = ("http://", "https://", "rtp://", "rtsp://", "udp://")
HTTP_SCHEMES = ("http://", "https://")
DIRTY_NAME_MARKERS = (
    '"', "group-title=", "tvg-logo=", "tvg-name=",
    "tvg-id=", "response-time=", "#EXT",
)

_GROUP_TITLE_RE = re.compile(r"""group-title\s*=\s*["']([^"']*)["']""", re.I)


# ==================== [1] 抓取与解析（自动识别 txt / m3u）====================

def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def read_local_or_remote(src: str) -> str:
    if src.startswith(("http://", "https://")):
        last_err = None
        for _ in range(MAX_RETRY + 1):
            try:
                return fetch_url(src)
            except Exception as e:
                last_err = e
                time.sleep(1)
        raise RuntimeError(f"下载失败 {src}: {last_err}")
    with open(src, "rb") as f:
        return f.read().decode("utf-8", errors="ignore")


def load_sources(path: str = SOURCES_FILE):
    if not os.path.exists(path):
        print(f"[WARN] 未找到 {path}，跳过抓取", file=sys.stderr)
        return []
    lines = []
    for raw in read_local_or_remote(path).splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines


def _clean_group(g: str) -> str:
    """组名清洗：去掉引号 / 逗号 / 空白，空组名归「未分组」。"""
    g = (g or "").strip().strip('"\'').replace(",", "，")
    g = g.replace("\t", " ").strip()
    return g or UNGROUPED


def parse_m3u_or_txt(text: str):
    """自适应解析 m3u / txt，返回 [(组名, 频道名, 地址), ...]。

    · txt：以「组名,#genre#」行为分组头，头前条目归「未分组」。
    · m3u：取 #EXTINF 的 group-title 属性（兼容 #EXTGRP: 行），缺失归「未分组」。
    · 格式按内容自动识别（#EXTM3U / #EXTINF 计数），与文件后缀无关。
    """
    items = []
    lines = text.splitlines()
    is_m3u = any(l.strip().startswith("#EXTM3U") for l in lines[:20]) or \
             sum(1 for l in lines if "#EXTINF" in l) > 3

    if is_m3u:
        pending_name = None
        pending_group = UNGROUPED
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#EXTINF"):
                _, _, title = line.partition(",")
                m = _GROUP_TITLE_RE.search(line)
                pending_group = _clean_group(m.group(1)) if m else UNGROUPED
                pending_name = title.strip() or None
            elif line.startswith("#EXTGRP:"):
                pending_group = _clean_group(line[len("#EXTGRP:"):])
            elif line.startswith("#") or not pending_name:
                continue
            elif line.startswith(VALID_SCHEMES):
                items.append((pending_group, pending_name or "unknown", line))
                pending_name = None
            else:
                pending_name = None
    else:
        current = UNGROUPED
        for raw in lines:
            line = raw.strip().rstrip(",")
            if not line or line.startswith("#"):
                continue
            if line.endswith("#genre#"):
                current = _clean_group(line[:-len("#genre#")].rstrip(","))
                continue
            if "," not in line:
                continue
            nm, _, url = line.partition(",")
            nm, url = nm.strip(), url.strip()
            if nm and url:
                items.append((current, nm, url))
    return items


def aggregate(sources):
    """逐源抓取解析，返回 [每个源的 [(组名, 频道名, 地址), ...]]（保持源顺序）。"""
    sources_items = []
    ok = 0
    for src in sources:
        try:
            text = read_local_or_remote(src)
        except Exception as e:
            print(f"[WARN] 抓取失败，跳过: {src} ({e})", file=sys.stderr)
            sources_items.append([])
            continue
        try:
            items = parse_m3u_or_txt(text)
        except Exception as e:
            print(f"[WARN] 解析失败，跳过: {src} ({e})", file=sys.stderr)
            sources_items.append([])
            continue
        dedup = OrderedDict()
        for g, nm, url in items:
            if nm and url.startswith(VALID_SCHEMES):
                dedup.setdefault((g, nm, url), True)
        lst = list(dedup.keys())
        groups = len({g for g, _, _ in lst})
        sources_items.append(lst)
        ok += 1
        print(f"[FETCH] {src} -> {len(lst)} 条 / {groups} 组")
    print(f"[AGG] {ok}/{len(sources)} 个源成功")
    return sources_items


# ==================== [2] 黑名单与组名处理 ====================

def _read_text(path: str) -> str:
    data = open(path, "rb").read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="ignore")


def _load_blacklist(path: str, label: str) -> set:
    """黑名单文件：每行一个名称，# 开头为注释（不支持行内注释）。"""
    if not os.path.exists(path):
        print(f"[WARN] 未找到{label}: {path}（在仓库根目录创建即可启用）", file=sys.stderr)
        return set()
    names = set()
    for raw in _read_text(path).splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            names.add(s)
    print(f"[BL] {label}载入 {len(names)} 条（{path}）")
    return names


_NAME_BL = None


def _name_blacklist() -> set:
    global _NAME_BL
    if _NAME_BL is None:
        _NAME_BL = _load_blacklist(NAME_BLACKLIST_FILE, "频道名黑名单")
    return _NAME_BL


def apply_group_blacklist(sources_items, blacklist: set):
    """对上游「原始组名」生效：命中的分组整组剔除。"""
    if not blacklist:
        return sources_items, 0
    out, dropped = [], 0
    dropped_groups = []
    for src in sources_items:
        keep = []
        for g, nm, url in src:
            if g in blacklist:
                dropped += 1
                if g not in dropped_groups:
                    dropped_groups.append(g)
            else:
                keep.append((g, nm, url))
        out.append(keep)
    if dropped:
        shown = "、".join(dropped_groups[:8]) + ("…" if len(dropped_groups) > 8 else "")
        print(f"[BL] 组名黑名单剔除 {dropped} 条（组：{shown}）")
    return out, dropped


def drop_reserved_group(sources_items):
    """剥离上游混入的「茂哥TV」组：保留组名只归置顶区（mgou_tv.txt）。"""
    out, dropped = [], 0
    for src in sources_items:
        keep = [(g, nm, url) for g, nm, url in src if g != MGOU_GROUP]
        dropped += len(src) - len(keep)
        out.append(keep)
    if dropped:
        print(f"[MGOU] 上游同名组剔除 {dropped} 条（由置顶源 {MGOU_FILE} 接管）")
    return out


def renumber_groups(sources_items):
    """跨源组名冲突时按出现顺序加序号：第二个同名组 →「组名2」，依此类推。

    同一源内同名组合并为一个组；「茂哥TV」为保留名（置顶区专用）。
    """
    taken = {MGOU_GROUP}
    out = []
    for src in sources_items:
        mapped = {}
        res = []
        for g, nm, url in src:
            if g not in mapped:
                if g not in taken:
                    mapped[g] = g
                else:
                    n = 2
                    while f"{g}{n}" in taken:
                        n += 1
                    mapped[g] = f"{g}{n}"
                    print(f"[GROUP] 组名冲突：「{g}」→「{mapped[g]}」")
                taken.add(mapped[g])
            res.append((mapped[g], nm, url))
        out.append(res)
    return out


# ==================== [3] 规范化与写出 ====================

def normalize_text_line(name: str, url: str):
    name, url = name.strip(), url.strip()
    if not name or not url or not url.startswith(VALID_SCHEMES):
        return None
    if any(m in name for m in DIRTY_NAME_MARKERS):
        return None
    return (name, url)


def write_raw(items, path: str = RAW_OUTPUT):
    """调试用：扁平中间产物（保留组名，不写 m3u）。"""
    groups = OrderedDict()
    for g, nm, url in items:
        groups.setdefault(g, []).append((nm, url))
    write_txt(list(groups.items()), path)
    print(f"[DONE] 调试中间产物 {path}（{len(items)} 条，跳过正式写出）")


def _load_mgou_items() -> list:
    """读取受版本控制的茂哥TV 置顶节目；缺失则返回空（不阻断）。"""
    if not os.path.exists(MGOU_FILE):
        return []
    try:
        items = parse_m3u_or_txt(_read_text(MGOU_FILE))
        mgou, _ = split_mgou(items)
        dedup = OrderedDict()
        for nm, url in mgou:
            dedup.setdefault((nm, url), True)
        items = list(dedup.keys())
        print(f"[MGOU] 置顶源 {MGOU_FILE} -> {len(items)} 条（完全隔离、不参与黑名单 / 探测 / 剔除）")
        return items
    except Exception as e:
        print(f"[WARN] 读取 {MGOU_FILE} 失败: {e}", file=sys.stderr)
        return []


def split_mgou(items):
    """[(组名, 频道名, 地址)] -> (茂哥TV条目 [(名, 地址)], 其余 [(组名, 名, 地址)])。"""
    mgou, others = [], []
    for g, nm, url in items:
        if g == MGOU_GROUP:
            mgou.append((nm, url))
        else:
            others.append((g, nm, url))
    return mgou, others


def _strip_mgou(items):
    """入口防御：硬性剥离名称含「茂哥TV」的条目（防止上游伪装混入置顶区）。"""
    others, leaked = [], 0
    for g, nm, url in items:
        if MGOU_GROUP in (nm or ""):
            leaked += 1
        else:
            others.append((g, nm, url))
    if leaked:
        print(f"[MGOU] 入口剥离混入的茂哥TV条目 {leaked} 条（已交由置顶区单独输出）")
    return others


_LABEL_H_RE = re.compile(r"[\(（](\d{2,4})[ip]p?[\)）]", re.I)
_TAG_RE = re.compile(r"[\(（]\d{2,4}[ip]p?[\)）]|HD|UHD", re.I)
_CCTV_RE = re.compile(r"CCTV[- ]?(\d+)")


def _label_height(nm: str) -> int:
    m = _LABEL_H_RE.search(nm or "")
    return int(m.group(1)) if m else 0


def _sort_key(name: str):
    m = _CCTV_RE.search(name)
    if m:
        return (0, int(m.group(1)), 1 if "+" in name else 0, name.lower())
    return (1, 0, 0, name.lower())


def _sort_items(items, speed_results=None):
    """组内排序：CCTV 按编号升序，其余按名称；有测速数据时快者在前。"""
    if not speed_results:
        return sorted(items, key=lambda x: _sort_key(x[0]))
    return sorted(items, key=lambda x: (_sort_key(x[0]), speed_sort_key(x[1], speed_results)))


def validate_stage(items):
    """剔除无效节目源（http/https 才能探测；rtp/rtsp/udp 保守保留）。"""
    if os.environ.get("DISABLE_VALIDATE", "0") == "1":
        print("[VALIDATE] 已关闭（DISABLE_VALIDATE=1），跳过剔除")
        return items, 0
    http_items = [(g, nm, u) for g, nm, u in items if u.startswith(HTTP_SCHEMES)]
    other_items = [(g, nm, u) for g, nm, u in items if not u.startswith(HTTP_SCHEMES)]
    results = validate_urls([(nm, u) for _, nm, u in http_items])
    kept, dropped = list(other_items), 0
    for g, nm, u in http_items:
        info = results.get(u)
        if info is not None and not info.get("alive"):
            dropped += 1
            continue
        kept.append((g, nm, u))
    print(f"[VALIDATE] 剔除无效源 {dropped} 条（未覆盖项保守保留）")
    return kept, dropped


def m3u_path_of(txt_path: str) -> str:
    """tv.txt → tv.m3u：m3u 路径跟随 txt 路径派生。"""
    return txt_path[:-len(".txt")] + ".m3u" if txt_path.endswith(".txt") else txt_path + ".m3u"


def _write_out(items, mgou_items, dst, speed_results=None, label="[DONE]"):
    """组装分组 → 排序 → 写 tv.txt + tv.m3u，返回总条数。"""
    speed_results = speed_results or {}
    buckets = OrderedDict()
    for g, nm, url in items:
        buckets.setdefault(g, OrderedDict())
        buckets[g].setdefault(nm, OrderedDict())
        if url not in buckets[g][nm]:
            buckets[g][nm][url] = (speed_results.get(url) or {}).get("response_time")

    groups = []
    if mgou_items:
        groups.append((MGOU_GROUP, list(mgou_items)))   # ★ 茂哥TV 永远置顶
    for g, grp in buckets.items():
        flat = [(nm, url) for nm, urls in grp.items() for url in urls]
        groups.append((g, _sort_items(flat, speed_results or None)))
    groups = [(g, it) for g, it in groups if it]        # 空组剔除
    groups = order_groups(groups, pin_first=(MGOU_GROUP,))  # ★ 茂哥TV 置顶；其余 央视→卫视→地方→港澳台/国际→其他

    write_txt(groups, dst)
    write_m3u(groups, m3u_path_of(dst))
    total = sum(len(it) for _, it in groups)
    print(f"{label} {dst} + {m3u_path_of(dst)}（{len(groups)} 组 / {total} 条，茂哥TV 置顶）")
    return total


def regroup_and_write(items, dst: str, mgou_items=None):
    """主管线：黑名单 → 门槛 → 剔除无效源 → 保底写出 → 实测 → 测速 → 最终写出。"""
    if mgou_items is None:
        mgou_items = []
    other = _strip_mgou(items)  # ★ 硬隔离

    # ---- [阶段 0a] 频道名黑名单 ----
    name_bl = _name_blacklist()
    if name_bl:
        before = len(other)
        other = [t for t in other if t[1] not in name_bl]
        if before != len(other):
            print(f"[BL] 频道名黑名单剔除 {before - len(other)} 条")

    # ---- [阶段 0b] 名称标签门槛 ----
    # 必须用「原始名称」判定：canonical 会剥掉 (360p) 这类分辨率标签。
    if MIN_HEIGHT > 0:
        before = len(other)
        other = [(g, nm, u) for g, nm, u in other
                 if not _label_height(nm) or _label_height(nm) >= MIN_HEIGHT]
        if before != len(other):
            print(f"[INFO] 名称标签门槛 <{MIN_HEIGHT}p 预筛 {before - len(other)} 条")

    # ---- [阶段 0c] 去重（组名 + 名称 + 地址 三元组）----
    seen, dedup = set(), []
    for t in other:
        if t not in seen:
            seen.add(t)
            dedup.append(t)
    other = dedup

    # ---- [阶段 0d] 剔除无效源（并发探测，带缓存与预算）----
    other, _vdropped = validate_stage(other)

    # ---- [阶段 1] 保底写出 ----
    # 纯 CPU 秒级完成。即使后面的抓流/测速把 job 拖到超时被取消，
    # 仓库里也已经有一份合法、规范、过了门槛的 tv.txt / tv.m3u。
    if os.environ.get("EARLY_WRITE", "true").lower() in ("1", "true", "yes"):
        _write_out([(g, canonical_name_keep_label(nm), u) for g, nm, u in other],
                   mgou_items, dst, label="[EARLY] 保底写出")

    # ---- [阶段 2] 抓流实测（并发 + 条数/时间双预算）----
    probe_info = {}
    if os.environ.get("DISABLE_PROBE") != "1":
        seen_url, to_probe = set(), []
        for g, nm, url in other:
            if _TAG_RE.search(nm) and url not in seen_url:
                seen_url.add(url)
                to_probe.append((nm, url))
        if to_probe:
            print(f"[INFO] 抓流实测候选 {len(to_probe)} 条（PROBE_MAX_ITEMS 限流）...")
            results = probe_batch(to_probe, workers=PROBE_WORKERS)
            # ★ 逐条按「自己的名称 + 该 URL 的实测」改名，不能按 url 建映射再回填：
            #   多个频道共用同一条线路时（多源聚合极常见），url 键会互相覆盖。
            relabelled, changed = [], 0
            for g, nm, url in other:
                new_nm = relabel_name(nm, results.get(url))
                if new_nm != nm:
                    changed += 1
                relabelled.append((g, new_nm, url))
            other = relabelled
            print(f"[INFO] 清晰度修正 {changed} 条（DISABLE_PROBE=1 可关闭）")
            probe_info = {url: info for _, url in to_probe
                          for info in (results.get(url),) if info}
        else:
            print("[INFO] 无标注清晰度的源，跳过抓流实测")

    # ---- [阶段 3] 清晰度门槛：实测优先，回退名称标签 ----
    def _eff_height(nm: str, info: dict) -> int:
        measured = (info or {}).get("height", 0)
        return measured or _label_height(nm)

    below = kept_fb = 0
    kept = []
    for g, nm, url in other:
        h = _eff_height(nm, probe_info.get(url))
        if not h:
            kept_fb += 1
            kept.append((g, nm, url))
        elif h < MIN_HEIGHT:
            below += 1
        else:
            kept.append((g, nm, url))
    other = kept
    if below:
        print(f"[INFO] 清晰度门槛 <{MIN_HEIGHT}p 舍弃 {below} 条"
              f"（保守保留无标注 {kept_fb} 条）")

    # ---- [阶段 4] 测速择优（并发 + 双预算）----
    speed_results = {}
    if os.environ.get("DISABLE_SPEED") != "1":
        repr_map = OrderedDict()
        for g, nm, url in other:
            repr_map.setdefault((g, nm), url)  # 每频道只测一条代表线路
        try:
            speed_results = lite_speed_test(
                [(f"{g}|{nm}", url) for (g, nm), url in repr_map.items()])
        except Exception as e:
            print(f"[WARN] 测速异常，跳过择优: {e}", file=sys.stderr)

    # ---- [阶段 5] 最终写出（此处归一，保证命名满足 CI 断言）----
    _write_out([(g, canonical_name_keep_label(nm), u) for g, nm, u in other],
               mgou_items, dst, speed_results=speed_results)


def _bootstrap(dst: str, mgou_items: list):
    """无源可用时的兜底：写出「仅茂哥TV」的种子 tv.txt / tv.m3u 并正常退出（ecode 0）。

    保证仓库在任何情况下都有一份可被订阅的产物，工作流不会因首次运行而变红。
    """
    if not mgou_items:
        print("[FATAL] 无可用上游源，且 mgou_tv.txt 为空，无法产出 tv.txt", file=sys.stderr)
        sys.exit(1)
    print(f"[WARN] 无可用上游源且无旧 tv.txt；仅输出茂哥TV 兜底 {len(mgou_items)} 条",
          file=sys.stderr)
    _write_out([], mgou_items, dst, label="[BOOTSTRAP] 仅茂哥TV")
    sys.exit(0)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="多源聚合（不重新分组）+ 剔除无效源，产出 tv.txt / tv.m3u")
    parser.add_argument("--no-final", action="store_true", help="只产出扁平 tv_raw.txt（调试）")
    parser.add_argument("--in", dest="infile", default=None, help="指定输入文件（跳过抓取）")
    parser.add_argument("--out", dest="outfile", default=OUTPUT, help="最终输出路径")
    args = parser.parse_args()

    mgou_items = _load_mgou_items()

    if args.infile:
        if not os.path.exists(args.infile):
            print(f"[WARN] 输入文件不存在: {args.infile}", file=sys.stderr)
            _bootstrap(args.outfile, mgou_items)
        file_mgou, other = split_mgou(parse_m3u_or_txt(_read_text(args.infile)))
        if file_mgou:
            mgou_items = list(OrderedDict.fromkeys(mgou_items + file_mgou))
        sources_items = [other]
        print(f"[AGG] 从 {args.infile} 读取 {len(other)} 条（跳过抓取）")
    else:
        sources = load_sources()
        if not sources:
            keep = os.environ.get("FORCE_KEEP", "true").lower() in ("1", "true", "yes")
            if keep and os.path.exists(args.outfile):
                print("[WARN] 未找到 sources.txt 且无 --in，FORCE_KEEP 保留旧文件", file=sys.stderr)
                sys.exit(0)
            _bootstrap(args.outfile, mgou_items)
        sources_items = aggregate(sources)

    # ---- 组名处理：黑名单 → 保留组剥离 → 冲突加序号 ----
    group_bl = _load_blacklist(GROUP_BLACKLIST_FILE, "组名黑名单")
    sources_items, _ = apply_group_blacklist(sources_items, group_bl)
    sources_items = drop_reserved_group(sources_items)
    sources_items = renumber_groups(sources_items)

    items = [t for src in sources_items for t in src]
    if not items:
        keep = os.environ.get("FORCE_KEEP", "true").lower() in ("1", "true", "yes")
        # ★ 保底顺序：旧 tv.txt > 茂哥TV 种子 > 失败退出。
        if keep and os.path.exists(args.outfile):
            print("[WARN] 聚合结果为空；FORCE_KEEP=true，保留旧 tv.txt", file=sys.stderr)
            sys.exit(0)
        _bootstrap(args.outfile, mgou_items)

    cleaned, seen = [], set()
    for g, nm, url in items:
        pair = normalize_text_line(nm, url)
        if pair is None:
            continue
        nm2, url2 = pair
        key = (g, nm2, url2)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(key)

    # ★ --no-final 产出带组名的扁平调试中间产物
    if args.no_final:
        write_raw(cleaned)
        print(f"[DONE] 调试中间产物 {RAW_OUTPUT}（{len(cleaned)} 条，跳过正式写出）")
        return

    regroup_and_write(cleaned, args.outfile, mgou_items=mgou_items)


if __name__ == "__main__":
    main()
