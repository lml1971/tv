#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""speed_test_lite.py —— 轻量级测速（HTTP HEAD + 持久化缓存 + 真并发 + 预算）。

★ 针对 live-aggregator 45 分钟超时的修复：

  1. 旧版 speed_test() 是纯串行 for 循环，workers 参数被完全忽略。
     实测：200 条 × 每条 0.05s、workers=32 → 实际 10.2s（= 串行耗时）。
     按 3000 个频道 × 最坏 3s 超时估算 = 150 分钟，是超时的直接原因。
     现改为 ThreadPoolExecutor 真并发。

  2. 双预算：SPEED_MAX_ITEMS（条数）+ SPEED_BUDGET_SEC（时间）。

  3. 增量落盘缓存，job 被取消也保留已完成部分。
"""
import os
import json
import time
import random
import socket
import urllib.request
import urllib.error
import concurrent.futures as futures

TIMEOUT = float(os.environ.get("SPEED_TIMEOUT", "2"))
CACHE_FILE = os.environ.get("SPEED_CACHE", "speed_cache.json")
WORKERS = int(os.environ.get("SPEED_WORKERS", "32"))
MAX_ITEMS = int(os.environ.get("SPEED_MAX_ITEMS", "2000"))
BUDGET_SEC = float(os.environ.get("SPEED_BUDGET_SEC", "240"))
SAVE_EVERY = int(os.environ.get("SPEED_SAVE_EVERY", "200"))
TTL_SEC = float(os.environ.get("SPEED_CACHE_TTL", str(3 * 24 * 3600)))

_OK = {200, 206, 301, 302, 303, 307, 308}
_USER_AGENT = "Mozilla/5.0 (compatible; IPTV-Aggregator/2.0)"


def _load_disk():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_disk(cache):
    tmp = CACHE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        pass


_CACHE = _load_disk()


def _cache_valid(entry) -> bool:
    """旧版缓存无 ts 字段，视为有效以平滑迁移。"""
    if not isinstance(entry, dict) or "ok" not in entry:
        return False
    ts = float(entry.get("ts") or 0)
    if ts == 0 or TTL_SEC <= 0:
        return True
    return (time.time() - ts) <= TTL_SEC


def _probe(url: str) -> dict:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": _USER_AGENT})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
        return {"response_time": None, "ok": False, "status": None, "ts": time.time()}
    rt = round(time.time() - t0, 3)
    return {"response_time": rt, "ok": status in _OK, "status": status, "ts": time.time()}


def speed_test(items, workers=None, timeout=None, use_cache=True,
               budget=None, max_items=None):
    """对「每个频道的代表线路」做一次 HEAD 探测，返回 {url: {...}}。

    items: [(name, url), ...] 或 dict，内部按 url 去重。
    """
    global TIMEOUT
    workers = workers or WORKERS
    TIMEOUT = timeout or TIMEOUT
    budget = BUDGET_SEC if budget is None else budget
    max_items = MAX_ITEMS if max_items is None else max_items

    pairs = list(items) if isinstance(items, list) else list(items.items())
    # 按 url 去重：同一条线路只测一次
    uniq_urls = list(dict((u, n) for n, u in pairs if u).keys())

    results = {}
    pending = []
    for u in uniq_urls:
        entry = _CACHE.get(u) if use_cache else None
        if entry is not None and _cache_valid(entry):
            results[u] = entry
        else:
            pending.append(u)

    if max_items >= 0 and len(pending) > max_items:
        random.shuffle(pending)
        print(f"[SPEED] 待探测 {len(pending)} 条 > 上限 {max_items}，"
              f"本轮随机采样 {max_items} 条")
        pending = pending[:max_items]

    t0 = time.time()
    done = 0
    if pending:
        print(f"[SPEED] 本轮探测 {len(pending)} 条：并发 {workers}，"
              f"单条上限 {TIMEOUT}s，总预算 {budget:.0f}s")
        deadline = t0 + budget
        with futures.ThreadPoolExecutor(max_workers=workers) as ex:
            fut_map = {ex.submit(_probe, u): u for u in pending}
            for fut in futures.as_completed(fut_map):
                u = fut_map[fut]
                done += 1
                try:
                    data = fut.result()
                except Exception:
                    data = {"response_time": None, "ok": False, "status": None}
                if "ts" not in data:
                    data["ts"] = time.time()
                _CACHE[u] = data
                results[u] = data
                if done % SAVE_EVERY == 0 and use_cache:
                    _save_disk(_CACHE)
                if time.time() > deadline:
                    print(f"[SPEED] 时间预算耗尽，剩余 {len(pending) - done} 条留待下次")
                    for f in fut_map:
                        f.cancel()
                    break

    if use_cache:
        _save_disk(_CACHE)

    ok_count = sum(1 for v in results.values() if v.get("ok"))
    print(f"[SPEED-LITE] 覆盖 {len(results)} 条（本轮实测 {done}），"
          f"可达 {ok_count} 条，耗时 {time.time() - t0:.0f}s")
    return results


def speed_sort_key(url, results):
    info = results.get(url) or {}
    rt = info.get("response_time")
    if rt is None or not info.get("ok"):
        return (1, 9_999_999)
    return (0, rt)


if __name__ == "__main__":
    import sys
    urls = sys.argv[1:] or ["https://example.com"]
    items = [(f"ch{i}", u) for i, u in enumerate(urls)]
    for u, r in speed_test(items).items():
        print(f"{r.get('response_time')}s ok={r.get('ok')} {u}")
