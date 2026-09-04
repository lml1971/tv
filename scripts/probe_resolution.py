#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_resolution.py —— 抓流实测真实分辨率 / 码率（持久化缓存 + 预算控制）。

★ 针对 live-aggregator 45 分钟超时的修复：

  1. 缓存区分「未探测」与「探测失败」。
     旧版对失败源写入 None，而 probe_batch 用 `cache.get(u) is None` 判定待测，
     于是失败源每次运行都要重新走完一整轮 ffprobe 超时——而失败源恰恰最慢、
     占比最高。现改为写入哨兵 {"ok": False}，命中即跳过。

  2. 双预算：PROBE_MAX_ITEMS（条数）+ PROBE_BUDGET_SEC（时间）。
     任一触顶立即停止，剩余留待下次运行，保证 job 时长可控。

  3. 增量落盘：每 PROBE_SAVE_EVERY 条保存一次，job 被取消也能保留已完成部分。

  4. 单条超时 20s → 8s，并发 4 → 8，并按 deadline 主动 kill 掉 ffprobe 子进程。
"""
import os
import re
import json
import time
import random
import subprocess
import concurrent.futures as futures

PROBE_TIMEOUT = float(os.environ.get("PROBE_TIMEOUT", "8"))
PROBE_WORKERS = int(os.environ.get("PROBE_WORKERS", "8"))
PROBE_MAX_ITEMS = int(os.environ.get("PROBE_MAX_ITEMS", "300"))
PROBE_BUDGET_SEC = float(os.environ.get("PROBE_BUDGET_SEC", "900"))
PROBE_SAVE_EVERY = int(os.environ.get("PROBE_SAVE_EVERY", "24"))
PROBE_CACHE_TTL = float(os.environ.get("PROBE_CACHE_TTL", str(10 * 24 * 3600)))

USER_AGENT = "Mozilla/5.0 (compatible; IPTV-Probe/1.0)"
CACHE_FILE = os.environ.get("PROBE_CACHE", "probe_cache.json")

_CLARITY_RE = re.compile(
    r"[\(（]\d{2,4}[ip]?[\)）]|[\(（]?HD[\)）]?|[\(（]?UHD[\)）]?|\bHD\b|\bUHD\b", re.I)
_TAG_RE = re.compile(r"\((\d{2,4})[ip]\)", re.I)


def to_label(height: int) -> str:
    if height >= 2160:
        return "4K"
    if height >= 1080:
        return "1080p"
    if height >= 720:
        return "720p"
    if height >= 480:
        return "480p"
    return "360p"


def strip_clarity(name: str) -> str:
    return _CLARITY_RE.sub("", name).strip().strip("-_()（）")


def probe_one(url: str, deadline: float = None) -> dict:
    """单条抓流探测；deadline 为绝对时间预算，耗尽时不再发起新探测。"""
    if not url or not url.startswith(("http://", "https://")):
        return None
    budget = PROBE_TIMEOUT if deadline is None else min(PROBE_TIMEOUT, deadline - time.time())
    if budget <= 0.5:
        return None

    cmd = [
        "ffprobe", "-v", "error",
        "-analyzeduration", "3000000",
        "-probesize", "3000000",
        "-rw_timeout", str(int(budget * 1_000_000)),
        "-user_agent", USER_AGENT,
        # ★ 必须显式请求 codec_type：旧版只请求 width/height/codec_name，
        #   而筛选逻辑用 s.get("codec_type") == "video"，该字段恒为 None，
        #   导致 probe_one 永远返回 None —— 抓流实测功能整体瘫痪。
        "-show_entries", "stream=codec_type,width,height,codec_name",
        "-of", "json",
        url,
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        try:
            out, _ = proc.communicate(timeout=budget + 3)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=3)
            except Exception:
                pass
            return None
        if proc.returncode != 0 or not (out or "").strip():
            return None
        data = json.loads(out)
    except (json.JSONDecodeError, OSError, ValueError):
        return None

    streams = data.get("streams", []) or []
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if vstream is None:
        # 兜底：部分流不返回 codec_type，取第一个有宽高的流
        vstream = next((s for s in streams
                        if s.get("width") and s.get("height")), None)
    if not vstream:
        return None
    w = vstream.get("width") or 0
    h = vstream.get("height") or 0
    if not w or not h:
        return None
    return {"width": int(w), "height": int(h), "label": to_label(int(h))}


class ProbeCache:
    """分辨率缓存。

    向下兼容旧格式（只有 width/height/label、无 ok/ts 的条目视为有效）。
    """

    def __init__(self, path: str = CACHE_FILE):
        self.path = path
        self._mem = {}
        self._dirty = 0
        if path and os.path.exists(path):
            try:
                self._mem = json.loads(open(path, encoding="utf-8").read())
            except (json.JSONDecodeError, OSError):
                self._mem = {}
        if not isinstance(self._mem, dict):
            self._mem = {}

    def has(self, url: str) -> bool:
        """是否已有（成功或已判定失败的）缓存，有则不必再测。"""
        e = self._mem.get(url)
        if not isinstance(e, dict):
            return False
        if PROBE_CACHE_TTL > 0 and "ts" in e:
            if time.time() - float(e.get("ts") or 0) > PROBE_CACHE_TTL:
                return False
        return True

    def get(self, url: str):
        """成功结果返回 info dict；失败或未探测一律返回 None（下游无需改动）。"""
        e = self._mem.get(url)
        if not isinstance(e, dict):
            return None
        if e.get("ok") is False:
            return None
        if not e.get("height"):
            return None
        return {k: v for k, v in e.items() if k not in ("ok", "ts")}

    def put(self, url: str, info):
        if info:
            self._mem[url] = dict(info, ok=True, ts=time.time())
        else:
            # ★ 关键修复：失败也要留痕，否则每次运行都会重测这些最慢的源
            self._mem[url] = {"ok": False, "ts": time.time()}
        self._dirty += 1

    def save(self, force: bool = False):
        if not self.path:
            return
        if not force and self._dirty < PROBE_SAVE_EVERY:
            return
        self._dirty = 0
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._mem, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass


def probe_batch(items, workers: int = None, cache: ProbeCache = None,
                budget: float = None, max_items: int = None) -> dict:
    """探测带标注的源；已缓存（含已判定失败）的直接跳过。

    返回 {url: info|None}，失败的 url 对应 None，下游 relabel_name 会原样保留名称。
    """
    workers = workers or PROBE_WORKERS
    budget = PROBE_BUDGET_SEC if budget is None else budget
    max_items = PROBE_MAX_ITEMS if max_items is None else max_items
    if cache is None:
        cache = ProbeCache()

    all_urls, seen = [], set()
    for _, u in items:
        if not u or u in seen:
            continue
        seen.add(u)
        all_urls.append(u)

    pending = [u for u in all_urls if not cache.has(u)]
    if max_items >= 0 and len(pending) > max_items:
        random.shuffle(pending)  # 随机采样，多轮累积逐步覆盖全量
        print(f"[PROBE] 待探测 {len(pending)} 条 > 上限 {max_items}，"
              f"本轮随机采样 {max_items} 条（其余 {len(pending) - max_items} 条留待后续运行）")
        pending = pending[:max_items]

    if not pending:
        print(f"[PROBE] 全部 {len(all_urls)} 条命中缓存，跳过抓流")
        return {u: cache.get(u) for u in all_urls}

    print(f"[PROBE] 本轮探测 {len(pending)} 条：并发 {workers}，"
          f"单条上限 {PROBE_TIMEOUT}s，总预算 {budget:.0f}s")
    t0 = time.time()
    deadline = t0 + budget
    done = ok = 0
    ex = futures.ThreadPoolExecutor(max_workers=workers)
    try:
        fut_map = {ex.submit(probe_one, u, deadline): u for u in pending}
        for fut in futures.as_completed(fut_map):
            u = fut_map[fut]
            done += 1
            try:
                info = fut.result()
            except Exception:
                info = None
            if info is not None:
                cache.put(u, info)
                ok += 1
                print(f"[PROBE] ({done}/{len(pending)}) {info['width']}x{info['height']}"
                      f"({info['label']}) {u[:60]}")
            else:
                if time.time() >= deadline:
                    # 预算耗尽：不写失败标记，留给下次真正测一遍
                    print(f"[PROBE] 时间预算耗尽，剩余 {len(pending) - done} 条留待下次")
                    break
                cache.put(u, None)
                print(f"[PROBE] ({done}/{len(pending)}) FAIL {u[:60]}")
            if done % max(1, workers) == 0:
                cache.save()
    finally:
        cache.save(force=True)
        ex.shutdown(wait=False, cancel_futures=True)

    print(f"[PROBE] 完成 {done}/{len(pending)} 条，成功 {ok}，"
          f"耗时 {time.time() - t0:.0f}s（缓存累计 {len(cache._mem)} 条）")
    return {u: cache.get(u) for u in all_urls}


def _level(n: int) -> int:
    return {360: 0, 480: 1, 576: 1, 720: 2, 1080: 3, 2160: 4}.get(n, -1)


def relabel_name(name: str, info: dict) -> str:
    if not info or not info.get("height"):
        return name
    label = info["label"]
    clean = strip_clarity(name)
    m = _TAG_RE.search(name)
    old_num = int(m.group(1)) if m else None
    # ★ 档位比较必须用「帧高」而非 max(width, height)：
    #   旧版取 max() 会拿到 1920/1280 这类宽度，_level() 查表得 -1，
    #   与任何标注值的档位差都 >= 2，于是所有带标注的源被无差别重写。
    #   统一用帧高，与 MIN_HEIGHT 的「帧高」口径保持一致。
    new_num = info["height"]

    if old_num and abs(_level(old_num) - _level(new_num)) >= 2:
        return f"{clean}({label})"
    if not old_num and label in ("4K", "1080p", "720p"):
        return f"{clean}({label})"
    return name


if __name__ == "__main__":
    import sys
    urls = sys.argv[1:] or ["https://example.com"]
    items = [(u, u) for u in urls]
    cache = ProbeCache()
    results = probe_batch(items, workers=PROBE_WORKERS, cache=cache)
    for u, info in results.items():
        print(f"{u}: {info}")
