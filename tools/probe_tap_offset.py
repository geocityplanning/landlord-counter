#!/usr/bin/env python3
"""微调: 点击 x 相对牌位左缘的**偏移量**该取多少? —— 用真值当裁判逐位试。

已知(2026-09-17): 点左缘时中间位精准 ✓、两端各差 1 位 ✗(命中判定"自右向左取第一个" ⇒ 边界归邻牌)
⇒ 试 偏移 0/6/12/18, 看哪一档能把"点第 i 位 ⇒ 选中第 i 张"做成全对 ✓

用法: PYTHONPATH=src python3 tools/probe_tap_offset.py
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


def ids_sel(c):
    t = c.truth() or {}
    return (t.get("handIds") or []), (t.get("selIds") or t.get("selected") or [])


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
    ids, sel = ids_sel(c)
    n = len(ids)
    print(f"牌位 {len(xs)} 个 | 手牌 {n} 张 | y={y} | selected={sel}\n")
    tests = [(n - 1, "最右"), (0, "最左"), (n // 2, "中间")]
    score: dict = {}
    for off in (0, 6, 12, 18):
        for i, tag in tests:
            if not (0 <= i < len(xs)):
                continue
            mt.tap(xs[i] + off, y)
            time.sleep(0.95)
            ids2, sel2 = ids_sel(c)
            pos = [ids2.index(s) for s in sel2 if s in ids2]
            hit = (pos == [i])
            score[(off, tag)] = hit
            print(f"  偏移 {off:>2}px {tag}(第{i}位) → 选中位置 {pos}  {'✓' if hit else '✗'}")
            # 清干净: 若选中了就再点同处取消; 否则点一下补取消
            if sel2:
                mt.tap(xs[i] + off, y)
                time.sleep(0.8)
            _i3, s3 = ids_sel(c)
            if s3:                                    # 还有残留 ⇒ 重置(别把表搞脏 ✗)
                print(f"     ⚠ 残留 {s3} → 本实验结束, 请 reset_table 后再试")
                return 0
        print()
    wins = [k[0] for k, v in score.items() if v]
    print(f"✓ 偏移能全对的: {sorted(set(wins))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
