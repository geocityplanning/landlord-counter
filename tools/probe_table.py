#!/usr/bin/env python3
"""诊断桌面识别: 游戏真值的上一手 vs 我们感知到的桌面牌块/读数 ✓

用法: python3 tools/probe_table.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP             # noqa: E402
from landlord_counter.platform.device import AdbDevice    # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def nm(v) -> str:
    return NAME.get(int(v), str(int(v)))


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    plays = t.get("plays") or []
    last = None
    for p in reversed(plays):
        if int(p.get("seat", 0)) != 0 and int(p.get("n") or 0) > 0:
            last = p
            break
    print("== 游戏真值的上一手(别人) ==")
    if last:
        print(f"  席{last.get('seat')} 出 {' '.join(nm(v) for v in last.get('zhi') or [])}")
    else:
        print("  (无 —— 可能是我领出)")

    img = dev.snap()
    print("\n== CV 找到的桌面牌块 table_plays() ==")
    blocks = list(P.table_plays(img))
    if not blocks:
        print("  ✗ **一个牌块都没找到**(⇒ read_table_last 必然返回 [], 这就是'桌面识别为空'的根因)")
    for name, box, cnt in blocks:
        print(f"  {name}: 框={box} 白像素={cnt}")

    print("\n== read_table_last() 的结论(rec=None ⇒ 只验 CV 那半段) ==")
    try:
        cards = P.read_table_last(None, img)
        print(f"  {[nm(getattr(x, 'zhi', x)) for x in cards] if cards else '(空)'}")
    except Exception as e:  # noqa: BLE001
        print(f"  抛异常: {type(e).__name__}: {e}")

    # 桌面区在画面上的哪一段? —— 打印每 40 行的白像素占比, 看牌块该在哪
    import numpy as np
    print("\n== 逐行白占比(找桌面牌块的真实纵段) ==")
    for y in range(100, 900, 40):
        seg = img[y:y + 40]
        b, g, r = seg[:, :, 0].astype(int), seg[:, :, 1].astype(int), seg[:, :, 2].astype(int)
        wht = ((b > 150) & (g > 150) & (r > 150)).mean()
        print(f"  y={y:>3}..{y + 40:>3}: 白占比 {wht:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
