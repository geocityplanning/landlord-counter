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
TABLE_CROP = {"L": (80, 140, 600, 430), "R": (680, 140, 1200, 430)}  # 电脑B/A 牌堆区
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

    # ---------- 相位 & 动作检测 ----------
    def button_row(self, img) -> dict:
        """返回按钮行内的块: grey/green 及其中心。"""
        grey = mask_blobs(img, GREY, 30, 120, 300, 100, 60)
        green = mask_blobs(img, GREEN, 35, 120, 300, 150, 60)
        out = {"grey": grey[0] if grey else None}
        # 绿色块可能含"出牌"(行内) — 取最小那个(x最近左)
        out["green"] = min(green, key=lambda b: b[2]) if green else None
        return out

    def result_screen(self, img):
        g = mask_blobs(img, GREEN, 35, 380, 700, 250, 80)
        return g[0] if g else None

    # ---------- 牌堆区跟踪 ----------
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
            x = int(start_x + i * sp + CARD_W / 2)
            adb("shell", "input", "tap", str(x), str(HAND_Y))
            time.sleep(0.16)
        # 点"出牌"(绿钮)
        btns = self.button_row(img)
        if btns["green"]:
            adb("shell", "input", "tap", str(btns["green"][0]), str(btns["green"][1]))
            return True
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
            score = bot.decide_bid(hand)
            target = grey  # 不叫
            if score > 0:
                reds = mask_blobs(img, (0xD3, 0x2F, 0x2F), 35, 120, 300, 100, 60)
                if reds:
                    target = reds[0]
                    print(f"[叫分] 叫 {score}分 (红钮)")
            if target:
                adb("shell", "input", "tap", str(target[0]), str(target[1] + 6))
                print(f"[叫分] 不叫@({target[0]},{target[1]})")
            time.sleep(2)
            continue
        # 2) 出牌轮: 需知道上一手
        ap.update_zones(img)
        n = len(hand)
        zone = ap.last_played_zone(img)
        if zone and grey and n > 0:  # 有人刚出牌, 可跟/不跟
            ranks = ap.read_zone_cards(img, zone)
            print(f"[跟牌] 上一手({zone}): {[E.rank_to_token(r) for r in ranks]}")
            last = E.identify(ranks) if ranks else E.Group()
            choice = bot.pick_follow(hand, last if not last.is_invalid else None)
            if choice is None:
                adb("shell", "input", "tap", str(grey[0]), str(grey[1]))
                print("  → 不出")
            else:
                ok = ap.play(img, choice, hand)
                print(f"  → 出 {E.group_to_str(choice)} ok={ok}")
                for r in choice.ranks:
                    if r in hand:
                        hand.remove(r)
            time.sleep(1.2)
            continue
        # 3) 领打 / 手牌未知
        if n == 0:
            print("[待牌] 屏读一次建立 belief(应配合 watch_game 投票)")
            ranks = rec.read_hand_vlm(img)
            hand = sorted(E.token_to_rank(t) for t in ranks)
            print(f"  hand={[E.rank_to_token(r) for r in hand]}")
            time.sleep(1.5)
            continue
        choice = bot.pick_lead(hand)
        ok = ap.play(img, choice, hand)
        print(f"[领打] 出 {E.group_to_str(choice)} ok={ok}")
        for r in choice.ranks:
            hand.remove(r)
        time.sleep(1.2)
        continue


if __name__ == "__main__":
    main()
