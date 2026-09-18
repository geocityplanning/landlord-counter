#!/usr/bin/env python3
"""发给用户看: 整屏 + 手牌放大(标注游戏真值的选中状态), 用于人工确认"抬起"表现。

用法: PYTHONPATH=src python3 tools/show_select_now.py
输出: data/shots/full_now.png, hand_zoom_now.png
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

OUT = "data/shots"
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {0: "♠", 1: "♥", 2: "♣", 3: "♦", 4: ""}

c = CDP()
c.find_truth()
dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")

img = dev.snap()
t = c.truth() or {}
sel = t.get("selected") or []
print("游戏真值 selected =", sel, "| 手牌 =", t.get("hands", {}).get("0"))
os.makedirs(OUT, exist_ok=True)
cv2.imwrite(f"{OUT}/full_now.png", img)

y0, y1 = P.hand_band_measured(img)
xs = P.card_slots(img, y0, y1)
reads, _ = P.tm_read_hand(img)
shown = [f"{SUIT.get(s, '')}{NAME.get(r, r)}" for s, r, _, _l in reads]
print(f"带 {(y0, y1)} | 牌位 {len(xs)} | 读取 {shown}")

# 手牌放大 2.5 倍, 并把"真值是选中的那张"用绿框标出
crop = img[max(0, y0 - 45):y1 + 20, :]
crop = cv2.resize(crop, (int(crop.shape[1] * 2.5), int(crop.shape[0] * 2.5)), interpolation=cv2.INTER_CUBIC)
# 手牌顺序 = 从大到小; 用真值判断哪几张被选中(真值里按 id 给, 这里只能标张数)
cv2.putText(crop, f"truth selected = {len(sel)} card(s)", (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
cv2.imwrite(f"{OUT}/hand_zoom_now.png", crop)
print(f"✓ {OUT}/full_now.png | {OUT}/hand_zoom_now.png")
