#!/usr/bin/env python3
"""看牌位附近每一列的白占比, 判断左边多出来的格是什么。

用法: PYTHONPATH=src python3 tools/_diag_cols.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

c = CDP()
c.find_truth()
t = c.truth()
print("真值:", t.get("hands", {}).get("0"), "张数", len(t.get("hands", {}).get("0") or []))
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
img = dev.snap()
y0, y1 = P.hand_band_measured(img)
print("带:", (y0, y1))
xs = P.card_slots(img, y0, y1)
print("牌位:", xs)
for x in xs:
    for x0 in range(max(0, x - 40), min(img.shape[1] - 8, x + 8), 8):
        col = img[y0 + 8:y1 - 8, x0:x0 + 8]
        w = float((col.min(axis=2) > 150).mean())
        mean = col.reshape(-1, 3).mean(axis=0).astype(int)
        mark = "  ←牌位" if x0 == x else ""
        print(f"  x={x0:>4} 白占比 {w:.2f} 均值BGR {tuple(mean)}{mark}")
    print()
