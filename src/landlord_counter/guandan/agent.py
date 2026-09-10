"""掼蛋托管 MVP（黑盒视觉版）: 轮到我→提示→出牌; 无解→不出。

判据(源码推导+实测): 仅当"轮到我且未过牌"时, 我方手牌(白卡)才被绘制 →
底部手牌带白卡存在 ⇒ 我的回合。
坐标实测(720x1280, dpr2): 提示(199,1119) 出牌(359,1119) 不出(519,1119); 开始游戏(359,942)
"""
from __future__ import annotations

import subprocess
import sys
import time

import cv2
import numpy as np

ADB = ["adb", "-s", "127.0.0.1:5555"]
BTN_HINT = (199, 1119)
BTN_PLAY = (359, 1119)
BTN_PASS = (519, 1119)
BTN_START = (359, 942)
HAND_BAND = (805, 945)  # y0,y1
WHITE_MIN = 20000  # 手牌带白卡像素阈值


def tap(x, y, wait=1.0):
    subprocess.run(ADB + ["shell", "input", "tap", str(x), str(y)], capture_output=True)
    time.sleep(wait)


def snap():
    r = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    arr = np.frombuffer(r.stdout, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def white_count(img) -> int:
    y0, y1 = HAND_BAND
    band = img[y0:y1, :, :]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    return int(((b > 200) & (g > 200) & (r > 200)).sum())


def gold_big(img) -> bool:
    """大金钮(开始/再来一局)存在? 中心区域金色占比"""
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    gold = (r > 140) & (r < 215) & (g > 110) & (g < 185) & (b < 90)
    c = gold[850:1050, 60:660]
    return c.mean() > 0.25


def selection_up(img) -> int:
    """提示后是否选中了牌: 选中牌上移18CSS=36设备px → 手牌带上沿之上出现白卡"""
    band = img[770:812, :, :]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    return int(((b > 200) & (g > 200) & (r > 200)).sum())


def main() -> int:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    t_end = time.time() + dur
    plays = passes = 0
    print("▶ 掼蛋托管MVP启动(v2: 无解自动不出)", flush=True)
    while time.time() < t_end:
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        if gold_big(img):  # 开始/再来一局
            print("[开始] 点大金钮", flush=True)
            tap(*BTN_START, wait=3.0)
            continue
        wc = white_count(img)
        if wc < WHITE_MIN:  # 非我回合
            time.sleep(0.8)
            continue
        # 我回合: 提示 → 判断是否选中
        tap(*BTN_HINT, wait=1.5)
        img2 = snap()
        if img2 is None:
            continue
        if selection_up(img2) > 800:  # 有选中 → 出牌
            tap(*BTN_PLAY, wait=2.2)
            plays += 1
            print(f"  ✓ 出牌 (累计出牌{plays} 不出{passes})", flush=True)
        else:  # 无解 → 不出
            tap(*BTN_PASS, wait=2.0)
            passes += 1
            print(f"  → 不出 (累计出牌{plays} 不出{passes})", flush=True)
        time.sleep(0.8)
        # 进度自检: 手牌白卡未变且仍我回合 → 下一轮换动作
        img3 = snap()
        if img3 is not None and white_count(img3) >= WHITE_MIN:
            wc2 = white_count(img3)
            if abs(wc2 - wc) < 300:  # 无变化
                print("  ! 疑似无进展, 尝试另一动作", flush=True)
                tap(*BTN_PASS, wait=1.8)
                tap(*BTN_PLAY, wait=2.0)
    print(f"▶ 结束: 出牌{plays} 不出{passes}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
