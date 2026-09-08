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
        """按钮行内 grey/green。grey 含按压暗色 #424242 兜底(min_w150)防瞬态漏检。"""
        grey = self.grey_loose(img)
        green = mask_blobs(img, GREEN, 35, 120, 300, 150, 60)
        out = {"grey": grey}
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

    def _zone_card_rect(self, img, zone):
        """牌堆白卡内容感知定位: 亮白(卡面)像素 bbox; 无卡返回 None。"""
        import numpy as np

        x0, y0, x1, y1 = TABLE_CROP[zone]
        band = img[y0:y1, x0:x1]
        bgr = band.astype(np.int16)
        # 白卡面: RGB 全高 & 低饱和(排除红色点色/绿底)
        r, g, b = bgr[:, :, 2], bgr[:, :, 1], bgr[:, :, 0]
        white = (r > 200) & (g > 200) & (b > 200)
        sat = bgr.max(axis=2) - bgr.min(axis=2)
        mask = white & (sat < 60)
        ys, xs = np.where(mask)
        if len(xs) < 600:  # 至少 ~120x120 卡面
            return None
        xa, xb = xs.min(), xs.max()
        ya, yb = ys.min(), ys.max()
        if (xb - xa) < 70 or (yb - ya) < 80:
            return None
        return (x0 + xa, y0 + ya, x0 + xb, y0 + yb)

    def read_zone_cards(self, img, zone) -> list[int]:
        rect = self._zone_card_rect(img, zone)
        if rect is None:
            return []  # 无白卡牌堆, 不发VLM
        xa, ya, xb, yb = rect
        # 内容外扩一点(点数在左上角, 防切边)
        pad_x, pad_y = 6, 8
        xa, ya = max(0, xa - pad_x), max(0, ya - pad_y)
        xb, yb = min(img.shape[1] - 1, xb + pad_x), min(img.shape[0] - 1, yb + pad_y)
        crop = img[ya:yb, xa:xb]
        crop = cv2.resize(crop, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
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
            # 命中=相邻牌中心分界(hitTestCard): 点 0.4*sp 处(避开右边界, 中心更稳)
            x = int(start_x + i * sp + sp * 0.4)
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


def lifted_count(img) -> int:
    """估计已选中的手牌数: 条带 y424..484(未选中时为空)亮列宽/间距。"""
    if img is None:
        return 0
    gray = cv2.cvtColor(img[424:484, 20:1260], cv2.COLOR_BGR2GRAY)
    cols = (gray > 205).any(axis=0)
    run = width = 0
    for v in cols:
        if v:
            run += 1
            width = max(width, run)
        else:
            run = 0
    if width < 60:
        return 0
    # 选中相邻牌: 宽度≈sp*(k-1)+卡宽 ~ 取亮宽/88 估算
    return max(1, int(round(width / 95)))


def tap_pass(ap: "AutoPlay") -> bool:
    """新鲜截图找灰钮点'不出'; 无灰钮返回 False。"""
    img2 = snap()
    g2 = ap.button_row(img2)["grey"] if img2 is not None else None
    if not g2:
        return False
    adb("shell", "input", "tap", str(g2[0]), str(g2[1]))
    return True


def play_lead_direct(ap: "AutoPlay", hand: list[int]) -> str:
    """领打: 直接点最小单张(物理已验证命中几何)+出牌绿钮; 'ok'|'fail'。"""
    if not hand:
        return "fail"
    n = len(hand)
    sp = min(max((HAND_AVAIL - CARD_W) / max(n - 1, 1), CARD_W * 0.35), CARD_W * 0.90)
    start_x = (1280.0 - (sp * (n - 1) + CARD_W)) / 2
    # 最小单张所在位置(升序 belief 第0个rank的所有同rank中第一个)
    r0 = hand[0]
    idx = next(i for i, h in enumerate(hand) if h == r0)
    x = int(start_x + idx * sp + sp * 0.4)
    for _ in range(2):
        adb("shell", "input", "tap", str(x), str(HAND_Y))
        time.sleep(0.35)
        img = snap()
        if img is None:
            return "fail"
        btns = ap.button_row(img)
        if not btns["green"]:
            return "fail"
        adb("shell", "input", "tap", str(btns["green"][0]), str(btns["green"][1]))
        time.sleep(1.8)
        img2 = snap()
        if img2 is None:
            return "fail"
        if not my_turn(ap, img2):
            return "ok"
    return "fail"


def play_smart(ap: "AutoPlay") -> str:
    """提示钮出牌+抬起确认。'ok'|'none'(无解→pass)|'end'(回合已结束)|'fail'。"""
    img = snap()
    if img is None:
        return "fail"
    if not my_turn(ap, img):
        return "end"  # 决策期间回合已结束(结算/轮到别人)
    for _ in range(2):
        blue = mask_blobs(img, BLUE, 25, 120, 300, 120, 50)
        if not blue:
            return "fail"
        adb("shell", "input", "tap", str(blue[0][0]), str(blue[0][1]))
        time.sleep(1.2)
        img2 = snap()
        lift = lifted_count(img2)
        if lift == 0:
            return "none"
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
        img = img3  # 重试一次用最新帧
    return "fail"


def attempt_play(ap: "AutoPlay", hand: list[int], choice: E.Group) -> str:
    """引擎直选+出牌(失败重试一次)。'ok'|'pass'(可不出)|'fail'(卡住)。"""
    for _ in range(2):
        img0 = snap()
        if img0 is None:
            return "fail"
        if not ap.play(img0, choice, hand):
            return "fail"
        time.sleep(1.7)
        img2 = snap()
        if img2 is None:
            return "fail"
        if not my_turn(ap, img2):
            return "ok"
    img2 = snap()
    grey2 = ap.button_row(img2)["grey"] if img2 is not None else None
    return "pass" if grey2 else "fail"


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
        # 2) 我回合统一处理: 读上家→决策(出/不出)→play_smart执行→按结果走
        ap.update_zones(img)
        row = ap.button_row(img)
        grey, green = row["grey"], row["green"]
        if not hand:
            ranks = rec.read_hand_vlm(img)
            hand = sorted(E.token_to_rank(t) for t in ranks) if ranks else []
            print(f"[建belief] hand={[E.rank_to_token(r) for r in hand]}")
            time.sleep(0.6)
            continue
        zone = ap.last_played_zone(img)
        zone_key = ap.zone_sig.get(zone) if zone else None
        tag = "领打/必出"
        if grey is not None and zone:
            # 跟牌决策(只有能不出时才需要判断; 无灰=真领打, 直接出)
            if zone_key == ap.last_zone_key and ap.zone_acted:
                print("  → 重复回合, 保守不出")
                if not tap_pass(ap):
                    print("    无灰钮, 转出牌")
                ap.last_zone_key, ap.zone_acted = None, False
                time.sleep(1.2)
                continue
            ap.last_zone_key, ap.zone_acted = zone_key, False
            ranks = ap.read_zone_cards(img, zone)
            if len(ranks) > 10 or (len(ranks) >= 9 and E.identify(ranks).type == E.T.STRAIGHT and ranks[-1] == 14):
                print(f"[跟牌] 读数可疑({len(ranks)}张) 弃读 → 不出")
                if not tap_pass(ap):
                    print("    无灰钮, 转出牌")
                ap.zone_acted = True
                time.sleep(1.2)
                continue
            last = E.identify(ranks) if ranks else E.Group()
            if last.is_invalid or last.type == E.T.ROCKET or not last.ranks:
                print(f"[跟牌] 上一手({zone}) 读空/火箭 → 不出")
                if not tap_pass(ap):
                    print("    无灰钮, 转出牌")
                time.sleep(1.2)
                continue
            print(f"[跟牌] 上一手({zone}): {[E.rank_to_token(r) for r in ranks]} = {last.type.name}")
            choice = bot.pick_follow(hand, last)
            if choice is None:
                print("  → 不出")
                if not tap_pass(ap):
                    print("    无灰钮, 转出牌")
                time.sleep(1.2)
                continue
            tag = f"跟牌(压{last.type.name})"
        elif grey is not None:
            # 可不出但上家牌堆未知/过期: 交给提示钮自决(能压则hint会选中)
            tag = "跟牌(上家未知→提示自决)"
        # 执行: 领打=直选最小单张(物理几何已验证); 跟牌=提示钮(必然合法); 抬起确认
        if tag == "领打/必出":
            print("[领打/必出] 直选最小单张")
            st = play_lead_direct(ap, hand)
            if st == "ok":
                remove_all(hand, [hand[0]])
                print("  ✓ 领打出牌成功")
                ap.last_zone_key, ap.zone_acted = None, False
                time.sleep(1.2)
                continue
            print(f"  ✗ 直选失败({st}) → 提示钮兜底")
        print(f"[{tag}] → play_smart")
        st = play_smart(ap)
        if st == "ok":
            print("  ✓ 出牌成功(提示所选, belief重建)")
            hand = []
            ap.last_zone_key, ap.zone_acted = None, False
        elif st == "end":
            print("  → 回合已结束(竞态), 重扫")
            time.sleep(0.8)
            continue
        elif st == "none":
            print("  → 提示无解, 不出")
            img2 = snap()
            g2 = ap.button_row(img2)["grey"] if img2 is not None else None
            if g2:
                adb("shell", "input", "tap", str(g2[0]), str(g2[1]))
            ap.zone_acted = True
        else:
            print(f"  ✗ play_smart失败({st})")
            img2 = snap()
            g2 = ap.button_row(img2)["grey"] if img2 is not None else None
            if g2:
                adb("shell", "input", "tap", str(g2[0]), str(g2[1]))
                print("  → 保守不出")
                ap.zone_acted = True
        time.sleep(1.2)
        continue


if __name__ == "__main__":
    main()
