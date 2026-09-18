#!/usr/bin/env python3
"""读牌认错的**定量诊断**: 对每个牌位, 列出距离最近的**前 3 个模板**及距离 ✓

用户 2026-09-18 判断: "没有切偏, 是认错" ⇒ 那么问题在匹配环节。本工具回答:
  · 正确的模板排第几? (排第 2 ⇒ 是阈值/平票问题; 完全在很后面 ⇒ 模板本身不像 ✗)
  · 前 2 名的距离差多少? (差很小 ⇒ 判别力不足; 差很大 ⇒ 是模板错/标签错 ✓)
  · 这些模板是哪一局采的(_auto_ 后缀) / 参考模板 ✓

用法: PYTHONPATH=src python3 tools/diag_read_match.py
"""
from __future__ import annotations

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L            # noqa: E402
from landlord_counter.guandan import percept as P           # noqa: E402
from landlord_counter.platform.cdp import CDP               # noqa: E402
from landlord_counter.platform.device import AdbDevice      # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    zhi = (t.get("hands") or {}).get("0") or []
    f = dev.snap()
    g = L.geom()
    n = len(zhi)
    slots, chk = L.locate(f, n)
    print(f"定位 {len(slots)} 位(来源 {chk.measured.get('source')}) | 真值 {n} 张")

    # 与读取端**完全相同**的裁切口径 ✓
    bank = P.load_templates_sr()
    y0, y1 = g.hand_y0, g.hand_y1
    card_h = y1 - y0 - 16
    from landlord_counter.guandan import read as R
    R.maybe_collect(f, t.get("handIds") or [], zhi, slots=slots)   # 确保有本局模板 ✓
    bank = P.load_templates_sr()

    print(f"\n模板库 {len(bank)} 个键")
    print(f"{'位':>3} {'真值':>5} {'我读':>5} {'正确模板排名':>6} {'第1名距离':>8} {'正确距离':>8}  前3名")
    bad = 0
    for i, x in enumerate(slots):
        x0 = int(x)
        ty = P.card_top_y(f, x0, y0 + 8)
        patch = f[ty + 8:ty + 8 + card_h, x0:x0 + 24]
        if patch.size == 0:
            continue
        # ★ 与读取端**同一条路**(slide_best: 竖直滑动 + 各自缩放对齐 ✓)
        #   裸比较会因"模板 105px / 片段 104px"的形状差**静默跳过全部模板** ✗(实测踩到)
        dists = []
        for k, arrs in bank.items():
            for b in arrs:
                dy, d = P.slide_best(f, int(x0), y0, b)
                if dy is not None:
                    dists.append((float(d), k))
        if not dists:
            continue
        dists.sort()
        tr = zhi[i] if i < len(zhi) else 0
        my = dists[0][1]
        my_rank = int(my.split("_")[-1] if False else my.split("_")[1])   # 键形如 花色_点数
        # 正确模板的最佳距离与前 3 名
        correct = [(d, k) for d, k in dists if int(k.split("_")[1]) == tr]
        rank_correct = 1 + sum(1 for d, _k in dists if d < correct[0][0]) if correct else -1
        top3 = ", ".join(f"{k}:{d:.2f}" for d, k in dists[:3])
        flag = "" if my_rank == tr else "  ✗"
        if my_rank != tr:
            bad += 1
        print(f"{i:>3} {NAME.get(tr, tr):>5} {NAME.get(my_rank, my_rank):>5} "
              f"{rank_correct:>8} {dists[0][0]:>8.3f} {correct[0][0] if correct else -1:>8.3f}  {top3}{flag}")
    print(f"\n读错 {bad} 位 / 共 {len(slots)}")
    print("判读: 正确模板排名=1 ⇒ 其实是对的; 排名=2 且距离接近 ⇒ 判别力不足(调阈值/换特征);")
    print("      排名很靠后 ⇒ 模板本身不像(裁切口径/标签问题) ✗")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
