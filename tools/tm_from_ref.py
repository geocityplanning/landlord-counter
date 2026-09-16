#!/usr/bin/env python3
"""用"参考截图 + 游戏真值"采一次干净模板(满手 27 张, 峰数应与真值张数一致)。

用法: PYTHONPATH=src python3 tools/tm_from_ref.py data/shots/ref_27cards.jpg [输出目录]
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "data/shots/ref_27cards.jpg"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/templates_lab"
    img = cv2.cvtColor(cv2.imread(ref), cv2.COLOR_BGR2RGB)
    c = CDP()
    if not c.find_truth():
        print("没有真值钩子")
        return 2
    truth_raw = c.truth()
    truth = sorted(int(x) for x in (truth_raw.get("hands", {}).get("0") or []))
    print(f"参考图 {ref}  真值手牌 {len(truth)} 张: {' '.join(map(str, truth))}")
    y0, y1 = P.hand_band_measured(img)
    peaks = P.card_edges(img, y0, y1)
    print(f"图上手牌带 {(y0, y1)}  峰数 {len(peaks)}")
    if len(truth) != len(peaks):
        print(f"峰数({len(peaks)}) != 真值张数({len(truth)}) → 这次不采(等同一手牌时再跑)")
        return 3
    os.makedirs(out, exist_ok=True)
    for idx, z in enumerate(truth):
        x = peaks[idx]
        patch = img[y0 + 8:y1 - 8, x:x + 24]
        if patch.size == 0:
            continue
        f = os.path.join(out, f"{z}.npy")
        k = 2
        while os.path.exists(f):
            f = os.path.join(out, f"{z}_{k}.npy")
            k += 1
        np.save(f, patch.astype(np.uint8))
    print("已采集:", sorted(os.listdir(out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
