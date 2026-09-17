#!/usr/bin/env python3
"""实测"选中抬起"的真实像素: 选中一张 vs 取消, 看牌的上边缘移动多少、亮带在哪。

用法: PYTHONPATH=src python3 tools/_diag_lift.py
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
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")


def profile(img, tag):
    band = img[740:940]
    white = (band.min(axis=2) > 200).sum(axis=1)          # 每行的"白像素"个数
    rows = [(740 + i, int(v)) for i, v in enumerate(white) if v > 30]
    top = rows[0][0] if rows else None
    print(f"{tag}: lifted_px={P.lifted_px(img)} | 白色行(>30px) {top}..{rows[-1][0] if rows else None}")
    return img


a = dev.snap()
t = c.truth() or {}
print("当前 selected =", t.get("selected"))
profile(a, "当前")
y0, y1 = P.hand_band_measured(a)
xs = P.card_slots(a, y0, y1)
print(f"手牌带 {(y0, y1)} | 牌位 {len(xs)} 个")
if not (t.get("selected") or []):
    print(f"→ 点最左一张 x={xs[0]} 让它进入选中态")
    dev.tap(xs[0] + 6, (y0 + y1) // 2, wait=1.2)
b = dev.snap()
t2 = c.truth() or {}
print("点后 selected =", t2.get("selected"))
profile(b, "选中后" if (t2.get("selected") or []) else "取消后")
d = np.abs(a.astype(int) - b.astype(int)).sum(axis=2) > 60
colsum = d.sum(axis=0)
xs_ch = np.where(colsum > 3)[0]
print(f"帧差: 变化列 {xs_ch.min() if len(xs_ch) else '-'}..{xs_ch.max() if len(xs_ch) else '-'}"
      f" | 总变化 {int(d.sum())}")
rows_ch = np.where(d.sum(axis=1) > 3)[0]
print(f"帧差: 变化行 {rows_ch.min() if len(rows_ch) else '-'}..{rows_ch.max() if len(rows_ch) else '-'}")
