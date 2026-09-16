#!/usr/bin/env python3
"""读牌自检: ① 用户标注的参考图(27 张, 花色+点数都有标注) ② 实时帧(对游戏真值查点数)。

用法: PYTHONPATH=src python3 tools/tm_selftest.py [live样本数=4]
"""
from __future__ import annotations

import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402

REF = "data/shots/ref_27cards.jpg"
# 用户 2026-09-16 逐张确认(含两次自纠 + 7号位裁决): 花色_点数
LABELS = ["1_16", "4_14", "1_12", "4_12", "1_11", "3_11", "2_11", "1_10", "3_10", "2_10",
          "2_10", "4_10", "4_9", "3_8", "3_8", "2_7", "4_7", "3_5", "1_5", "4_5",
          "3_4", "3_3", "3_3", "4_3", "1_2", "3_2", "2_2"]
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦"}


def show(reads):
    return " ".join(f"{SUIT.get(s, '?')}{NAME.get(r, r)}" for s, r, _ in reads)


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    # ① 参考图
    img = cv2.cvtColor(cv2.imread(REF), cv2.COLOR_BGR2RGB)
    reads, info = P.tm_read_hand(img)
    got = [f"{s}_{r}" for s, r, _ in reads]
    hit = sum(1 for i, k in enumerate(got) if i < len(LABELS) and k == LABELS[i])
    print(f"① 用户标注图: 读 {len(reads)} 张 | 逐位(花色+点数)对: {hit}/{len(LABELS)} = {hit / len(LABELS) * 100:.1f}%")
    print(f"   读取 {show(reads)}")
    print(f"   未知位 {info['unknown']} (卡边界 {len(P.card_slots(img))} 个位)")
    # ② 实时帧
    from landlord_counter.platform.cdp import CDP
    from landlord_counter.platform.device import AdbDevice
    c = CDP()
    if not c.find_truth():
        print("② 实时帧: 没有真值钩子, 跳过")
        return 0
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    hits = tot = 0
    for i in range(n * 3):
        if tot >= n:
            break
        t1 = c.truth()
        f = dev.snap()
        t2 = c.truth()
        if not t1 or t1.get("phase") != "playing":
            time.sleep(1.5)
            continue
        if t1.get("hands", {}).get("0") != t2.get("hands", {}).get("0"):
            time.sleep(1.0)
            continue
        truth = sorted(int(x) for x in t1["hands"]["0"])
        rd, _ = P.tm_read_hand(f)
        rk = sorted(r for _, r, _ in rd)
        cnt = sum(min(rk.count(z), truth.count(z)) for z in set(truth))
        hits += cnt
        tot += max(len(truth), len(rk))
        print(f"② 真值 {truth}")
        print(f"   读取 {[NAME.get(r, r) for r in rk]}  ({len(rd)} 张)")
        time.sleep(1)
    print(f"② 实时帧 点数逐张准确率: {hits}/{tot} = {hits / max(1, tot) * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
