#!/usr/bin/env python3
"""实时帧上验证"花色+点数"模板读取(与游戏真值对比, 只看点数)。

用法: PYTHONPATH=src python3 tools/tm_live_check.py [样本数=6]
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

BANK = "data/templates_sr"
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦"}


def norm(p):
    g = cv2.cvtColor(p, cv2.COLOR_RGB2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    g = g - g.mean()
    s = g.std()
    return g / s if s > 1e-6 else g


def load_bank():
    b = {}
    for fn in os.listdir(BANK):
        k = fn.rsplit("_", 1)[0]
        b.setdefault(k, []).append(np.load(os.path.join(BANK, fn)))
    return b


def grid(img, y0, y1):
    peaks = [int(x) for x in P.card_edges(img, y0, y1)]
    if len(peaks) < 2:
        return []
    gaps = np.diff(peaks)
    med = float(np.median(gaps[(gaps >= 18) & (gaps <= 30)])) if len(gaps) else 24.0
    ph = float(np.median([p % med for p in peaks]))
    g = [int(round(ph + k * med)) for k in range(0, int((peaks[-1] - ph) / med) + 1)]
    while g[0] > 30:
        g = [g[0] - int(med)] + g
    return g


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    bank = load_bank()
    c = CDP()
    if not c.find_truth():
        print("没有真值钩子")
        return 2
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    hit = tot = 0
    got_n = 0
    for i in range(n * 3):
        if got_n >= n:
            break
        t1 = c.truth()
        f = dev.snap()
        t2 = c.truth()
        if not t1 or t1.get("phase") != "playing" or t1.get("hands", {}).get("0") != t2.get("hands", {}).get("0"):
            time.sleep(1.5)
            continue
        truth = sorted(int(x) for x in t1["hands"]["0"])
        y0, y1 = P.hand_band_measured(f)
        xs = grid(f, y0, y1)
        reads = []
        for x in xs:
            patch = f[y0 + 8:y1 - 8, x:x + 24]
            if patch.size == 0 or float(patch.std()) < 10:
                continue
            a = norm(patch)
            best, bd = None, 1e18
            for k, arrs in bank.items():
                for t in arrs:
                    b = norm(t)
                    if b.shape != a.shape:
                        continue
                    d = float(np.mean(np.abs(a - b)))
                    if d < bd:
                        bd, best = d, k
            if best is None or bd > 1.35:            # 归一化距离阈值(不像任何已知牌 → 未知)
                reads.append(None)
                continue
            suit, rank = best.split("_")
            reads.append((int(suit), int(rank)))
        got_n += 1
        got_r = sorted(item[1] for item in reads if item)
        cnt = sum(min(got_r.count(z), truth.count(z)) for z in set(truth))
        hit += cnt
        tot += max(len(truth), len(got_r))
        shown = [f"{SUIT.get(item[0], '?')}{NAME.get(item[1], item[1])}" for item in reads if item]
        print(f"  真值 {truth}")
        print(f"  读取 {shown}  未知 {reads.count(None)}")
        print(f"       点数命中 {cnt}/{max(len(truth), len(got_r))}")
        time.sleep(1)
    print(f"★ 实时帧 点数逐张准确率: {hit}/{tot} = {hit / max(1, tot) * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
