#!/usr/bin/env python3
"""把参考图手牌的 27 张竖条放大、编号, 拼成一张对照图(便于人眼报花色)。

用法: PYTHONPATH=src python3 tools/tm_montage.py
输出: data/shots/montage_27.png
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402

REF = "data/shots/ref_27cards.jpg"
OUT = "data/shots/montage_27.png"
SCALE = 3
COLS = 7


def main() -> int:
    img = cv2.cvtColor(cv2.imread(REF), cv2.COLOR_BGR2RGB)
    y0, y1 = P.hand_band_measured(img)
    peaks = P.card_edges(img, y0, y1)
    # 等距网格(与 tm_label_ref 一致): 相位 + 牌距 外推到 27 位
    peaks = [int(x) for x in peaks]
    gaps = np.diff(peaks)
    med = float(np.median(gaps[(gaps >= 18) & (gaps <= 30)]))
    ph = float(np.median([p % med for p in peaks]))
    grid = [int(round(ph + k * med)) for k in range(0, int((peaks[-1] - ph) / med) + 1)]
    while len(grid) < 27:
        grid = [grid[0] - int(med)] + grid
    grid = grid[:27]
    strips = []
    for i, x in enumerate(grid, 1):
        s = img[y0:y1, max(0, x):x + 24]
        s = cv2.resize(s, (s.shape[1] * SCALE, s.shape[0] * SCALE), interpolation=cv2.INTER_NEAREST)
        s = cv2.copyMakeBorder(s, 30, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        cv2.putText(s, str(i), (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        strips.append(s)
    h = max(s.shape[0] for s in strips)
    rows = []
    for r in range(0, len(strips), COLS):
        row = strips[r:r + COLS]
        row = [cv2.copyMakeBorder(s, 0, h - s.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for s in row]
        while len(row) < COLS:
            row.append(np.full_like(row[0], 255))
        rows.append(np.hstack(row))
    sheet = np.vstack(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cv2.imwrite(OUT, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print(f"✓ 对照图: {OUT}  {sheet.shape}  (编号 1..27, 左→右)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
