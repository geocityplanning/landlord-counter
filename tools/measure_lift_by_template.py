#!/usr/bin/env python3
"""模板滑动测抬起量 —— 修正版(模板是原始高度, 不是 96x24 ✗)。

做法: 对每张牌, 取其列 x..x+24 的一段竖直窗口(覆盖放平/抬起两种位置),
      对每个候选起始行 dy: 取"模板自身高度 H"的那一段 → 与模板各自缩放对齐后比 → 取最优
      → 最优起始行相对"放平位置"的偏移 = 抬起量 ✓
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

NORM_H, NORM_W = 96, 24


def main() -> int:
    c = CDP()
    c.find_truth()
    sel = len((c.truth() or {}).get("selected") or [])
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    xs = P.card_slots(f)
    bank = P.load_templates_sr()
    # 取每个点数的一个样本(原始高度)
    samples = [(k, t[0]) for k, t in bank.items() if t]
    print(f"真值 selected = {sel} | 牌位 {len(xs)} | 模板类别 {len(samples)} | 样本高度 "
          f"{sorted({s[1].shape[0] for s in samples})[:5]}")
    gray = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    res = []
    for x in xs:
        x0 = max(0, int(x))
        win = gray[max(0, y0 - 56): y0 + 56 + 130, x0:x0 + 24]
        if win.shape[0] < 140:
            continue
        best = (None, 1e9, 0)
        for k, tpl in samples:
            H = tpl.shape[0]
            if win.shape[0] < H + 4:
                continue
            tn = cv2.GaussianBlur(cv2.cvtColor(tpl, cv2.COLOR_RGB2GRAY).astype(np.float32), (3, 3), 0)
            tn = cv2.resize(tn, (NORM_W, NORM_H), interpolation=cv2.INTER_AREA)
            tn = (tn - tn.mean()) / (tn.std() + 1e-6)
            for dy in range(0, win.shape[0] - H):
                seg = cv2.resize(win[dy:dy + H], (NORM_W, NORM_H), interpolation=cv2.INTER_AREA)
                seg = (seg - seg.mean()) / (seg.std() + 1e-6)
                d = float(np.mean(np.abs(seg - tn)))
                if d < best[1]:
                    best = (k, d, dy)
        # "放平"时牌面顶边在窗口里的位置 ≈ 56 - 3 = 53
        res.append((x0, best[0], best[2] - 53, round(best[1], 3)))
    ups = [r for r in res if r[2] <= -18]
    print(f"★ 判定抬起 = {len(ups)} 个 (真值 {sel} 张)")
    for x, k, dy, d in res[:18]:
        mark = "抬起" if dy <= -18 else ("平放" if dy >= -8 else "?")
        print(f"   x={x:>4} 模板={k:<6} 偏移={dy:>4}px 距离={d:<7} → {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
