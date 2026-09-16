#!/usr/bin/env python3
"""用"用户标注的参考截图"采模板 + 当场验证(实验台)。

用户 2026-09-16 报的 27 张(从左到右, 从大到小):
    大王 A Q Q J J J 10 10 10 10 10 9 8 8 7 7 5 5 5 4 3 3 3 2 2 2
牌位: 卡边界峰给出 24px 间距, 用"牌距 + 相位"外推成 27 个等距位(实测首张与末张的边界
可能不在峰里 → 需要两头外推)。

用法: PYTHONPATH=src python3 tools/tm_label_ref.py
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402

REF = "data/shots/ref_27cards.jpg"
OUT = "data/templates_lab"
LABELS = ([16] + [14] + [12, 12] + [11, 11, 11] + [10] * 5 + [9] + [8, 8] + [7, 7]
          + [5, 5, 5] + [4] + [3, 3, 3] + [2, 2, 2])       # 16=大王, 15=小王, 14=A, 11=J, 12=Q


def slot_grid(peaks: list, n: int) -> list:
    """由卡边界峰推出 n 个等距牌位(牌距=峰间距中位数; 两头按需外推)。"""
    peaks = [int(x) for x in peaks]
    gaps = np.diff(peaks)
    med = float(np.median(gaps[(gaps >= 18) & (gaps <= 30)])) if len(gaps) else 24.0
    # 相位: 各峰 mod 牌距 → 取中位
    ph = float(np.median([p % med for p in peaks]))
    grid = [int(round(ph + k * med)) for k in range(0, int((peaks[-1] - ph) / med) + 1)]
    # 两头外推, 凑到 n 个
    while len(grid) < n:
        grid = [grid[0] - int(med)] + grid
        if len(grid) < n:
            grid = grid + [grid[-1] + int(med)]
    # 右端对齐: 若最左位明显偏右(首张没边界), 再往左挪
    return grid[:n]


def main() -> int:
    img = cv2.cvtColor(cv2.imread(REF), cv2.COLOR_BGR2RGB)
    y0, y1 = P.hand_band_measured(img)
    peaks = P.card_edges(img, y0, y1)
    n = len(LABELS)
    grid = slot_grid(peaks, n)
    print(f"参考图 {REF}  带 {y0,y1}  峰 {len(peaks)} 个 → 外推 {len(grid)} 个牌位")
    print("  牌位:", grid)
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    ok = 0
    for x, z in zip(grid, LABELS):
        patch = img[y0 + 8:y1 - 8, x:x + 24]
        if patch.size == 0:
            continue
        np.save(os.path.join(OUT, f"{z}_{x}.npy"), patch.astype(np.uint8))
        ok += 1
    print(f"  采集 {ok} 个牌面样本 → {OUT}")
    # 当场验证: 用这些样本回读这张图
    tpl = {}
    for fn in os.listdir(OUT):
        z = int(fn.split("_")[0])
        tpl.setdefault(z, []).append(np.load(os.path.join(OUT, fn)).astype(np.float32))
    right = 0
    reads = []
    for x, z in zip(grid, LABELS):
        patch = img[y0 + 8:y1 - 8, x:x + 24].astype(np.float32)
        best, bd = None, 1e18
        for tz, arrs in tpl.items():
            for t in arrs:
                if t.shape != patch.shape:
                    continue
                d = float(np.mean(np.abs(patch - t)))
                if d < bd:
                    bd, best = d, tz
        reads.append(best)
        right += 1 if best == z else 0
    names = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
    print("\n读取结果(左→右, 与标注对照):")
    print("  标注:", " ".join(names.get(z, str(z)) for z in LABELS))
    print("  读取:", " ".join(names.get(z, str(z)) if z else "?" for z in reads))
    print(f"★ 自校验: {right}/{n} = {right / n * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
