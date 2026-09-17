#!/usr/bin/env python3
"""在真实画面上圈出"我比对的那条竖条"和"左上角的点数/花色", 供用户确认。

输出: data/shots/strip_explain.png
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

OUT = "data/shots/strip_explain.png"


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    xs = P.card_slots(f)
    x = xs[10] if len(xs) > 10 else xs[0]
    strip = f[max(0, y0 - 45):y1 + 6, x:x + 24].copy()
    S = 5
    big = cv2.resize(strip, (strip.shape[1] * S, strip.shape[0] * S), interpolation=cv2.INTER_NEAREST)
    # 蓝框 = 我取的整条竖条; 红框 = 左上角的点数/花色那小块
    cv2.rectangle(big, (2, 2), (big.shape[1] - 3, big.shape[0] - 3), (255, 120, 0), 2)
    cv2.rectangle(big, (4, 6), (int(24 * S * 0.9), int(96 * S * 0.30)), (0, 0, 255), 2)
    cv2.putText(big, "blue = strip I match (24 x card height)", (6, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(big, "red = rank+suit corner", (6, 44),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cv2.imwrite(OUT, big)
    print(f"✓ {OUT}  取的是 x={x} 这一条(宽 24px × 高 {strip.shape[0]}px), 放大 {S} 倍")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
