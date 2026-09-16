#!/usr/bin/env python3
"""用"已确认的花色锚点"自动判定剩余牌的花色(实验台)。

背景(2026-09-16): 用户报 27 张花色时, 黑色套(♠/♣)在小图里易混 ✗。
用户随后确认: 7 号=♣J, 27 号=♣2 (梅花锚点); 3/5/25 号=♠ (黑桃锚点)。
本脚本用**像素**判定其余牌:
  ① 先看下部有没有红色像素 → 红套(♥/♦) 还是黑套(♠/♣)
  ② 黑套再用锚点模板比对(♠ vs ♣ 字形不同)
输出: 每号位的推定花色 + 与用户报告的差异清单。

用法: PYTHONPATH=src python3 tools/tm_suit_audit.py
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402

REF = "data/shots/ref_27cards.jpg"
RANKS = ([16] + [14] + [12, 12] + [11, 11, 11] + [10] * 5 + [9] + [8, 8] + [7, 7]
         + [5, 5, 5] + [4] + [3, 3, 3] + [2, 2, 2])            # 1..27 的点数(用户已确认)
REPORT = ["?", "♦", "♠", "♦", "♠", "♥", "♣", "♠", "♥", "♠", "♠", "♦", "♦",
          "♥", "♥", "♣", "♦", "♥", "♠", "♦", "♥", "♥", "♥", "♦", "♠", "♥", "♣"]
ANCHOR_SPADE = [3, 5, 25]
ANCHOR_CLUB = [7, 27]


def grid27(img) -> list:
    y0, y1 = P.hand_band_measured(img)
    peaks = [int(x) for x in P.card_edges(img, y0, y1)]
    gaps = np.diff(peaks)
    med = float(np.median(gaps[(gaps >= 18) & (gaps <= 30)]))
    ph = float(np.median([p % med for p in peaks]))
    g = [int(round(ph + k * med)) for k in range(0, int((peaks[-1] - ph) / med) + 1)]
    while len(g) < 27:
        g = [g[0] - int(med)] + g
    return y0, y1, g[:27]


def main() -> int:
    img = cv2.cvtColor(cv2.imread(REF), cv2.COLOR_BGR2RGB)
    y0, y1, xs = grid27(img)
    strips = [img[y0:y1, x:x + 24] for x in xs]
    # 花色符号通常在牌面下半部 → 取该区域做判定
    def suit_zone(s):
        h = s.shape[0]
        return s[int(h * 0.45):int(h * 0.95)]
    def is_red(s):
        z = suit_zone(s).astype(int)
        r, g, b = z[:, :, 0], z[:, :, 1], z[:, :, 2]
        return int(((r > 140) & (r - g > 45) & (r - b > 45)).sum()) > 12
    tpl_sp = np.median(np.stack([suit_zone(strips[i - 1]).astype(np.float32) for i in ANCHOR_SPADE]), axis=0)
    tpl_cl = np.median(np.stack([suit_zone(strips[i - 1]).astype(np.float32) for i in ANCHOR_CLUB]), axis=0)
    print("号位 点数 用户报  像素判定  说明")
    print("-" * 46)
    diff = []
    names = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
    for i, s in enumerate(strips, 1):
        rk = names.get(RANKS[i - 1], str(RANKS[i - 1]))
        rep = REPORT[i - 1]
        if rep == "?":
            print(f"{i:>3}  {rk:<4} {'大王':<5} 大王        彩色牌, 不分花色")
            continue
        z = suit_zone(s).astype(np.float32)
        if not is_red(s):
            d_sp = float(np.mean(np.abs(z - tpl_sp)))
            d_cl = float(np.mean(np.abs(z - tpl_cl)))
            got = "♠" if d_sp < d_cl else "♣"
            why = f"黑套比对: ♠{d_sp:.1f} vs ♣{d_cl:.1f}"
        else:
            got = rep if rep in ("♥", "♦") else "♥/♦?"
            why = "红套(有红色像素)"
        flag = "" if got == rep else "  ← 与用户报告不同"
        if flag:
            diff.append((i, rk, rep, got))
        print(f"{i:>3}  {rk:<4} {rep:<5} {got:<9} {why}{flag}")
    print("-" * 46)
    if diff:
        print("需要用户复核的:")
        for i, rk, rep, got in diff:
            print(f"  {i} 号位({rk}): 用户说 {rep}, 像素判 {got}")
    else:
        print("✓ 像素判定与用户报告完全一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
