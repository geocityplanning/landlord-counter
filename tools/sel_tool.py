#!/usr/bin/env python3
"""清理与测量小工具(只留一套实现) —— 用户 2026-09-17 指令"旧的就删"。

· clear:  调**执行器**的 _clear_selection_via_truth()(与出牌前的回落同一套 ✓),
          不再自带第二套清残留逻辑(旧的 tools/clear_selection.py 会 4↔6 振荡 ✗, 已删)
· tapid:  点第 i 位 → 看游戏选中是不是第 i 张(用真值当裁判)

用法:
  PYTHONPATH=src python3 tools/sel_tool.py clear
  PYTHONPATH=src python3 tools/sel_tool.py tapid
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P               # noqa: E402
from landlord_counter.platform.cdp import CDP                   # noqa: E402
from landlord_counter.platform.device import AdbDevice          # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch         # noqa: E402
from landlord_counter.platform.registry import create           # noqa: E402


def build():
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    ad = create("guandan")
    ad.attach(dev)
    try:
        ad._ex.cdp = c                      # 真值通道 ✓
    except Exception:  # noqa: BLE001
        pass
    return dev, c, ad


def wait_my_turn(c, tries: int = 40) -> bool:
    for _ in range(tries):
        t = c.truth() or {}
        if t.get("phase") == "playing" and t.get("current") == 0:
            return True
        time.sleep(3)
    return False


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "tapid"
    dev, c, ad = build()
    print(f"真值: {(c.truth() or {}).get('phase')} 轮到={(c.truth() or {}).get('current')} "
          f"selected={(c.truth() or {}).get('selected')}")

    if mode == "clear":
        n = ad._ex._clear_selection_via_truth()
        print(f"✓ 清理调用完成({n} 次点击) → selected={(c.truth() or {}).get('selected')}")
        return 0

    # tapid: 逐位验证"点第 i 位 = 选中第 i 张"
    if not wait_my_turn(c):
        print("✗ 等不到我的回合")
        return 0
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()
    if (c.truth() or {}).get("selected"):
        print("· 桌上还有残留 → 先用执行器清(同一套实现 ✓)")
        ad._ex._clear_selection_via_truth()
    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    cards, _i = P.tm_read_hand(f)
    y = (y0 + y1) // 2
    ids = (c.truth() or {}).get("handIds") or []
    print(f"牌位 {len(cards)} 个 | 手牌 {len(ids)} 张 | y={y}")
    hit = 0
    tests = [len(cards) - 1, len(cards) // 2, 3, 0]
    for i in tests:
        if not (0 <= i < len(cards)):
            continue
        if (c.truth() or {}).get("selected"):
            n = ad._ex._clear_selection_via_truth()
            print(f"  (清了一次残留: {n} 次点击)")
        x = cards[i][2]
        mt.tap(x, y)
        time.sleep(0.9)
        sel = (c.truth() or {}).get("selIds") or []
        pos = [ids.index(s) for s in sel if s in ids]
        good = pos == [i]
        hit += 1 if good else 0
        print(f"  点第{i}位(x={x}) → 游戏选中 {pos}  {'✓' if good else '✗'}")
    print(f"★ 命中 {hit}/{len(tests)}")
    ad._ex._clear_selection_via_truth()
    print(f"✓ 收尾清干净 → selected={(c.truth() or {}).get('selected')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
