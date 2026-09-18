#!/usr/bin/env python3
"""对账: 游戏真值的数组顺序 vs 屏幕上的显示顺序 —— 到底哪个和牌位对得上。

用法: python3 tools/check_truth_order.py
输出: 每个牌位 | 真值数组第 i 项 | 模板读出来的点数 | handIds 第 i 项 —— 一眼看谁对得上 ✓
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L          # noqa: E402
from landlord_counter.guandan import percept as P         # noqa: E402
from landlord_counter.platform.cdp import CDP             # noqa: E402
from landlord_counter.platform.device import AdbDevice    # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def nm(v) -> str:
    try:
        return NAME.get(int(v), str(int(v)))
    except (TypeError, ValueError):
        return str(v)


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    hands = (t.get("hands") or {}).get("0") or []
    ids = list(t.get("handIds") or [])
    img = dev.snap()
    slots, _ = L.locate(img, len(hands))
    reads = [a[1] for a in P.tm_read_hand(img, y0=L.geom().hand_y0, slots=slots)[0]]

    if "--recollect" in sys.argv:
        # 决定性实验: 用**当前版面**重采一次模板, 再读同一帧 ✓
        import glob
        for f in glob.glob("data/templates_rank/0_*.npy"):
            os.remove(f)
        n = P.tm_collect_from_ranks(img, [int(v) for v in hands], out_dir="data/templates_rank",
                                    tag="auto", slots=slots,
                                    y0=L.geom().hand_y0, y1=L.geom().hand_y1)   # ★ 必须用标定带 ✓
        print(f"✓ 用当前版面重采了 {n} 个模板 → 再读同一帧:")
        reads = [a[1] for a in P.tm_read_hand(img, y0=L.geom().hand_y0, slots=slots)[0]]

    print(f"真值 hands 数组: {' '.join(nm(v) for v in hands)}   (共 {len(hands)})")
    print(f"真值 handIds   : {ids}")
    print(f"牌位数         : {len(slots)}")
    print("位 |  真值数组[i] | 模板读 | handIds[i]")
    for i in range(max(len(slots), len(hands))):
        a = nm(hands[i]) if i < len(hands) else "-"
        b = nm(reads[i]) if i < len(reads) else "-"
        c_ = ids[i] if i < len(ids) else "-"
        same = "✓" if a == b else "✗"
        print(f"{i + 1:>3} | {a:>10} | {b:>6} {same} | {c_}")
    # 关键结论
    sorted_desc = sorted((int(v) for v in hands), reverse=True)
    is_sorted = [int(v) for v in hands] == sorted_desc
    print(f"\n真值数组是否【从大到小排】(= 屏幕显示顺序)? {'是 ✓' if is_sorted else '**不是** ✗'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
