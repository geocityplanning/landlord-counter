#!/usr/bin/env python3
"""取实时帧的最左/最右牌位放大, 用于确认手牌排序方向(从大到小 or 从小到大)。

用法: PYTHONPATH=src python3 tools/_ask_order.py
输出: data/shots/live_left.png, data/shots/live_right.png, data/shots/live_hand.png
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


def main() -> int:
    c = CDP()
    if not c.find_truth():
        print("没有真值钩子")
        return 2
    t = c.truth()
    hand = t.get("hands", {}).get("0") if t else None
    print("游戏内部手牌数组:", hand)
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    img = dev.snap()
    y0, y1 = P.hand_band_measured(img)
    xs = P.card_slots(img, y0, y1)
    print(f"带 {(y0, y1)} | 牌位 {xs}")
    os.makedirs(OUT, exist_ok=True)
    cv2.imwrite(f"{OUT}/live_hand.png", img[y0 - 10:y1 + 10, :])
    for tag, x in (("left", xs[0]), ("right", xs[-1])):
        crop = img[y0 - 5:y1 + 5, max(0, x - 2):x + 30]
        crop = cv2.resize(crop, (crop.shape[1] * 6, crop.shape[0] * 6), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(f"{OUT}/live_{tag}.png", crop)
        print(f"  {tag}: x={x} → {OUT}/live_{tag}.png")
    print("读取(左→右):", P.tm_read_hand(img)[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
