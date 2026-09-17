#!/usr/bin/env python3
"""判定最左那张"王"到底是大王还是小王(用颜色/图案; 大王彩色, 小王黑白)。

对照游戏源码常量: XIAO_WANG=15, DA_WANG=16 (lab/guandan_www/js/gameRules.js:16)
若真值给 15 而像素显示彩色 → 说明"15=小王"的映射与该游戏实际显示不符 ✗

用法: PYTHONPATH=src python3 tools/_diag_joker.py
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
h = t.get("hands", {}).get("0") or []
print("真值手牌:", h, "→ 最左(应该是最大那张) =", h[0] if h else None,
      "= 小王" if h and h[0] == 15 else ("= 大王" if h and h[0] == 16 else ""))
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
img = dev.snap()
y0, y1 = P.hand_band_measured(img)
xs = P.card_slots(img, y0, y1)
print("牌位:", xs[:3], "...")
# 最左那张完整看得到(没被别的牌压住) → 取它整张宽度(约 62px)
for tag, x, w in (("最左整张", xs[0], 62), ("最左露出的24px", xs[0], 24)):
    patch = img[y0 + 8:y1 - 8, x:x + w].reshape(-1, 3).astype(int)
    r, g, b = patch[:, 0], patch[:, 1], patch[:, 2]
    red = ((r - g > 40) & (r - b > 40)).mean()
    dark = (patch.max(axis=1) < 90).mean()
    print(f"{tag}: 红色像素占比 {red:.3f} | 近黑占比 {dark:.3f} | 均值 {tuple(patch.mean(axis=0).astype(int))}")
print("判据: 大王(彩色, 红占比高) vs 小王(黑白, 红占比≈0)")
