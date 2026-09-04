#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_lite.py —— 轻量源有效性探测：聚合时剔除无效节目（宁留勿杀）。

判定规则：
    · GET 拿到任意 HTTP 状态码 → 服务器在线：
        - 404 / 410（资源确实不存在）         → 判无效，剔除
        - 其余状态（403 / 405 / 451 等防盗链）→ 判有效，保守保留
    · 连接被拒 / DNS 失败 / 超时 / 地址非法    → 判无效，剔除
    · 非 http(s) 地址（rtp / rtsp / udp）无法探测 → 保守保留

后期可变量（环境变量可覆盖；工作流 yml 各 step 的 env 中已注明）：
    DISABLE_VALIDATE     设为 1 关闭剔除（默认开启）
    VALIDATE_TIMEOUT     单条超时秒数            默认 3
    VALIDATE_WORKERS     并发线程数              默认 32
    VALIDATE_MAX_ITEMS   单轮最多探测条数        默认 3000
    VALIDATE_BUDGET_SEC  单轮总耗时上限（秒）    默认 300
    VALIDATE_CACHE       缓存文件路径            默认 validate_cache.json
    VALIDATE_CACHE_TTL   有效结果缓存期（秒）    默认 3 天
    VALIDATE_FAIL_TTL    失败结果缓存期（秒）    默认 10 分钟（防抖动误杀）

缓存带时间戳增量落盘，job 被取消也保留已完成部分。
"""
import os
import json
import time
import random
import socket
import urllib.request
import urllib.error
import concurrent.futures as futures

TIMEOUT = float(os.environ.get("VALIDATE_TIMEOUT", "3"))
WORKERS = int(os.environ.get("VALIDATE_WORKERS", "32"))
MAX_ITEMS = int(os.environ.get("VALIDATE_MAX_ITEMS", "3000"))
BUDGET_SEC = float(os.environ.get("VALIDATE_BUDGET_SEC", "300"))
CACHE_FILE = os.environ.get("VALIDATE_CACHE", "validate_cache.json")
TTL_SEC = float(os.environ.get("VALIDATE_CACHE_TTL", str(3 * 24 * 3600)))
FAIL_TTL_SEC = float(os.environ.get("VALIDATE_FAIL_TTL", "600"))
SAVE_EVERY = int(os.environ.get("VALIDATE_SAVE_EVERY", "200"))

_USER_AGENT = "Mozilla/5.0 (compatible; IPTV-Aggregator/2.0)"
_DEAD_STATUS = {404, 410}   # 资源不存在 → 判死；其余状态码一律保守放行


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
    if not isinstance(entry, dict) or "alive" not in entry:
        return False
    ts = float(entry.get("ts") or 0)
    if ts == 0:
        return True
    age = time.time() - ts
    if entry.get("alive"):
        return age <= TTL_SEC
    return age <= FAIL_TTL_SEC   # 失败结果短缓存，避免网络抖动误杀


def _probe(url: str) -> dict:
    """GET 探测（比 HEAD 更抗防盗链），只取响应头 + 1KB 即断开。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Connection": "close",
    })
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            resp.read(1024)
    except urllib.error.HTTPError as e:
        status = e.code
    except (urllib.error.URLError, socket.timeout, TimeoutError,
            OSError, ValueError):
        return {"alive": False, "status": None,
                "rt": round(time.time() - t0, 3), "ts": time.time()}
    return {"alive": status not in _DEAD_STATUS, "status": status,
            "rt": round(time.time() - t0, 3), "ts": time.time()}


def validate_urls(items, use_cache=True, workers=None, budget=None, max_items=None):
    """探测一批地址的有效性，返回 {url: {"alive": bool, "status": ...}}（仅含已覆盖项）。

    items: [(name, url), ...]，内部按 url 去重，同一条线路只测一次。
    """
    workers = workers or WORKERS
    budget = BUDGET_SEC if budget is None else budget
    max_items = MAX_ITEMS if max_items is None else max_items

    pairs = list(items) if isinstance(items, list) else list(items.items())
    uniq_urls = list(dict((u, n) for n, u in pairs if u).keys())

    results, pending = {}, []
    for u in uniq_urls:
        entry = _CACHE.get(u) if use_cache else None
        if entry is not None and _cache_valid(entry):
            results[u] = entry
        else:
            pending.append(u)

    if max_items >= 0 and len(pending) > max_items:
        random.shuffle(pending)
        print(f"[VALIDATE] 待探测 {len(pending)} 条 > 上限 {max_items}，"
              f"本轮随机采样 {max_items} 条（未覆盖项保守保留）")
        pending = pending[:max_items]

    t0 = time.time()
    done = 0
    if pending:
        print(f"[VALIDATE] 本轮探测 {len(pending)} 条：并发 {workers}，"
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
                    data = {"alive": False, "status": None}
                if "ts" not in data:
                    data["ts"] = time.time()
                _CACHE[u] = data
                results[u] = data
                if done % SAVE_EVERY == 0 and use_cache:
                    _save_disk(_CACHE)
                if time.time() > deadline:
                    print(f"[VALIDATE] 时间预算耗尽，剩余 {len(pending) - done} 条留待下次")
                    for f in fut_map:
                        f.cancel()
                    break

    if use_cache:
        _save_disk(_CACHE)

    dead = sum(1 for v in results.values() if not v.get("alive"))
    print(f"[VALIDATE-LITE] 覆盖 {len(results)} 条（本轮实测 {done}），"
          f"判死 {dead} 条，耗时 {time.time() - t0:.0f}s")
    return results


if __name__ == "__main__":
    import sys
    urls = sys.argv[1:] or ["https://example.com"]
    items = [(f"ch{i}", u) for i, u in enumerate(urls)]
    for u, r in validate_urls(items).items():
        print(f"alive={r.get('alive')} status={r.get('status')} {u}")
