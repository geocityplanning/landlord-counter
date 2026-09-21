#!/usr/bin/env python3
"""把设备里的**掼蛋游戏页**拉到前台(适配器要求页面 visible ✓ 否则真值找不到 ✗)

为什么需要(2026-09-21 实测):
  platform/cdp.py 的 find_truth() 有三个条件, 其中一条是
    document.visibilityState === 'visible'
  ⇒ 设备里只有**前台的标签页** visible ⇒ 如果前台停在别处(比如伴随应用页)
    ⇒ find_truth() 返回 False ⇒ 整轮"真值读不到" ✗ (夜里无人值守 = 直接跑废 ✗)

用法: python3 tools/bring_game_front.py [--close-stale]
  --close-stale: 顺手把堆积的旧标签页关掉(只留每类 URL 一个 ✓)
     来历: 设备里曾堆到 205 个页签 ⇒ devtools 被拖死 ⇒ 目标全不应答 ✗
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:9222"


def _truth_ok() -> bool:
    """能不能真的读到真值(find_truth + truth 有 phase ✓)"""
    try:
        import sys

        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src"))
        from landlord_counter.platform.cdp import CDP

        c = CDP()
        if not c.find_truth():
            return False
        t = c.truth()
        return bool(isinstance(t, dict) and t.get("phase"))
    except Exception:  # noqa: BLE001
        return False


def _reopen_game() -> None:
    """关掉所有 8123 页签(HTTP close 对僵死渲染进程也管用 ✓) 再重开一个 ✓"""
    for t in [x for x in _pages() if "8123" in (x.get("url") or "")]:
        try:
            urllib.request.urlopen(f"{BASE}/json/close/{t['id']}", timeout=6).read()
        except Exception:  # noqa: BLE001
            pass
    time.sleep(1.5)
    subprocess.run('adb -s 127.0.0.1:5555 shell am start -a android.intent.action.VIEW'
                   ' -d "http://172.18.0.1:8123/index.html"', shell=True, capture_output=True)
    time.sleep(8)


def _pages() -> list[dict]:
    try:
        return [t for t in json.load(urllib.request.urlopen(f"{BASE}/json", timeout=8))
                if t.get("type") == "page"]
    except Exception:  # noqa: BLE001
        return []


def close_stale(pages: list[dict]) -> int:
    """同(域名+路径)只留一个 —— 保留 target id 最大的(通常最新 ✓)"""
    keep: dict[str, str] = {}
    closed = 0
    for t in sorted(pages, key=lambda x: str(x.get("id", ""))):
        u = urllib.parse.urlparse(t.get("url", ""))
        k = f"{u.scheme}://{u.netloc}{u.path}"
        if k in keep:
            try:
                urllib.request.urlopen(f"{BASE}/json/close/{t['id']}", timeout=5).read()
                closed += 1
            except Exception:  # noqa: BLE001
                pass
        else:
            keep[k] = t["id"]
    return closed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--close-stale", action="store_true")
    ap.add_argument("--ensure-live", action="store_true",
                    help="真值读不到时, 关掉僵死的游戏页签重开一个 ✓ (夜跑自愈 ✓)")
    a = ap.parse_args()

    if a.ensure_live:
        ok = False
        for i in range(3):                       # 页面可能正在加载 ⇒ 连试 3 次再判定 ✓
            ok = _truth_ok()
            if ok:
                break
            if i < 2:
                time.sleep(3)
        print(f"  真值自检: {'✓ 可读' if ok else '✗ 读不到(连试 3 次)'}")
        if not ok:
            print("  ⚠ 真值读不到(渲染进程僵死) ⇒ 关掉重开游戏页…")
        _reopen_game()
        for _ in range(3):
            time.sleep(6)
            if _truth_ok():
                print("  ✓ 救活了, 真值可读")
                break
        else:
            print("  ✗ 重开后仍读不到 —— 夜跑这段会失败, 但不会污染数据 ✓")

    pages = _pages()
    games = sorted([p for p in pages if "8123" in (p.get("url") or "")],
                   key=lambda t: -int(str(t["id"]).split("/")[-1]) if str(t["id"]).isdigit() else 0)
    if not games:
        print("  ✗ 设备里没有 8123 页签(先跑 guandan_prep.py ✓)")
        return 1

    # 用 CDP 把它拉到前台(不开新标签页 ✓ —— am start 会越堆越多 ✗)
    target = games[0]
    try:
        import asyncio

        import websockets

        async def bring():
            async with websockets.connect(target["webSocketDebuggerUrl"],
                                          open_timeout=8) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Page.bringToFront"}))
                while True:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                    if m.get("id") == 1:
                        return True

        asyncio.run(bring())
        print(f"  ✓ 已把游戏页拉到前台: {target['url'][:52]}")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ 拉前台失败({type(e).__name__}) —— 跑到 prep 时也会被带起来 ✓")

    if a.close_stale:
        n = close_stale(_pages())
        left = len(_pages())
        print(f"  ✓ 清掉堆积页签 {n} 个, 剩 {left} 个")
    time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
