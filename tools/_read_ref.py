#!/usr/bin/env python3
"""对参考截图跑模板读取(实验台): 把 27 张的读数打出来, 供人眼对照原图核对。

用法: PYTHONPATH=src python3 tools/_read_ref.py [图片路径]
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402

NAMES = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "data/shots/ref_27cards.jpg"
    img = cv2.cvtColor(cv2.imread(ref), cv2.COLOR_BGR2RGB)
    y0, y1 = P.hand_band_measured(img)
    peaks = P.card_edges(img, y0, y1)
    out, info = P.tm_read_hand(img)
    print(f"图: {ref}")
    print(f"手牌带 {(y0, y1)} | 卡边界 {len(peaks)} 个 | 模板库 {info['tpl']}")
    print(f"读取 {len(out)} 张 (从左到右):")
    print("   " + " ".join(NAMES.get(z, str(z)) for z, _ in out))
    print(f"   未知位 {info['unknown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
