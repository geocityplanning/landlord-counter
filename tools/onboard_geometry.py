#!/usr/bin/env python3
"""新游戏接入: 几何扫描器 — 给一张云手机截图, 输出标定报告(行剖面/色块/候选按钮行)。

用途: 接入一款新游戏时, 先跑本工具得到"手牌带/按钮行/配色"的初值, 再人工确认。
用法: python3 tools/onboard_geometry.py [截图路径]   # 不给路径则现场 adb 截屏
"""
from __future__ import annotations

import subprocess
import sys
from collections import Counter

import cv2
import numpy as np


def grab() -> np.ndarray:
    raw = subprocess.run(["adb", "-s", "127.0.0.1:5555", "exec-out", "screencap", "-p"],
                         capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def main() -> int:
    if len(sys.argv) > 1:
        img = cv2.imread(sys.argv[1])
    else:
        img = grab()
    if img is None:
        print("无法获取截图")
        return 1
    h, w = img.shape[:2]
    cv2.imwrite("/tmp/onboard_frame.png", img)
    print(f"■ 截图 {w}x{h} (已存 /tmp/onboard_frame.png)")
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    white = (b > 200) & (g > 200) & (r > 200)

    print("\n■ 行剖面(每 40px): 白像素 / 主色")
    for y in range(0, h, 40):
        seg = img[y:y + 40]
        wp = int(white[y:y + 40].sum())
        mean = seg.reshape(-1, 3).mean(axis=0).round(0)
        bar = "#" * min(50, wp // 800)
        print(f"  y{y:4d}-{y+40:4d}: 白{wp:6d} 均值BGR{mean} {bar}")

    print("\n■ 主要颜色(整图量化, 前 8)")
    q = (img // 32 * 32).reshape(-1, 3)
    for c, n in Counter(map(tuple, q)).most_common(8):
        pct = 100 * n / (w * h)
        print(f"  BGR{c} {pct:5.1f}%")

    print("\n■ 候选'按钮行'(横向成排的纯色块): 用阈值找 5 类常见按钮色")
    for name, bgr, tol in [("灰(禁用/不出)", (0x61, 0x61, 0x61), 30), ("绿(确认/出牌)", (0x38, 0x8E, 0x3C), 35),
                           ("蓝(提示/次要)", (0x19, 0x76, 0xD2), 35), ("红(危险/3分)", (0xD3, 0x2F, 0x2F), 35),
                           ("金(开始/主钮)", (0x20, 0x9A, 0xC0), 40)]:
        lower = np.array([max(0, c - tol) for c in bgr], np.uint8)
        upper = np.array([min(255, c + tol) for c in bgr], np.uint8)
        mask = cv2.inRange(img, lower, upper)
        n, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
        hits = [(int(stats[i][4]), tuple(stats[i][:4])) for i in range(1, n) if stats[i][4] > 3000]
        if hits:
            hits.sort(reverse=True)
            print(f"  {name}: " + "; ".join(f"area={a} box={box}" for a, box in hits[:3]))

    print("\n■ 提示: 手牌带通常是某个 120-180px 高的白像素密集横条; 按钮行在其下方 60-200px。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
