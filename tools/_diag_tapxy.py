#!/usr/bin/env python3
"""实测: 同 x 下, 不同 y 点击(857 vs 875)能不能选中牌; 顺带看按住时长的影响。

用法: PYTHONPATH=src python3 tools/_diag_tapxy.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

c = CDP()
c.find_truth()
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
img = dev.snap()
y0, y1 = P.hand_band_measured(img)
xs = P.card_slots(img, y0, y1)
x = xs[0] + 6
print(f"带 {(y0, y1)} | 牌位 {len(xs)} 个 | 点 x={x}")


def state():
    t = c.truth() or {}
    return t.get("selected") or []


for y in (857, 875, 866):
    # 先确保是"未选中"状态
    if state():
        dev.tap(x, y, wait=1.0)
        time.sleep(0.4)
    before = state()
    dev.tap(x, y, wait=1.0)
    time.sleep(0.3)
    after = state()
    print(f"  y={y}: 点前 {before} → 点后 {after}  {'✓ 选中成功' if after else '✗ 没选中'}")
    if after:
        dev.tap(x, y, wait=1.0)          # 点回来, 保持干净
        time.sleep(0.3)
print("抬起的像素量 lifted_px =", P.lifted_px(dev.snap()))
