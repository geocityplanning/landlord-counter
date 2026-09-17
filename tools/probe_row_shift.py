#!/usr/bin/env python3
"""验证"出一张牌之后, 牌位会不会变" —— 出牌前后各量一次, 逐位对比。

用户怀疑(2026-09-17): 出了一张牌之后牌位变了 —— 若成立, 则"点回同一张牌"必然打到隔壁 ✗
  验证法: 出牌前量 (牌位x, 真值手牌id) → 用最小路径打出一张 → 出牌后再量 → 逐位对照:
    ① 手牌张数 27→26
    ② **同一个 id 的牌, 它的 x 移了多少**(居中布局 ⇒ 预期整体平移半个牌距≈12px)

用法: PYTHONPATH=src python3 tools/probe_row_shift.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch    # noqa: E402


def snapshot(c, dev):
    t = c.truth() or {}
    img = dev.snap()
    y0, y1 = P.hand_band_measured(img)
    xs = P.card_slots(img, y0, y1)
    ids = t.get("handIds") or []
    zhi = (t.get("hands") or {}).get("0") or []
    return {"xs": xs, "ids": ids, "zhi": zhi, "sel": t.get("selIds") or t.get("selected") or []}


def play_btn(img):
    y_a, y_b = 1078, 1148
    band = img[y_a:y_b]
    g = band[:, :, 1].astype(int)
    ng = ~((g > band[:, :, 2].astype(int) + 12) & (g > band[:, :, 0].astype(int) + 12))
    col = ng.mean(axis=0)
    runs, s = [], None
    for x, v in enumerate(col):
        if v > 0.6 and s is None:
            s = x
        elif v <= 0.6 and s is not None:
            if x - s > 25:
                runs.append((s, x))
            s = None
    if s is not None and len(col) - s > 25:
        runs.append((s, len(col)))
    if len(runs) < 3:
        return None
    lo, hi = max(runs, key=lambda ab: band[:, ab[0]:ab[1]].mean())
    return ((lo + hi) // 2, (y_a + y_b) // 2)


def main() -> int:
    c = CDP()
    c.find_truth()
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()
    for _ in range(30):
        t = c.truth() or {}
        if t.get("phase") == "playing" and t.get("current") == 0 and not (t.get("selected") or []):
            break
        time.sleep(3)

    a = snapshot(c, dev)
    print(f"出牌前: 手牌 {len(a['ids'])} 张 | selected={a['sel']}")
    print(f"  牌位x 前8 = {a['xs'][:8]}")
    print(f"  手牌id 前8 = {a['ids'][:8]}")
    if not a["ids"]:
        print("✗ 没读到牌")
        return 0
    if len(a["xs"]) != len(a["ids"]):
        print(f"⚠ 牌位 {len(a['xs'])} 个 vs 真值 {len(a['ids'])} 张 → 只比前 {min(len(a['xs']), len(a['ids']))} 位 ✓")

    i = len(a["ids"]) - 1                     # 选最右那张(最小牌, 单出必合法 ✓)
    x = a["xs"][i]
    img0 = dev.snap()
    yb0, yb1 = P.hand_band_measured(img0)
    mt.tap(x, (yb0 + yb1) // 2)
    time.sleep(0.9)
    pb = play_btn(dev.snap())
    mt.tap(pb[0], pb[1])
    time.sleep(2.2)

    b = snapshot(c, dev)
    print(f"\n出牌后: 手牌 {len(b['ids'])} 张 | selected={b['sel']}")
    print(f"  牌位x 前8 = {b['xs'][:8]}")
    print(f"  手牌id 前8 = {b['ids'][:8]}")
    if len(b["ids"]) >= len(a["ids"]):
        print("\n✗ 手牌没减少(这次没打出去) → 换个时机重试")
        return 0
    gone = [k for k in a["ids"] if k not in b["ids"]]
    print(f"\n★ 打出去的牌 id = {gone}")
    print("★ 同一张牌 id 的 x 位移(出牌前 → 出牌后):")
    moved = []
    for k in b["ids"][:6] + b["ids"][-3:]:
        pa = a["ids"].index(k) if k in a["ids"] else None
        pb2 = b["ids"].index(k)
        if pa is not None:
            d = b["xs"][pb2] - a["xs"][pa]
            moved.append(d)
            print(f"   id={k:4d} 第{pa}位(x={a['xs'][pa]}) → 第{pb2}位(x={b['xs'][pb2]})  位移 {d:+d}px")
    if moved:
        print(f"\n结论: 位移中位数 = {sorted(moved)[len(moved)//2]:+d}px  "
              f"⇒ {'✓ 牌位确实变了(用户怀疑成立)' if abs(sorted(moved)[len(moved)//2]) > 4 else '✗ 基本没变'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
