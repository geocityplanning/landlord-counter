"""自动托管 v1：真·出牌（决策+点击全自动），驱动 wishday 完整对局。

感知/几何(全部来自 wishday 源码, 1280x720):
  按钮行   y144..274   灰=不叫/不出  绿=出牌  蓝=提示  橙/红=2/3分
  结算    绿大钮 (440..840, 450..570) = 再来一局
  牌堆区   电脑B(左) cx=0.30W,cy=0.38H | 我 cx=0.50W,cy=0.38H+50 | 电脑A(右) cx=0.70W
  mini卡  119x166.6 间距61.2
  手牌    卡136x195.5, 升序, startX=(1280-(sp*(n-1)+136))/2, sp=(1216-136)/(n-1)夹[47.6,122.4]
          点选 y≈580
流程: 结算→再来一局 | 叫分→策略 | 出牌轮→(领打/跟牌) bot决策→点选→绿钮
"""
from __future__ import annotations

import re
import time

import cv2
import numpy as np

from landlord_counter.config import load_config
from landlord_counter.logic import ddz_engine as E
from landlord_counter.logic import bot
from landlord_counter.tools.auto_pass import GREEN, GREY, adb, mask_blobs, snap
from landlord_counter.vision.card_recognizer import CardRecognizer

# ---- 几何常量(源码推导, 1280x720) ----
CARD_W, CARD_H = 136.0, 195.5
HAND_AVAIL = 1216.0
HAND_Y = 580
TABLE_CROP = {"L": (150, 200, 610, 350), "R": (670, 200, 1130, 350)}  # 电脑B/A 牌堆带(mini卡 y190..357)
ZONES = ("L", "R")
PROMPT_PLAYED = (
    "这是斗地主桌面上某一玩家刚打出的牌堆, 牌面朝上(白底, 左上角有点数)。"
    "请只列出点数, 从小到大, 空格分隔, 不要花色符号; 王写 小 或 大; "
    "若该区域没有任何扑克牌则只回答: 无"
)


def parse_ranks(text: str) -> list[int]:
    """VLM 文本 → rank 列表(升序)。容忍 小王/大王/王。"""
    t = text.replace("小王", "小").replace("大王", "大").replace(" ", "")
    toks = []
    i = 0
    while i < len(t):
        if t[i] in "大小":
            toks.append(16 if t[i] == "小" else 17)
            i += 1
        elif t[i] == "1" and i + 1 < len(t) and t[i + 1] == "0":
            toks.append(10)
            i += 2
        elif t[i] in "JQKA" or t[i].isdigit():
            toks.append(E.token_to_rank(t[i]))
            i += 1
        else:
            i += 1
    return sorted(toks)


class AutoPlay:
    def __init__(self, rec: CardRecognizer):
        self.rec = rec
        self.zone_sig: dict[str, bytes | None] = {}
        self.zone_ts: dict[str, float] = {z: 0.0 for z in ZONES}
        self.n_actions = 0
        self.last_zone_key: bytes | None = None
        self.zone_acted = False

    # ---------- 相位 & 动作检测 ----------
    def button_row(self, img) -> dict:
        """返回按钮行内的块: grey/green 及其中心。min_w=200 过滤细噪声(实测按钮宽340)."""
        grey = mask_blobs(img, GREY, 30, 120, 300, 200, 60)
        green = mask_blobs(img, GREEN, 35, 120, 300, 150, 60)
        out = {"grey": grey[0] if grey else None}
        out["green"] = min(green, key=lambda b: b[2]) if green else None
        return out

    def result_screen(self, img):
        """结算屏=再来一局(绿大钮)+返回主界面(蓝大钮)同现。防主界面'普通'绿钮误判。"""
        g = mask_blobs(img, GREEN, 35, 380, 700, 250, 60)
        b = mask_blobs(img, BLUE, 25, 380, 700, 250, 60)
        if not g or not b:
            return None
        return g[0]

    def grey_loose(self, img):
        """宽松灰检测: #616161±30 或按压色 #424242±20, 宽≥150。"""
        b = mask_blobs(img, GREY, 30, 120, 300, 150, 60)
        if b:
            return b[0]
        b = mask_blobs(img, (0x42, 0x42, 0x42), 20, 120, 300, 150, 60)
        return b[0] if b else None

    # ---------- 牌堆区跟踪 ----------
    def _color_blocks(self, img, colors, tol, y0=120, y1=300, min_w=80, min_h=50):
        import numpy as np

        band = img[y0:y1, :]
        m = np.zeros(band.shape[:2], np.uint8)
        for c in colors:
            bgr = np.array(c[::-1], dtype=np.int16)
            sub = np.abs(band.astype(np.int16) - bgr).sum(axis=2) <= tol * 3
            m[sub] = 255
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if w >= min_w and h >= min_h:
                out.append((x + w // 2, y0 + y + h // 2, w, h))
        return sorted(out)
    def _sig(self, img, zone):
        x0, y0, x1, y1 = TABLE_CROP[zone]
        small = cv2.resize(img[y0:y1, x0:x1], (48, 22))
        return cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).tobytes()

    def update_zones(self, img):
        for z in ZONES:
            s = self._sig(img, z)
            if s != self.zone_sig.get(z):
                self.zone_sig[z] = s
                self.zone_ts[z] = time.time()

    def last_played_zone(self, img) -> str | None:
        self.update_zones(img)
        now = time.time()
        recent = {z: t for z, t in self.zone_ts.items() if now - t < 15.0}
        return max(recent, key=recent.get) if recent else None

    def read_zone_cards(self, img, zone) -> list[int]:
        x0, y0, x1, y1 = TABLE_CROP[zone]
        crop = img[y0:y1, x0:x1]
        crop = cv2.resize(crop, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
        text = self.rec.recognize_with_vlm(crop, PROMPT_PLAYED) or ""
        return parse_ranks(text)

    # ---------- 点击 ----------
    def play(self, img, action: E.Group, hand: list[int]):
        """点选 action.ranks 对应的手牌位置并点出牌。hand=当前完整手牌(升序)."""
        # action.ranks 每张在手牌中从低到高取位; 注意同rank多张: 逐张从低索引取
        used: dict[int, int] = {}
        pos: list[int] = []
        for r in action.ranks:
            k = used.get(r, 0)
            found = -1
            cnt = 0
            for i, h in enumerate(hand):
                if h != r:
                    continue
                if cnt == k:
                    found = i
                    break
                cnt += 1
            if found < 0:
                return False
            used[r] = k + 1
            pos.append(found)
        pos.sort()
        sp = min(max((HAND_AVAIL - CARD_W) / max(len(hand) - 1, 1), CARD_W * 0.35), CARD_W * 0.90)
        start_x = (1280.0 - (sp * (len(hand) - 1) + CARD_W)) / 2
        for i in pos:
            # 关键: 卡重叠(间距67 < 卡宽136), 点卡左可见带而非中心(中心被右邻卡覆盖)
            x = int(start_x + i * sp + sp * 0.5)
            adb("shell", "input", "tap", str(x), str(HAND_Y))
            time.sleep(0.16)
        # 点"出牌"(绿钮)
        btns = self.button_row(img)
        if btns["green"]:
            adb("shell", "input", "tap", str(btns["green"][0]), str(btns["green"][1]))
            return True
        return False


BLUE = (0x19, 0x76, 0xD2)


BID_COLORS_ALL = [(0x61, 0x61, 0x61), (0x19, 0x76, 0xD2), (0xF5, 0x7C, 0x00), (0xD3, 0x2F, 0x2F)]


def remove_all(hand: list[int], ranks: list[int]):
    for r in ranks:
        if r in hand:
            hand.remove(r)


def my_turn(ap: "AutoPlay", img) -> bool:
    row = ap.button_row(img)
    return row["grey"] is not None or row["green"] is not None


def play_via_hint(ap: "AutoPlay") -> str:
    """点提示(自动选牌)→点出牌。返回 'ok'|'pass'|'fail'。"""
    for _ in range(2):
        img = snap()
        if img is None:
            return "fail"
        blue = mask_blobs(img, BLUE, 25, 120, 300, 120, 50)
        if not blue:
            return "fail"
        adb("shell", "input", "tap", str(blue[0][0]), str(blue[0][1]))
        time.sleep(1.0)
        img2 = snap()
        if img2 is None:
            return "fail"
        btns = ap.button_row(img2)
        if not btns["green"]:
            return "fail"
        adb("shell", "input", "tap", str(btns["green"][0]), str(btns["green"][1]))
        time.sleep(1.8)
        img3 = snap()
        if img3 is None:
            return "fail"
        if not my_turn(ap, img3):
            return "ok"
    return "fail"


def hint_fallback(ap: "AutoPlay") -> bool:
    """点"提示"(游戏自动选牌)再点出牌。返回是否已出成功。"""
    img = snap()
    if img is None:
        return False
    blue = mask_blobs(img, BLUE, 25, 120, 300, 120, 50)
    if not blue:
        return False
    adb("shell", "input", "tap", str(blue[0][0]), str(blue[0][1]))
    time.sleep(1.0)
    img2 = snap()
    if img2 is None:
        return False
    btns = ap.button_row(img2)
    if btns["green"]:
        adb("shell", "input", "tap", str(btns["green"][0]), str(btns["green"][1]))
        time.sleep(1.7)
        img3 = snap()
        return img3 is not None and not my_turn(ap, img3)
    return False


def main():
    cfg = load_config()
    rec = CardRecognizer(cfg.vision)
    ap = AutoPlay(rec)
    hand: list[int] = []  # 当前手牌 belief(升序), 由发牌投票/出牌自减维护
    last_hand_len = -1
    print("▶ auto_play 启动 (完整托管 v1)")
    while True:
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        # 0) 结算: 再来一局
        btn = ap.result_screen(img)
        if btn:
            adb("shell", "input", "tap", str(btn[0]), str(btn[1]))
            print("[结算] 点再来一局, 等新发牌…")
            time.sleep(2)
            continue
        row = ap.button_row(img)
        grey, green = row["grey"], row["green"]
        if not grey and not green:
            ap.update_zones(img)  # 机器人回合: 只跟踪牌堆变化
            time.sleep(0.8)
            continue
        # 1) 叫分轮(无绿=只有叫分按钮)
        if not green:
            if hand:  # 上一局残念 → 新局重置
                hand = []
            if not hand:  # 新局: 发牌已展示, 读一次建立 belief
                ranks = rec.read_hand_vlm(img)
                if ranks:
                    hand = sorted(E.token_to_rank(t) for t in ranks)
                    print(f"[新局] 屏读 hand={[E.rank_to_token(r) for r in hand]}")
            score = bot.decide_bid(hand)
            # 不叫=灰钮(单色, 恒最左); 3分=红钮(单色, 最右)。禁用多色union(相邻钮会桥接成巨块)
            score = bot.decide_bid(hand)
            target, label = grey, "不叫"
            if score > 0:
                reds = ap._color_blocks(img, [(0xD3, 0x2F, 0x2F)], 35, min_w=220, min_h=100)
                if reds:
                    target, label = reds[-1], f"叫 {score}分"
            if target:
                adb("shell", "input", "tap", str(target[0]), str(target[1]))
                print(f"[叫分] {label}@({target[0]},{target[1]})")
            time.sleep(3.0)  # 等发牌入场动画(逐张滑入 ~3s)落定
            continue
        # 2) 出牌轮(我回合: 有灰钮=可跟, 无灰钮=必出/领打)
        ap.update_zones(img)
        row = ap.button_row(img)
        grey, green = row["grey"], row["green"]
        if not hand:
            ranks = rec.read_hand_vlm(img)
            hand = sorted(E.token_to_rank(t) for t in ranks) if ranks else []
            print(f"[建belief] hand={[E.rank_to_token(r) for r in hand]}")
            time.sleep(0.6)
            continue
        if grey is None:
            # 复查宽松灰(按压色#424242/暗灰) — 防瞬态漏检把"可不出"误判为领打
            loose = ap.grey_loose(img)
            if loose:
                grey = loose
                # 落回跟牌逻辑: 直接跳到跟牌块
                pass
            else:
                # ---- 领打/必出: 提示钮(游戏自选, 必然合法) ----
                print("[领打/必出] 提示钮出牌")
                st = play_via_hint(ap)
                if st == "ok":
                    print("  ✓ 出牌成功")
                    hand = []  # 提示自选, 牌未知 → 下回合重建 belief
                    ap.last_zone_key, ap.zone_acted = None, False
                else:
                    print(f"  ✗ 提示出牌失败({st}), 下轮再试")
                time.sleep(1.0)
                continue
        # ---- 跟牌(有人出了, 可跟可不跟) ----
        zone = ap.last_played_zone(img)
        zone_key = ap.zone_sig.get(zone) if zone else None
        if zone and zone_key == ap.last_zone_key and ap.zone_acted:
            # 同一牌堆已决策过且仍是我回合 → 上次动作没生效, 保守不出
            print("  → 重复回合, 保守不出")
            adb("shell", "input", "tap", str(grey[0]), str(grey[1]))
            ap.last_zone_key, ap.zone_acted = None, False
            time.sleep(1.2)
            continue
        ap.last_zone_key, ap.zone_acted = zone_key, False
        ranks = ap.read_zone_cards(img, zone) if zone else []
        if len(ranks) > 10 or (len(ranks) >= 9 and E.identify(ranks).type == E.T.STRAIGHT and ranks[-1] == 14):
            print(f"[跟牌] 读数可疑({len(ranks)}张) 弃读 → 不出")
            adb("shell", "input", "tap", str(grey[0]), str(grey[1]))
            ap.zone_acted = True
            time.sleep(1.2)
            continue
        last = E.identify(ranks) if ranks else E.Group()
        if last.is_invalid or last.type == E.T.ROCKET:
            print(f"[跟牌] 上一手(zone={zone}) 读空或火箭 → 不出")
            adb("shell", "input", "tap", str(grey[0]), str(grey[1]))
            time.sleep(1.2)
            continue
        print(f"[跟牌] 上一手({zone}): {[E.rank_to_token(r) for r in ranks]} = {last.type.name}")
        choice = bot.pick_follow(hand, last)
        if choice is None:
            adb("shell", "input", "tap", str(grey[0]), str(grey[1]))
            print("  → 不出")
            time.sleep(1.2)
            continue
        # 提示钮出牌(必然合法; 引擎候选仅用于决策)
        print(f"[跟牌] 决策=出({E.group_to_str(choice)}), 执行走提示钮")
        st = play_via_hint(ap)
        if st == "ok":
            print("  ✓ 出牌成功")
            hand = []  # 提示自选 → 下回合重建 belief
        else:
            print(f"  ✗ 出牌失败({st}) → 保守不出")
            adb("shell", "input", "tap", str(grey[0]), str(grey[1]))
        ap.zone_acted = True
        time.sleep(1.2)
        continue


if __name__ == "__main__":
    main()
