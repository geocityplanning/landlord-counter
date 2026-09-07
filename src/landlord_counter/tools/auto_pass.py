"""自动托管 v1（pass-only，像素色块定位，零 OCR）——坐标/颜色来自 wishday 源码几何。

按钮几何(1280x720): 按钮行 y=144..274(中心~209)
  叫分/不出=灰 #616161(左起第1个); 提示=蓝#1976D2; 出牌=绿#388E3C
  再来一局(结算屏)=绿 #388E3C 大钮 x440-840 y450-570 中心(640,510)
驱动策略(v0 只托管"不叫/不出/再来一局")。

用法: uv run python -m landlord_counter.tools.auto_pass [秒数]
"""
from __future__ import annotations

import subprocess
import sys
import time

import cv2
import numpy as np

SERIAL = "127.0.0.1:5555"

GREY = (0x61, 0x61, 0x61)     # 不叫/不出
GREEN = (0x38, 0x8E, 0x3C)    # 出牌/再来一局/难度卡


def adb(*a):
    subprocess.run(["adb", "-s", SERIAL, *a], capture_output=True)


def snap() -> np.ndarray | None:
    try:
        r = subprocess.run(["adb", "-s", SERIAL, "exec-out", "screencap", "-p"],
                           capture_output=True, timeout=20)
        img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def mask_blobs(img, color, tol, y0, y1, min_w=80, min_h=60):
    """在 y0..y1 行内找指定颜色的连通块, 返回 [(cx, cy, w, h)], 按 x 排序。"""
    bgr = np.array(color[::-1], dtype=np.int16)  # to BGR
    band = img[y0:y1, :]
    m = (np.abs(band.astype(np.int16) - bgr).sum(axis=2) <= tol * 3).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w >= min_w and h >= min_h:
            out.append((x + w // 2, y0 + y + h // 2, w, h))
    return sorted(out)


def main() -> None:
    limit = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    t0 = time.time()
    n_pass = n_restart = n_play = 0
    last_action = 0.0
    print("▶ auto_pass v1(色块定位) 启动")
    while time.time() - t0 < limit:
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        h, w = img.shape[:2]
        acted = False
        # 1) 结算屏"再来一局"(绿色大钮, y>400) — 点击进入下一局
        for cx, cy, bw, bh in mask_blobs(img, GREEN, 35, 400, min(h - 1, 700), min_w=250, min_h=80):
            if cy > 400 and bh > 80:
                adb("shell", "input", "tap", str(cx), str(cy))
                n_restart += 1
                print(f"[{time.time()-t0:5.0f}s] 点『再来一局』@({cx},{cy})")
                acted = True
                break
        # 2) 叫分/出牌行: 灰块=不叫/不出(左起第一个)
        if not acted:
            blobs = mask_blobs(img, GREY, 30, 120, 300, min_w=100, min_h=60)
            if blobs:
                cx, cy, bw, bh = blobs[0]
                adb("shell", "input", "tap", str(cx), str(cy + 10))
                n_pass += 1
                print(f"[{time.time()-t0:5.0f}s] 点灰钮(不叫/不出)@({cx},{cy}) w{bw}")
                acted = True
            else:
                # 3) 出牌轮但我先手(无灰块=必出): 不托管(v0), 记录待 M2
                green_play = mask_blobs(img, GREEN, 35, 120, 300, min_w=150, min_h=60)
                if green_play:
                    n_play += 1
        if acted:
            last_action = time.time()
        time.sleep(1.4)
    print(f"■ 结束: 灰钮(不叫/不出)×{n_pass}  再来一局×{n_restart}  遇必出轮×{n_play}")


if __name__ == "__main__":
    main()
