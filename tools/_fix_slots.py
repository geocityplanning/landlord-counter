#!/usr/bin/env python3
"""一次性: 简化 tm_read_hand 的牌位定位(删掉过度滤波, 直接用 card_edges)。

原因(2026-09-16 实测): 满手 27 张的参考图上, card_edges 直接给出**干净 27 峰**(间距正好 24px);
而后来加的"最长等距串/末位补格/相位筛"反而把干净结果搞乱 → 读出一堆重复位 ✗
"""
import re

P = "src/landlord_counter/guandan/percept.py"
s = open(P).read()

m = re.search(r"    # 牌位提取\(2026-09-16 实测\).*?\n(    out = \[\]\n)", s, re.S)
if not m:
    print("没找到要改的段(可能已改过)")
    raise SystemExit(0)

new = ("    # 牌位 = 卡边界实测结果(实测: 满手 27 张给出干净 27 峰, 间距正好 24px ✓)\n"
       "    # 教训: 此处曾加\"最长等距串/末位补格/相位筛\"等滤波 → 反而把干净结果搞乱 ✗ → 删掉\n")
s = s[:m.start()] + new + s[m.end(1):]
open(P, "w").write(s)
print("✓ 已简化牌位定位")
