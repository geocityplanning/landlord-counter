#!/usr/bin/env python3
"""注解图: 在真实画面上标出每个牌位的"顶边检测结果", 供人眼核对"遮挡"是否存在。

输出: data/shots/annotated_tops.png
  · 每个牌位画一条竖线(位置) + 一个圆点(我测到的该牌位顶边)
  · 绿色 = 判定"已抬起", 蓝色 = 判定"平放", 橙色 = 看不出
  · 顶部写一行说明 + 真值 selected 张数
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

OUT = "data/shots/annotated_tops.png"


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    xs = P.card_slots(f)
    flat = float(y0) + 3.0
    tops = [P.card_top_y(f, x, y0 + 8) for x in xs]

    # 取手牌带上方留白的一段做画布(抬起牌会露在这里)
    top = max(0, y0 - 50)
    crop = f[top:y1 + 10, :].copy()
    S = 2
    big = cv2.resize(crop, (crop.shape[1] * S, crop.shape[0] * S), interpolation=cv2.INTER_CUBIC)
    # 放平基线
    bl = int((flat - top) * S)
    cv2.line(big, (0, bl), (big.shape[1], bl), (255, 0, 255), 1)
    cv2.putText(big, "flat baseline", (6, bl - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
    n_up = 0
    for x, ty in zip(xs, tops):
        d = flat - ty
        raised = d >= 20
        if raised:
            n_up += 1
        col = (0, 220, 0) if raised else (200, 120, 0)
        xx = min(big.shape[1] - 1, int(x) * S)
        cv2.line(big, (xx, 0), (xx, big.shape[0]), col, 1)
        cv2.circle(big, (xx, int((ty - top) * S)), 4, col, -1)
    cv2.rectangle(big, (0, 0), (big.shape[1], 30), (0, 0, 0), -1)
    sel = (c.truth() or {}).get("selected") or []
    cv2.putText(big, f"green=my detector says RAISED ({n_up} slots) | blue=flat | "
                     f"game truth selected={len(sel)}", (6, 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cv2.imwrite(OUT, big)
    print(f"✓ {OUT}  画布 {big.shape} | 判定抬起 {n_up} 个位 (真值 selected {len(sel)} 张)")
    print("  顶边逐个:", list(zip(xs[:14], tops[:14])))
    print(f"  放平基线 ≈ {flat:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
