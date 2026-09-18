#!/usr/bin/env python3
"""把每个牌位的**裁切条**画成一张对照图: 上排=我读的, 下排=真值, 红框=读错 ✓

用途: 读牌不准时, 一眼看出"是位置偏了"还是"模板不对" ✓(比猜快一个量级)
输出: data/shots/slot_crops.png
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L            # noqa: E402
from landlord_counter.guandan import percept as P           # noqa: E402
from landlord_counter.platform.cdp import CDP               # noqa: E402
from landlord_counter.platform.device import AdbDevice      # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
OUT = "data/shots/slot_crops.png"


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    zhi = (t.get("hands") or {}).get("0") or []
    f = dev.snap()
    g = L.geom()
    n = len(zhi)
    slots, chk = L.locate(f, n)
    print(f"定位: {len(slots)} 位 (来源 {chk.measured.get('source')}) | 真值 {n} 张")
    cards, _i = P.tm_read_hand(f, slots=slots)

    y0, y1 = g.hand_y0, g.hand_y1
    h = y1 - y0
    SC = 2
    cols = []
    for i, x in enumerate(slots):
        x0 = max(0, int(x))
        strip = f[y0 - 40:y1 + 6, x0:x0 + 24]          # 含抬起区, 便于看位置
        if strip.size == 0:
            continue
        big = cv2.resize(strip, (24 * SC, strip.shape[0] * SC), interpolation=cv2.INTER_NEAREST)
        my = cards[i][1] if i < len(cards) else 0
        tr = zhi[i] if i < len(zhi) else 0
        ok = (my == tr)
        col = (0, 200, 0) if ok else (0, 0, 255)
        cv2.rectangle(big, (0, 0), (big.shape[1] - 1, big.shape[0] - 1), col, 2)
        cv2.putText(big, str(NAME.get(my, my)), (2, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)
        cv2.putText(big, str(NAME.get(tr, tr)), (2, big.shape[0] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)
        cv2.putText(big, f"{i}", (2, big.shape[0] // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (128, 128, 128), 1)
        cols.append(big)
    if not cols:
        print("✗ 没有可画的牌位")
        return 1
    # 两行拼(每行 13 个)
    per = 13
    rows = []
    for k in range(0, len(cols), per):
        chunk = cols[k:k + per]
        w = sum(cc.shape[1] for cc in chunk) + 4 * len(chunk)
        hh = max(cc.shape[0] for cc in chunk)
        row = np.full((hh, w, 3), 30, np.uint8)
        xx = 0
        for cc in chunk:
            row[:cc.shape[0], xx:xx + cc.shape[1]] = cc
            xx += cc.shape[1] + 4
        rows.append(row)
    W = max(r.shape[1] for r in rows)
    H = sum(r.shape[0] for r in rows) + 8 * len(rows) + 30
    out = np.full((H, W, 3), 30, np.uint8)
    yy = 26
    for r in rows:
        out[yy:yy + r.shape[0], :r.shape[1]] = r
        yy += r.shape[0] + 8
    bad = sum(1 for i in range(len(cards)) if i < len(zhi) and cards[i][1] != zhi[i])
    cv2.putText(out, f"green=OK red=WRONG ({bad} bad of {n}) | per strip: mine(top) vs truth(bottom, yellow)",
                (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cv2.imwrite(OUT, out)
    print(f"✓ {OUT} | 读错 {bad}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
