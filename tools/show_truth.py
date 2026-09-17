#!/usr/bin/env python3
"""把"游戏真值"是什么、每个字段什么意思, 实时打出来 —— 给用户看, 也给复盘用。

用法: PYTHONPATH=src python3 tools/show_truth.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SEAT = {"0": "我(南)", "1": "ai1(西)", "2": "ai2(北/队友)", "3": "ai3(东)"}


def main() -> int:
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    print("=== 游戏内部真值 window.__truth() 原始内容 ===")
    print(json.dumps(t, ensure_ascii=False, indent=2)[:1200])

    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    xs = P.card_slots(f, y0, y1)
    ids = t.get("handIds") or []
    zhi = (t.get("hands") or {}).get("0") or []
    sel = t.get("selIds") or t.get("selected") or []

    print("\n=== 各字段含义 + 与我看到的画面逐位对照 ===")
    print(f"phase   = {t.get('phase')}          ← 现在处于什么阶段(playing=打牌中)")
    print(f"current = {t.get('current')}          ← 该谁出牌(0=我, 1/2/3=三个AI)")
    print(f"selected= {t.get('selected')}    ← 游戏认定的【已选中】牌(id)")
    print(f"selIds  = {sel}")
    print("\nhands   = 四家手牌的**点数**(14=A, 13=K, 12=Q, 11=J; 15/16=小王/大王)")
    for k, v in (t.get("hands") or {}).items():
        print(f"   {SEAT.get(k, k):12s} {len(v):2d} 张  {[NAME.get(z, z) for z in v][:14]}")
    print("\nhandIds = 我手牌的 **id 列表**(与 selected 同一编号空间 ⇒ 才判得出【点的是哪张】 ✓)")
    print(f"   我的 id(显示顺序) = {ids}")
    print("\n=== 对照表(我量到的牌位 ↔ 游戏真值) ===")
    print(f"{'位':>3} {'我量的x':>7} {'我的读数':>8} {'游戏真值':>8} {'一致':>4} {'id':>5}")
    my = P.tm_read_hand(f)[0]
    for i, (s_, r_, x) in enumerate(my):
        tr = zhi[i] if i < len(zhi) else None
        ok = "✓" if tr == r_ else "✗"
        ii = ids[i] if i < len(ids) else "-"
        star = "  ← 被选中" if ii in sel else ""
        print(f"{i:>3} {x:>7} {NAME.get(r_, r_):>8} {NAME.get(tr, tr):>8} {ok:>4} {str(ii):>5}{star}")
    print(f"\n牌位 {len(xs)} 个 | 真值手牌 {len(zhi)} 张 | 选中 {len(sel)} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
