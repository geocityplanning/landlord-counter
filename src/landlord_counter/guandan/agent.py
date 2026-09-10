"""掼蛋托管 MVP（黑盒视觉版）: 轮到我→提示→出牌; 无解→不出。

判据(源码推导+实测): 仅当"轮到我且未过牌"时, 我方手牌(白卡)才被绘制 →
底部手牌带白卡存在 ⇒ 我的回合。
坐标实测(720x1280, dpr2): 提示(199,1119) 出牌(359,1119) 不出(519,1119); 开始游戏(359,942)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2
import numpy as np

from . import ai as AI
from . import percept as P
from . import rules as R
from .percept import card_tap_x

ADB = ["adb", "-s", "127.0.0.1:5555"]
BTN_HINT = (199, 1119)
BTN_PLAY = (359, 1119)
BTN_PASS = (519, 1119)
BTN_START = (359, 942)
HAND_BAND = (805, 945)  # y0,y1
WHITE_MIN = 4000  # 手牌带白卡像素阈值(27张≈66k, 15张≈42k, 8张≈19k → 取4k, 非我回合时≈0)


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


def gold_button(img):
    """找大金钮(开始游戏/再接一局): 金色块 w>250 h>50, y∈[600,1100]。返回中心或 None。"""
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    gold = ((r > 140) & (r < 215) & (g > 110) & (g < 185) & (b < 90)).astype(np.uint8) * 255
    n, lab, stats, cent = cv2.connectedComponentsWithStats(gold, 8)
    best = None
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if w > 250 and h > 50 and 600 <= y <= 1100:
            if best is None or a > best[4]:
                best = (x, y, w, h, a, int(cent[i][0]), int(cent[i][1]))
    return (best[5], best[6]) if best else None


def selection_up(img) -> int:
    """提示后是否选中了牌: 选中牌上移18CSS=36设备px → 手牌带上沿之上出现白卡"""
    band = img[770:812, :, :]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    return int(((b > 200) & (g > 200) & (r > 200)).sum())


JIPAI = int(os.getenv("GUANDAN_JIPAI", "2"))  # 本局级牌(默认打2)
OURS = os.getenv("GUANDAN_OURS", "0") == "1"  # 自研决策模式


def map_indices(hand, cards) -> list[int] | None:
    """把决策选中的 Card 列表映射回手牌(左→右)下标; 失败 None。"""
    used: set[int] = set()
    out: list[int] = []
    for c in cards:
        hit = None
        for i, h in enumerate(hand):
            if i in used:
                continue
            if h.zhi == c.zhi and (h.hua == c.hua or c.hua == 4 or h.hua == 4):
                hit = i
                break
        if hit is None:
            for i, h in enumerate(hand):
                if i not in used and h.zhi == c.zhi:
                    hit = i
                    break
        if hit is None:
            return None
        used.add(hit)
        out.append(hit)
    return sorted(out)


def ours_decide(img, rec) -> str:
    """自研决策: 读手牌+桌面 → rules/ai 决策 → 点选执行。
    返回 'play'|'pass'|'fallback'(回落提示钮)。"""
    hand = P.read_hand_ordered(rec, img)
    if not hand:
        print("  [ours] 手牌读取失败 → 回落", flush=True)
        return "fallback"
    last_cards = P.read_table_last(rec, img)
    if last_cards is None:
        print("  [ours] 桌面读取失败 → 回落", flush=True)
        return "fallback"
    st = AI.GameState()
    st.jipai = JIPAI
    last = R.identify(last_cards, JIPAI) if last_cards else None
    choice = AI.choose_play(hand, last, st)
    if choice is None or getattr(choice, "is_invalid", False):
        print(f"  [ours] 决策=不出 (手牌{len(hand)}张, 待压={R.cards_to_str(last_cards) if last_cards else '无'})", flush=True)
        return "pass"
    idxs = map_indices(hand, choice.cards)
    if idxs is None:
        print("  [ours] 选牌映射失败 → 回落", flush=True)
        return "fallback"
    print(
        f"  [ours] 决策={R.group_to_str(choice)} idx={idxs} (手牌{len(hand)}, 压={R.cards_to_str(last_cards) if last_cards else '领出'})",
        flush=True,
    )
    for i in idxs:
        tap(card_tap_x(i), 875, wait=0.18)
    tap(*BTN_PLAY, wait=2.2)
    # 执行回执: 手牌白卡应下降(或回合结束)
    img2 = snap()
    if img2 is not None:
        w_before, w_after = P.white_count(img), P.white_count(img2)
        if w_after >= P.WHITE_TURN_MIN and abs(w_after - w_before) < 300:
            print(f"  [ours] ✗ 出牌未生效(w {w_before}→{w_after}) → 回落提示钮", flush=True)
            return "fallback"
    return "play"


def main() -> int:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    t_end = time.time() + dur
    plays = passes = 0
    rec = None
    if OURS:
        from ..config import load_config
        from ..vision.card_recognizer import CardRecognizer

        rec = CardRecognizer(load_config().vision)
        print("▶ 自研决策模式(OURS=1): rules+ai 接管, 失败回落提示钮", flush=True)
    print("▶ 掼蛋托管MVP启动(v2: 无解自动不出)", flush=True)
    while time.time() < t_end:
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        gb = gold_button(img)
        if gb:  # 开始游戏 / 结算页"再接一局"
            print(f"[按钮] 点大金钮@{gb}", flush=True)
            tap(gb[0], gb[1], wait=3.0)
            continue
        wc = white_count(img)
        if wc < WHITE_MIN:  # 非我回合
            time.sleep(0.8)
            continue
        # 我回合
        if OURS:
            r = ours_decide(img, rec)
            if r == "pass":
                tap(*BTN_PASS, wait=2.0)
                passes += 1
                print(f"  → 不出(ours) (出牌{plays} 不出{passes})", flush=True)
                continue
            if r == "play":
                plays += 1
                print(f"  ✓ 出牌(ours) (出牌{plays} 不出{passes})", flush=True)
                time.sleep(1.0)
                continue
            # fallback → 走提示钮
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
