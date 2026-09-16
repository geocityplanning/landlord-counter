#!/usr/bin/env python3
"""打印实时帧每个牌位的"最佳匹配 + 距离", 看真牌位与杂位之间有没有清晰界线。

用法: PYTHONPATH=src python3 tools/_diag_dist.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {0: "", 1: "♠", 2: "♣", 3: "♥", 4: "♦"}

c = CDP()
c.find_truth()
t = c.truth()
truth = t.get("hands", {}).get("0")
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
img = dev.snap()
y0, y1 = P.hand_band_measured(img)
xs = P.card_slots(img, y0, y1)
bank = P.load_templates_sr()
print(f"真值: {truth} (共 {len(truth)} 张) | 牌位 {len(xs)} 个")
print(" x     亮度   匹配          距离    解释")
for x in xs:
    patch = img[y0 + 8:y1 - 8, x:x + 24]
    if patch.size == 0:
        continue
    a = P.norm_patch(patch)
    best, bd = None, 1e18
    for k, arrs in bank.items():
        for tp in arrs:
            b = P.norm_patch(tp)
            if b.shape != a.shape:
                continue
            d = float(np.mean(np.abs(a - b)))
            if d < bd:
                bd, best = d, k
    s, r = (int(v) for v in best.split("_"))
    print(f"{x:>4}  {float(patch.mean()):6.1f}  {SUIT.get(s, '?')}{NAME.get(r, r):<8}  {bd:.3f}")
