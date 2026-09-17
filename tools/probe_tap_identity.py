#!/usr/bin/env python3
"""点对没对? —— 用游戏真值当裁判, **逐位验证**: 点第 i 个牌位, 看游戏选中的是第几张牌。

真值: hands['0'] = 我的手牌(游戏内部数组) ; selected = 被选中的牌 id
  ⇒ 选中 id 在数组里的位置 = 它的身份 ⇒ 与"我点的是第几个牌位"逐位对照 ✓

用法: PYTHONPATH=src python3 tools/probe_tap_identity.py [要试的位号, 默认 26 13 0]
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


def state(c, dev):
    """返回 (手牌id列表(显示顺序), 手牌点数, 选中id列表) —— id 才能与 selected 比 ✓"""
    t = c.truth() or {}
    ids = t.get("handIds") or []
    zhi = (t.get("hands") or {}).get("0") or []
    sel = t.get("selIds") or t.get("selected") or []
    return ids, zhi, sel


def main() -> int:
    c = CDP()
    c.find_truth()
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()

    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    xs = P.card_slots(f, y0, y1)
    y = int((y0 + y1) // 2)
    ids, zhi, sel = state(c, dev)
    n = len(ids)
    print(f"手牌带 {y0}..{y1} | 牌位 {len(xs)} 个 | 手牌 {n} 张 | selected={sel}")
    print(f"手牌id(显示顺序) = {ids}")
    print(f"点击 y = {y}\n")
    # 显示顺序 = 从大到小 ⇒ 显示第 i 张 = 数组第 (n-1-i) 张
    want = [int(a) for a in sys.argv[1:]] or [n - 1, n // 2, 0]
    for i in want:
        if not (0 <= i < len(xs)) or sel:
            print(f"  跳过 i={i} (越界或当前已有选中 {sel} ⇒ 先重置)")
            continue
        x = xs[i]
        mt.tap(x, y)
        time.sleep(1.0)
        _ids, _z, sel2 = state(c, dev)
        pos = [ids.index(s) for s in sel2 if s in ids]
        ok = (pos == [i])
        print(f"  点第 {i} 位(x={x}) → selected={sel2} → 显示位置 {pos}  "
              f"{'✓✓ 点对了!' if ok else '✗ 不是这一张'}")
        # 点回去 / 清干净
        mt.tap(x, y)
        time.sleep(0.9)
        _ids, _z, sel3 = state(c, dev)
        print(f"     (再点一次 → selected={sel3})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
