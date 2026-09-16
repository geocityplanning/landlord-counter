#!/usr/bin/env python3
"""诊断实时帧读牌: 手牌带 / 牌位 / 每列白占比 / 前几张的匹配距离。

用法: PYTHONPATH=src python3 tools/_diag_live.py
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
print("真值钩子:", bool(c.find_truth()))
t = c.truth()
print("真值手牌:", t.get("hands", {}).get("0") if t else None, "| 阶段", t.get("phase") if t else None)
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
img = dev.snap()
print("帧尺寸:", img.shape)
y0, y1 = P.hand_band_measured(img)
print("手牌带:", (y0, y1))
sub = img[y0 + 6:y1 - 6]
white = (sub.min(axis=2) > 150).mean(axis=0)
cols = np.where(white > 0.40)[0]
print("白占比>0.40 的列范围:", (int(cols[0]), int(cols[-1])) if len(cols) else "无")
print("白占比 >0.4 的行数:", len(cols), "| 全宽带最大白占比:", round(float(white.max()), 3))
peaks = P.card_edges(img, y0, y1)
print("卡边界峰:", peaks[:20], "共", len(peaks))
xs = P.card_slots(img, y0, y1)
print("牌位:", xs)
bank = P.load_templates_sr()
print("模板库:", len(bank), "类")
for x in xs[:14]:
    patch = img[y0 + 8:y1 - 8, max(0, x):x + 24]
    if patch.size == 0:
        print(f"  x={x} 空")
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
    print(f"  x={x:>4} std={float(patch.std()):6.1f} → {best} d={bd:.3f}")
