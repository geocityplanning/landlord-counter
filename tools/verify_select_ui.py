#!/usr/bin/env python3
"""做"点选前/点选后"对照图, 供人眼判定选中反馈是**抬起**还是**高亮**。

同时读游戏真值 window.__truth().selected → "到底有没有选中"是铁证 ✓

用法: PYTHONPATH=src python3 tools/verify_select_ui.py
输出: data/shots/select_before.png / select_after.png / select_compare.png
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P            # noqa: E402
from landlord_counter.platform.cdp import CDP                # noqa: E402
from landlord_counter.platform.device import AdbDevice       # noqa: E402

OUT = "data/shots"
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {0: "♠", 1: "♥", 2: "♣", 3: "♦", 4: ""}


def label(img, text, y0):
    img = img.copy()
    cv2.rectangle(img, (0, 0), (img.shape[1], 34), (0, 0, 0), -1)
    cv2.putText(img, text, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    return img


def main() -> int:
    c = CDP()
    c.find_truth()
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    a = dev.snap()
    t_before = c.truth() or {}
    y0, y1 = P.hand_band_measured(a)
    xs = P.card_slots(a, y0, y1)
    x = xs[0]
    print(f"带 {(y0, y1)} | 牌位 {len(xs)} 个 | 准备点最左一张 x={x}")
    print(f"点前 真值.selected = {t_before.get('selected')}")
    dev.tap(x + 6, (y0 + y1) // 2, wait=1.2)
    b = dev.snap()
    t_after = c.truth() or {}
    print(f"点后 真值.selected = {t_after.get('selected')}")

    os.makedirs(OUT, exist_ok=True)
    band = 40
    A = a[max(0, y0 - band):y1 + band, :]
    B = b[max(0, y0 - band):y1 + band, :]
    cv2.imwrite(f"{OUT}/select_before.png", A)
    cv2.imwrite(f"{OUT}/select_after.png", B)
    # 对照图: 上下两栏 + 该牌位放大
    top = label(A, "BEFORE (点之前)", y0)
    bot = label(B, "AFTER (点了最左那张)", y0)
    # 画参考线(与点前该牌的顶边对齐) → 一眼看出有没有"抬起"
    top = np.ascontiguousarray(top)
    bot = np.ascontiguousarray(bot)
    cv2.line(top, (x - 8, band - 6), (x + 80, band - 6), (0, 0, 255), 2)
    cv2.line(bot, (x - 8, band - 6), (x + 80, band - 6), (0, 0, 255), 2)
    cv2.rectangle(top, (x - 4, band - 20), (x + 66, A.shape[0] - band + 20), (255, 0, 0), 2)
    cv2.rectangle(bot, (x - 4, band - 20), (x + 66, B.shape[0] - band + 20), (255, 0, 0), 2)
    gap = np.full((14, A.shape[1], 3), 255, dtype=np.uint8)
    comp = np.vstack([top, gap, bot])
    cv2.imwrite(f"{OUT}/select_compare.png", comp)
    print(f"✓ 对照图: {OUT}/select_compare.png  (红框 = 被点的那张; 红线 = 点前顶边位置)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
