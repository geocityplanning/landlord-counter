#!/usr/bin/env python3
"""画出"我判定的抬起牌"(用滑动匹配的抬起量) —— 供用户人眼核对。

输出: data/shots/raised_marked.png
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦", 0: ""}
OUT = "data/shots/raised_marked.png"


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    cards, info = P.tm_read_hand(f)
    crop = f[max(0, y0 - 50):y1 + 6, :].copy()
    S = 2
    big = cv2.resize(crop, (crop.shape[1] * S, crop.shape[0] * S), interpolation=cv2.INTER_CUBIC)
    n_up = 0
    for s, r, x, l in cards:
        xx = int(x) * S
        if xx >= big.shape[1]:
            continue
        if l >= 18:
            n_up += 1
            cv2.rectangle(big, (xx + 1, 4), (min(big.shape[1] - 2, xx + 24 * S - 2), big.shape[0] - 40),
                          (0, 220, 0), 2)
            cv2.putText(big, f"{SUIT.get(s, '')}{NAME.get(r, r)}", (xx + 2, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 2)
            cv2.putText(big, f"{l:.0f}px", (xx + 2, big.shape[0] - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 1)
        else:
            cv2.line(big, (xx, 0), (xx, big.shape[0]), (200, 120, 0), 1)
    cv2.rectangle(big, (0, big.shape[0] - 34), (big.shape[1], big.shape[0]), (0, 0, 0), -1)
    cv2.putText(big, f"green = my detector: RAISED ({n_up} cards) | blue = flat | baseline {info['base']:.0f}px",
                (6, big.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cv2.imwrite(OUT, big)
    print(f"✓ {OUT} | 判抬起 {n_up} 张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
