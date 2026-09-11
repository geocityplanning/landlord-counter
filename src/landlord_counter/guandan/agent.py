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


PROMPT_SETTLE = (
    "这是掼蛋结算弹窗。只回答两行: 头游=<谁(我方是南/北, 对手是西/东)>; 我方是否升级=<是/否>。不要解释。"
)


def read_settle(rec, img):
    """读结算弹窗 → (raw_text, win_bool_or_None)"""
    roi = img[300:900, 30:690]
    txt = rec.recognize_with_vlm(roi, PROMPT_SETTLE) or ""
    win = None
    if "头游" in txt:
        if any(k in txt for k in ("南", "北", "你", "队友")):
            win = True
        elif any(k in txt for k in ("西", "东")):
            win = False
    return txt, win


def _stats_append(path: str, row: str) -> None:
    try:
        with open(path, "a") as fo:
            fo.write(row + "\n")
    except Exception:  # noqa: BLE001
        pass


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
_LAST_SIG = ""   # 上次决策签名(防重复空转)
_SAME_SIG_N = 0


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
    global _LAST_SIG, _SAME_SIG_N
    # 像素数牌(已滤噪) 作为期望张数喂给识别
    n_vis = P.hand_columns(img)
    hand = P.read_hand_ordered(rec, img, expected=n_vis)
    if not hand:  # 读失败 → 重新取帧再读一次(VLM 偶发空返回)
        img2 = snap()
        if img2 is not None:
            n_vis = P.hand_columns(img2) or n_vis
            hand = P.read_hand_ordered(rec, img2, expected=n_vis)
            if hand:
                img = img2
    if not hand:
        print("  [ours] 手牌读取失败 → 回落", flush=True)
        return "fallback"
    # 读数一致性: 与像素数牌差 >1 → 用期望值重读一次
    if n_vis and abs(n_vis - len(hand)) > 1:
        print(f"  [ours] 读数{len(hand)}张 vs 像素{n_vis}张 → 重读", flush=True)
        hand2 = P.read_hand_ordered(rec, img, expected=n_vis)
        if hand2 and abs(len(hand2) - n_vis) <= 1:
            hand = hand2
        else:
            print("  [ours] 重读后仍不一致 → 回落", flush=True)
            return "fallback"
    last_cards = P.read_table_last(rec, img)
    if last_cards is None:
        print("  [ours] 桌面读取失败 → 回落", flush=True)
        return "fallback"
    # 牌型合法性闸门: 读到的"待压牌"必须能识别成合法牌型, 否则视为误读
    if last_cards:
        gl = R.identify(last_cards, JIPAI)
        if getattr(gl, "is_invalid", False):
            print(f"  [ours] 待压牌型非法(误读): {R.cards_to_str(last_cards)} → 回落", flush=True)
            return "fallback"
    st = AI.GameState()
    st.jipai = JIPAI
    # 队友判定: 主循环跟踪"刚出牌的那一家"(座位块变化) → top=北=我方队友
    st.shi_dui_you = _LAST_SEAT.get("who") == "top"
    last = R.identify(last_cards, JIPAI) if last_cards else None
    if last_cards:
        print(f"  [ours] 上家={'队友(北)' if st.shi_dui_you else _LAST_SEAT.get('who') or '未知'}", flush=True)
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
    # 执行策略: 跟牌(压牌)一律"提示选牌执行"; 领出 ≥3 张也走提示; 仅"领出 1-2 张"直选
    follow = bool(last_cards)
    if len(idxs) >= 3 or follow:
        tag = "跟牌" if follow else f"多张({len(idxs)})"
        print(f"  [ours] {tag} → 提示选牌执行", flush=True)
        tap(*BTN_HINT, wait=1.6)
        iv2 = snap()
        if iv2 is None:
            return "fallback"
        lift = P.lifted_px(iv2)
        est = round(lift / 1460) if lift > 500 else 0
        if est == 0:
            print("  [ours] 提示无可出 → 不出", flush=True)
            return "pass"
        if not follow and abs(est - len(idxs)) > max(1, len(idxs) // 2):
            print(f"  [ours] ✗ 提示选牌张数{est} ≠ 决策{len(idxs)} → 回落", flush=True)
            return "fallback"
        tap(*BTN_PLAY, wait=1.6)
        w_before = P.white_count(img)
        for _ in range(8):
            time.sleep(0.4)
            i2 = snap()
            if i2 is None:
                continue
            if not P.my_turn(i2):
                return "play"
            if P.white_count(i2) < w_before - 1500:
                return "play"
        print("  [ours] ✗ 提示执行未生效 → 回落", flush=True)
        return "fallback"

    sig = f"{R.group_to_str(choice)}|{len(hand)}|{R.cards_to_str(last_cards) if last_cards else '-'}"
    if sig == _LAST_SIG:
        _SAME_SIG_N += 1
        if _SAME_SIG_N >= 2:  # 同一决策重复出现(上次未生效) → 熔断, 回落提示钮
            print(f"  [ours] ↻ 决策重复({_SAME_SIG_N}) → 熔断回落提示钮", flush=True)
            return "fallback"
    else:
        _LAST_SIG, _SAME_SIG_N = sig, 0
    for attempt in range(2):   # 直选最多两轮: 第二轮重新取帧重选重出
        if attempt:
            print("  [ours] ↻ 直选重试(重新取帧)", flush=True)
            time.sleep(1.0)
        miss = False
        for i in idxs:
            if not _tap_card_verified(i, len(hand)):
                miss = True
                break
        if miss:
            print("  [ours] ✗ 点选不中(扫点仍无抬起) → 清选", flush=True)
            for j in idxs:  # 清掉可能已选中的牌
                tap(card_tap_x(j, len(hand)), 875, wait=0.15)
            continue
        # 选牌校验: 抬起亮带 ≈ 选中张数 × ~1460px(实测5张=7316)
        time.sleep(0.5)
        iv = snap()
        if iv is not None:
            lift = P.lifted_px(iv)
            est = round(lift / 1460) if lift > 500 else 0
            if est == 0 or (not follow and abs(est - len(idxs)) > max(1, len(idxs) // 2)):
                print(f"  [ours] ✗ 选牌校验失败(抬起≈{est}张/{lift}px vs 决策{len(idxs)}张) → 清选", flush=True)
                for i in idxs:  # 再点一遍取消选中
                    tap(card_tap_x(i, len(hand)), 875, wait=0.15)
                continue
        w_before = P.white_count(img)
        tap(*BTN_PLAY, wait=1.6)
        # 执行回执(强): 轮询3秒 — 手牌白卡须明显下降, 或回合已交出(手牌带消失)
        for _ in range(8):
            time.sleep(0.4)
            i2 = snap()
            if i2 is None:
                continue
            if not P.my_turn(i2):
                return "play"  # 回合已交出 → 成功
            if P.white_count(i2) < w_before - 1500:
                return "play"  # 手牌减少 → 成功
        # 未生效 → 补点一次出牌(可能按钮点击丢失/动画未落定), 再判
        print("  [ours] ↻ 出牌未生效 → 补点一次", flush=True)
        tap(*BTN_PLAY, wait=1.6)
        for _ in range(6):
            time.sleep(0.4)
            i2 = snap()
            if i2 is None:
                continue
            if not P.my_turn(i2):
                return "play"
            if P.white_count(i2) < w_before - 1500:
                return "play"
        # 清选, 进入下一轮重试
        for i in idxs:
            tap(card_tap_x(i, len(hand)), 875, wait=0.15)
        print(f"  [ours] ↻ 出牌仍未生效(w_before={w_before})", flush=True)
    print("  [ours] ✗ 直选两轮均未生效 → 回落提示钮", flush=True)
    return "fallback"


def _tap_card_verified(i: int, n: int) -> bool:
    """点选第 i 张并验证抬起; 抬起≈0 时左右扫点(小牌量牌位会漂移)。"""
    base = card_tap_x(i, n)
    for dx in (0, 8, -8, 16, -16):
        tap(base + dx, 875, wait=0.30)
        iv = snap()
        if iv is not None and P.lifted_px(iv) > 900:
            return True
    return False


def _lazy_rec():
    """按需创建识别器(统计模式需要, 非 OURS 模式也适用)"""
    try:
        from ..config import load_config
        from ..vision.card_recognizer import CardRecognizer

        return CardRecognizer(load_config().vision)
    except Exception:  # noqa: BLE001
        return None


_LAST_SEAT = {"who": None, "blocks": {}}


def _track_last_seat(img) -> None:
    """跟踪"刚出牌的那一家": 对比相邻帧各座位牌块(纯CV, 无VLM)。
    块变了/新出现 → 该座位刚出牌; 全部消失(新一轮) → 归为未知。"""
    cur = P.blocks_by_seat(img)
    changed = None
    for name, box in cur.items():
        pb = _LAST_SEAT["blocks"].get(name)
        if pb is None or abs(box[0] - pb[0]) + abs(box[1] - pb[1]) > 10:
            changed = name
    if changed:
        _LAST_SEAT["who"] = changed
    elif not cur and _LAST_SEAT["blocks"]:
        _LAST_SEAT["who"] = None      # 桌面清空 = 新一轮开始, 谁领出未知
    _LAST_SEAT["blocks"] = cur


def _recover_page(tag: str = "") -> None:
    """看门狗自愈: 强制重开浏览器页面并回到对局/开始页"""
    print(f"[看门狗] 页面疑似卡死({tag}) → 重开浏览器", flush=True)
    subprocess.run(ADB + ["shell", "am", "force-stop", "org.mozilla.focus"], capture_output=True)
    time.sleep(2)
    subprocess.run(
        ADB + ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "http://172.18.0.1:8123/index.html"],
        capture_output=True,
    )
    time.sleep(12)
    for _ in range(6):
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        gb = gold_button(img)
        if gb:
            tap(gb[0], gb[1], wait=3.0)
            continue
        break
    print("[看门狗] 重开完成", flush=True)


def main() -> int:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    t_end = time.time() + dur
    plays = passes = 0
    deals = 0
    last_prog = time.time()  # 看门狗: 最近进展时刻
    last_wc = -1
    rec = None
    if OURS or os.getenv("STATS_FILE"):
        from ..config import load_config
        from ..vision.card_recognizer import CardRecognizer

        rec = CardRecognizer(load_config().vision)
    if OURS:
        print("▶ 自研决策模式(OURS=1): rules+ai 接管, 失败回落提示钮", flush=True)
    print("▶ 掼蛋托管MVP启动(v2: 无解自动不出)", flush=True)
    while time.time() < t_end:
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        _track_last_seat(img)   # 跟踪"刚出牌的那一家"(供队友判定)
        # 看门狗: 3 分钟无任何进展(无大金钮/无我方回合动作/手牌无变化) → 重开页面自愈
        wc_now = white_count(img)
        if wc_now != last_wc:
            last_wc = wc_now
            last_prog = time.time()
        if time.time() - last_prog > 240:
            _recover_page(f"{int(time.time() - last_prog)}s 无进展")
            last_prog = time.time()
            last_wc = -1
            continue
        gb = gold_button(img)
        if gb:  # 开始游戏 / 结算页"再接一局"
            last_prog = time.time()
            _LAST_SEAT["who"] = None      # 新一局: 清空上家跟踪
            _LAST_SEAT["blocks"] = {}
            sf = os.getenv("STATS_FILE")
            if sf:
                r = rec if rec is not None else _lazy_rec()
                if r is not None:
                    raw, win = read_settle(r, img)
                    deals += 1
                    _stats_append(sf, f"{int(time.time())},{deals},{'win' if win else ('lose' if win is False else '?')},{os.getenv('STATS_TAG','-')},{raw.strip()[:60]}")
                    print(f"[统计] 第{deals}局: {'我方升级' if win else ('对手升级' if win is False else '未判定')} | {raw.strip()[:40]!r}", flush=True)
            print(f"[按钮] 点大金钮@{gb}", flush=True)
            tap(gb[0], gb[1], wait=3.0)
            continue
        wc = white_count(img)
        if wc < WHITE_MIN or not P.play_button_active(img):  # 非我回合(残局手牌仍显示但按钮禁用)
            time.sleep(0.8)
            continue
        # 我回合
        last_prog = time.time()
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
