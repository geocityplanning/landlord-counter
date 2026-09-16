#!/usr/bin/env python3
"""把参考截图的手牌带切成 3 段, 便于人眼逐张报牌(实验台)。

用法: python3 tools/_split_ref.py [图片路径]
"""
from __future__ import annotations

import sys

import cv2

REF = sys.argv[1] if len(sys.argv) > 1 else "data/shots/ref_27cards.jpg"
Y0, Y1 = 800, 950          # 牌面带(上下各留一点)
XS = [(0, 230), (218, 448), (436, 660)]

img = cv2.imread(REF)
for i, (a, b) in enumerate(XS, 1):
    crop = img[Y0:Y1, a:b]
    out = f"data/shots/ref_part{i}.png"
    cv2.imwrite(out, crop)
    print(f"  {out}  x={a}..{b}  {crop.shape}")
