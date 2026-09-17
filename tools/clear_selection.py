#!/usr/bin/env python3
"""清掉手牌上的残留选中(用游戏真值 selected 当裁判, 清到空为止)。

为什么需要: 反复测试的点击会把手牌留在"多张选中"状态 ✗ → 之后每次出牌都错 ✗
教训(2026-09-17): 残留会让 清残留 逻辑自己振荡(10202↔9191) ✗ —— 点同一张 = 来回切换
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402


def main() -> int:
    c = CDP()
    if not c.find_truth():
        print("没有真值钩子")
        return 2
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    for i in range(12):
        t = c.truth() or {}
        sel = t.get("selected") or []
        if not sel:
            print(f"✓ 已清空(第 {i} 轮)")
            break
        f = dev.snap()
        y0, _ = P.hand_band_measured(f)
        xs = P.lifted_xs(f)
        print(f"  第{i}轮: selected={len(sel)} 张 | lifted_xs={xs} | lifted_px={P.lifted_px(f)}")
        if not xs:
            # 抬起位置分不出来 → 退化为"从左往右逐张点一遍"(点奇数张后再点一遍回退)
            xs = P.card_slots(f)[:4]
        for x in xs:
            dev.tap(int(x), (y0 or 815) + 68, wait=0.5)
            time.sleep(0.2)
        time.sleep(0.4)
    t = c.truth() or {}
    print(f"最终 selected = {t.get('selected')} | 真值手牌张数 {len((t.get('hands') or {}).get('0') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
