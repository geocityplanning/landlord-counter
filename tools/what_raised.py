#!/usr/bin/env python3
"""读出"现在抬起了哪些牌"(用滑动匹配的抬起量; 并与游戏真值 selected 对照)。

用法: PYTHONPATH=src python3 tools/what_raised.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦", 0: ""}


def main() -> int:
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    f = dev.snap()
    cards, info = P.tm_read_hand(f)
    print(f"放平基线 = {info['base']:.0f}px | 读出 {len(cards)} 张")
    print("\n整手牌(左→右, ↑ = 我判抬起):")
    line = []
    for s, r, x, l in cards:
        line.append(f"{SUIT.get(s, '')}{NAME.get(r, r)}{'↑' if l >= 18 else ''}")
    print("  " + " ".join(line))
    raised = [(s, r, x, l) for s, r, x, l in cards if l >= 18]
    print(f"\n★ 抬起的牌共 {len(raised)} 张:")
    for s, r, x, l in raised:
        print(f"   {SUIT.get(s, '')}{NAME.get(r, r)}  (x={x}, 抬起 {l:.0f}px)")
    sel = t.get("selected") or []
    print(f"\n游戏真值 selected = {len(sel)} 张 ({sel})")
    print(f"手牌张数 真值 {len((t.get('hands') or {}).get('0') or [])} / 我读 {len(cards)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
