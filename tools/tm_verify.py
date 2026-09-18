#!/usr/bin/env python3
"""读牌验收(位对位, 不排序): ① 用户标注的 27 张图 ② 实时帧对游戏真值。

口径 = 身份级逐张准确率: 第 i 位读出的牌 == 真值第 i 位(张数也必须一致)。

用法: PYTHONPATH=src python3 tools/tm_verify.py [实时样本数=6]
"""
from __future__ import annotations

import os
import sys
import time

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402

REF = "data/shots/ref_27cards.jpg"
LABELS = ["1_16", "4_14", "1_12", "4_12", "1_11", "3_11", "2_11", "1_10", "3_10", "2_10",
          "2_10", "4_10", "4_9", "3_8", "3_8", "2_7", "4_7", "3_5", "1_5", "4_5",
          "3_4", "3_3", "3_3", "4_3", "1_2", "3_2", "2_2"]
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦"}


def fmt(reads):
    return " ".join(f"{SUIT.get(s, '')}{NAME.get(r, r)}" for s, r, _, _l in reads)


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    # ① 标注图
    img = cv2.cvtColor(cv2.imread(REF), cv2.COLOR_BGR2RGB)
    reads, info = P.tm_read_hand(img)
    got = [f"{s}_{r}" for s, r, _, _l in reads]
    same_n = len(got) == len(LABELS)
    hit = sum(1 for a, b in zip(got, LABELS) if a == b)
    print(f"① 标注图: 张数 {len(got)}/{len(LABELS)} {'✓' if same_n else '✗'} | 逐位对 {hit}/{len(LABELS)}"
          f" = {hit / len(LABELS) * 100:.1f}%")
    print(f"   {fmt(reads)}")
    # ② 实时帧
    from landlord_counter.platform.cdp import CDP
    from landlord_counter.platform.device import AdbDevice
    c = CDP()
    if not c.find_truth():
        print("② 实时帧: 无真值钩子, 跳过")
        return 0
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    per = []
    for _ in range(n * 3):
        if len(per) >= n:
            break
        t1 = c.truth()
        f = dev.snap()
        t2 = c.truth()
        if not t1 or t1.get("phase") != "playing":
            time.sleep(1.5)
            continue
        h1 = t1.get("hands", {}).get("0")
        if not h1 or h1 != t2.get("hands", {}).get("0"):
            time.sleep(1.0)
            continue
        truth = [int(x) for x in h1]
        rd, _ = P.tm_read_hand(f)
        rk = [r for _, r, _, _l in rd]
        hit_n = sum(1 for a, b in zip(rk, truth) if a == b)
        per.append((len(rk), len(truth), hit_n))
        print(f"② 真值({len(truth)}) {NAME.get(truth[0], truth[0])}… | 读取({len(rk)}) {[NAME.get(r, r) for r in rk]}")
        print(f"   张数 {'✓' if len(rk) == len(truth) else '✗'} | 逐位对 {hit_n}/{len(truth)}")
        time.sleep(1)
    if per:
        nn = sum(1 for a, b, _ in per if a == b)
        hh = sum(h for _, _, h in per)
        tt = sum(b for _, b, _ in per)
        print(f"★ 实时帧: 张数全对 {nn}/{len(per)} 帧 | 逐张(位对位) {hh}/{tt} = {hh / max(1, tt) * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
