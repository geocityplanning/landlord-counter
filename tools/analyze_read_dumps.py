"""读牌帧留证分析: 对留证的帧跑三种独立读法, 判定"谁对"。

三种独立信号:
  1. n_est    —— 手牌块**实测宽度**反推 (源码布局 整排宽=(n-1)*24+88 居中)
  2. n_read   —— VLM 直接读牌张数 (离线复读, 可多跑几次看稳定性)
  3. n_edges  —— 手牌带**竖直边缘**计数 (卡与卡的边界线, 与上面两法独立)

判定: 两个信号一致者为真; 三法分歧 → 人工看帧。

用法: cd /project1/landlord-counter && PYTHONPATH=src python3 tools/analyze_read_dumps.py [目录]
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from landlord_counter.guandan import percept as P  # noqa: E402

DIR = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GUANDAN_READ_DUMP_DIR",
                                                      "/tmp/guandan_read_dumps")


def n_edges(img) -> int:
    """垂直边缘计数估张数: 卡边界线数 + 1(近似, 与块宽/VLM 独立)。"""
    y0, y1 = P.HAND_BAND
    band = img[y0:y1]
    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)).mean(axis=0)
    if gx.max() <= 0:
        return 0
    thr = 0.45 * float(gx.max())
    peaks: list = []
    for x in range(1, len(gx) - 1):
        if gx[x] > thr and gx[x] >= gx[x - 1] and gx[x] > gx[x + 1]:
            if not peaks or x - peaks[-1] >= 12:
                peaks.append(x)
    return len(peaks) + 1 if peaks else 0


def main() -> int:
    files = sorted(glob.glob(os.path.join(DIR, "*.json")))
    if not files:
        print(f"目录 {DIR} 里没有留证 JSON(说明运行期间没出现读牌分歧 = 好消息)")
        return 0
    rec = None
    try:
        from landlord_counter.config import load_config
        from landlord_counter.vision.card_recognizer import CardRecognizer

        rec = CardRecognizer(load_config().vision)
    except Exception as e:  # noqa: BLE001
        print(f"! VLM 不可用({e}), 只做块宽/边缘两法")
    print(f"{'时间':<16}{'标记':<12}{'块宽推':>6}{'VLM读':>6}{'边缘':>6}{'密度':>6}  判定")
    for jf in files:
        info = json.load(open(jf, encoding="utf-8"))
        png = jf[:-5] + ".png"
        if not os.path.exists(png):
            continue
        img = cv2.imread(png)
        n_est = P.hand_card_count_est(img)
        xl, xr = P.hand_block(img)
        dens = 0.0
        if xl is not None:
            y0, y1 = P.HAND_BAND
            sub = img[y0:y1, xl:xr + 1]
            dens = float((sub.min(axis=2) > 150).mean())
        n_read = info.get("n_read")
        if rec is not None:
            h = P.read_hand_ordered(rec, img, expected=n_est or 0)
            n_read = len(h) if h else 0
        ne = n_edges(img)
        votes = [v for v in (n_est, n_read, ne) if v]
        verdict = "—"
        if votes:
            from collections import Counter

            c = Counter(votes)
            top, cnt = c.most_common(1)[0]
            verdict = f"多为 {top} 张" if cnt >= 2 else "三法分歧(看帧)"
        print(f"{info.get('ts',''):<16}{info.get('tag',''):<12}{n_est:>6}{n_read if n_read is not None else -1:>6}"
              f"{ne:>6}{dens:>6.2f}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
