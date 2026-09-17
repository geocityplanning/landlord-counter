#!/usr/bin/env python3
"""把"我读到的 27 张"逐张标在画面上, 并与游戏真值逐张打 ✓/✗ —— 供人眼一眼验收。

输出: data/shots/read_result.png
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦", 0: ""}
OUT = "data/shots/read_result.png"


def main() -> int:
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    read = P.tm_read_hand(f)[0]
    truth = sorted((t.get("hands") or {}).get("0") or [], reverse=True)

    crop = f[max(0, y0 - 48):y1 + 8, :].copy()
    S = 2
    big = cv2.resize(crop, (crop.shape[1] * S, crop.shape[0] * S), interpolation=cv2.INTER_CUBIC)
    ok = 0
    for i, (s_, r_, x) in enumerate(read):
        tr = truth[i] if i < len(truth) else None
        hit = (tr == r_)
        ok += 1 if hit else 0
        xx = int(x) * S
        if xx >= big.shape[1]:
            continue
        col = (0, 200, 0) if hit else (0, 0, 255)
        cv2.line(big, (xx, 0), (xx, big.shape[0]), col, 1)
        cv2.putText(big, f"{NAME.get(r_, r_)}", (xx + 1, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, col, 2 if not hit else 1)
    bar = 34
    cv2.rectangle(big, (0, big.shape[0] - bar), (big.shape[1], big.shape[0]), (0, 0, 0), -1)
    cv2.putText(big, f"my read: {len(read)} cards | match vs game truth: {ok}/{len(truth)}",
                (6, big.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cv2.imwrite(OUT, big)
    print(f"✓ {OUT} | 读 {len(read)} 张 | 与真值一致 {ok}/{len(truth)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
