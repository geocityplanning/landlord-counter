#!/usr/bin/env python3
"""构建"花色+点数"模板库 + 归一化匹配器(实验台)。

标签来自用户对参考图 27 张的逐张确认(2026-09-16):
  大王 ♦A ♠Q ♦Q ♠J ♥J ♣J ♠10 ♥10 ♣10 ♣10 ♦10 ♦9 ♥8 ♥8 ♣7 ♦7 ♥5 ♠5 ♦5 ♥4 ♥3 ♥3 ♦3 ♠2 ♥2 ♣2
  (已通过"每种(花色,点数) ≤ 2"的牌堆校验 ✓)

匹配用**归一化**表示(灰度 + 去均值/除标准差) → 抹平 JPEG/PNG 压缩与亮度差异 ✓

用法: PYTHONPATH=src python3 tools/tm_build.py
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402

REF = "data/shots/ref_27cards.jpg"
OUT = "data/templates_sr"
KEY = ["1_16", "4_14", "1_12", "4_12", "1_11", "3_11", "2_11", "1_10", "3_10", "2_10",
       "2_10", "4_10", "4_9", "3_8", "3_8", "2_7", "4_7", "3_5", "1_5", "4_5",
       "3_4", "3_3", "3_3", "4_3", "1_2", "3_2", "2_2"]     # 花色_点数 (1♠ 2♣ 3♥ 4♦)


def norm_patch(p: np.ndarray) -> np.ndarray:
    """归一化: 灰度 → 中心化+标准化(抹平压缩/亮度/对比差异)。"""
    g = cv2.cvtColor(p, cv2.COLOR_RGB2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    g = g - g.mean()
    s = g.std()
    return g / s if s > 1e-6 else g


def grid27(img) -> list:
    y0, y1 = P.hand_band_measured(img)
    peaks = [int(x) for x in P.card_edges(img, y0, y1)]
    gaps = np.diff(peaks)
    med = float(np.median(gaps[(gaps >= 18) & (gaps <= 30)]))
    ph = float(np.median([p % med for p in peaks]))
    g = [int(round(ph + k * med)) for k in range(0, int((peaks[-1] - ph) / med) + 1)]
    while len(g) < len(KEY):
        g = [g[0] - int(med)] + g
    return y0, y1, g[:len(KEY)]


def main() -> int:
    img = cv2.cvtColor(cv2.imread(REF), cv2.COLOR_BGR2RGB)
    y0, y1, xs = grid27(img)
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    for i, (x, k) in enumerate(zip(xs, KEY), 1):
        patch = img[y0 + 8:y1 - 8, x:x + 24]
        if patch.size == 0:
            continue
        np.save(os.path.join(OUT, f"{k}_{i}.npy"), patch.astype(np.uint8))
    print(f"✓ 采集 {len(KEY)} 个牌面 → {OUT} ({len(set(KEY))} 个不同花色+点数)")
    # 归一化自校验: 回读这张图
    bank = {}
    for fn in os.listdir(OUT):
        k = fn.rsplit("_", 1)[0]
        bank.setdefault(k, []).append(np.load(os.path.join(OUT, fn)))
    ok = 0
    for i, (x, k) in enumerate(zip(xs, KEY), 1):
        patch = img[y0 + 8:y1 - 8, x:x + 24]
        if patch.size == 0:
            continue
        a = norm_patch(patch)
        best, bd = None, 1e18
        for kk, arrs in bank.items():
            for t in arrs:
                b = norm_patch(t)
                if b.shape != a.shape:
                    continue
                d = float(np.mean(np.abs(a - b)))
                if d < bd:
                    bd, best = d, kk
        ok += 1 if best == k else 0
        if best != k:
            print(f"   ✗ {i} 号位({k}) 认成 {best}  (d={bd:.3f})")
    print(f"★ 归一化后自校验(花色+点数): {ok}/{len(KEY)} = {ok / len(KEY) * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
