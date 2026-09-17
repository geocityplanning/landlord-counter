#!/usr/bin/env python3
"""实测: 点一张牌之后, 画面在**哪里**变了 —— 是"牌抬起来"(上部出现变化)还是"高亮"(牌面变亮)?

用途: 直选验证器现在靠"抬起量"(lift)判定, 实测一直判定失败 ✗
      → 若实际是"高亮", 验证器要改成看牌面亮度变化 ✓

用法: PYTHONPATH=src python3 tools/_diag_tap.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
a = dev.snap()
y0, y1 = P.hand_band_measured(a)
xs = P.card_slots(a, y0, y1)
print(f"带 {(y0, y1)} | 牌位 {xs[:6]}...")
x = xs[0]
print(f"点最左一张 x={x} (牌位带内) ...")
dev.tap(x + 6, (y0 + y1) // 2, wait=1.0)
b = dev.snap()
d = np.abs(a.astype(int) - b.astype(int)).sum(axis=2)
print(f"变化像素总数: {int((d > 30).sum())}")
ys, xs_ch = np.where(d > 30)
if len(ys):
    print(f"变化区域: y {ys.min()}..{ys.max()} | x {xs_ch.min()}..{xs_ch.max()}")
    print(f"  手牌带内变化像素: {int(((ys >= y0) & (ys <= y1)).sum())}  带上方变化: {int((ys < y0).sum())}")
    # 该牌位附近的亮度变化(高亮会让牌面变亮)
    for tag, img in (("点前", a), ("点后", b)):
        patch = img[y0 + 8:y1 - 8, x:x + 24]
        print(f"  {tag}: 该牌位平均亮度 {float(patch.mean()):.1f}")
else:
    print("画面**完全没有变化** → 点的位置没有命中任何牌 ✗")
