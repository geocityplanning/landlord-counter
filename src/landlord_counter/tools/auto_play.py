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

import os
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
        self.last_counted_sig: dict = {"L": None, "R": None}
        self.round_plays = 0  # 本局已出牌次数(>0 = 出牌阶段, 非叫分)
        # DouZero 回合状态 (round-local)
        self.landlord_seat: str | None = None  # human/B/A
        self.seat_played: dict[str, int] = {"B": 0, "A": 0}  # 已出张数(估)
        self.round_first_actor_checked = False

    def round_reset(self):
        self.landlord_seat = None
        self.seat_played = {"B": 0, "A": 0}
        self.round_first_actor_checked = False
        self.last_zone_key = None
        self.zone_acted = False
        self.last_counted_sig = {"L": None, "R": None}
        self.round_plays = 0

    def note_new_plays(self, img):
        """新出现的牌堆: 估张数记入 seat_played; 首个出牌者=地主。"""
        for zone in ZONES:
            sig = self.zone_sig.get(zone)
            if sig is None or sig == self.last_counted_sig.get(zone):
                continue
            rect = self._zone_card_rect(img, zone)
            if rect is None:
                continue
            w = rect[2] - rect[0]
            n = max(1, int(round((w - 119) / 61.2)) + 1)
            seat = "B" if zone == "L" else "A"
            if self.landlord_seat is None:
                self.landlord_seat = seat
            self.seat_played[seat] = self.seat_played.get(seat, 0) + n
            self.last_counted_sig[zone] = sig
            self.round_plays += 1

    # ---------- 相位 & 动作检测 ----------
    def button_row(self, img) -> dict:
        """按钮行内 grey/green。grey 含按压暗色 #424242 兜底(min_w150)。
        出牌绿钮: x∈[700,1050] 中最右(实测786/980; 机器人头像绿在x≈260/1100+排除)。"""
        grey = self.grey_loose(img)
        green = [b for b in mask_blobs(img, GREEN, 35, 120, 300, 150, 60) if 700 <= b[0] <= 1050]
        out = {"grey": grey}
        out["green"] = green[-1] if green else None
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
        time.sleep(0.5)  # 等抬起动画落定
        img = snap()
        if img is None:
            return False
        # 点"出牌"(绿钮) — 必须从抬起校验后的新帧取绿钮坐标
        btns = self.button_row(img)
        att = os.environ.get("ATT_DIR")
        if att:
            os.makedirs(f"{att}/f", exist_ok=True)
            cv2.imwrite(f"{att}/f/sel_{int(time.time()*100)%1000000}.png", img)
            with open(f"{att}/sel.csv", "a") as fo:
                gray = cv2.cvtColor(img[424:484, 20:1260], cv2.COLOR_BGR2GRAY)
                cols = (gray > 205).any(axis=0)
                xs = [i for i, v in enumerate(cols) if v]
                w = xs[-1] - xs[0] if len(xs) > 60 else 0
                fo.write(f"{time.time():.1f},idx={pos},n={len(hand)},lift_w={w},green_x={btns['green'][0] if btns['green'] else -1}\n")
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


def my_turn_stable(ap: "AutoPlay") -> tuple[bool, dict | None]:
    """稳定双帧回合判定: 0.35s两连拍; 必须绿钮(出牌, x≥700)两帧一致才算出牌轮。
    (我方出牌绿钮中心实测 786/980; 机器人头像绿块在 x≈260 → 用x≥700滤除)"""
    a = snap()
    if a is None:
        return False, None
    time.sleep(0.35)
    b = snap()
    if b is None:
        return False, None
    ra, rb = ap.button_row(a), ap.button_row(b)
    ga = ra["green"]
    gb = rb["green"]
    if ga is None or gb is None:
        return False, None
    if ga[0] < 700 or gb[0] < 700:
        return False, None
    if abs(ga[0] - gb[0]) > 25 or abs(ga[1] - gb[1]) > 25:
        return False, None
    return True, rb


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


def turn_ended(ap: "AutoPlay") -> bool:
    """我回合是否已结束(稳定双帧, 滤机器人头像误报)。"""
    ok, _ = my_turn_stable(ap)
    return not ok


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
        time.sleep(2.0)
        if turn_ended(ap):
            return "ok"
    return "fail"


def play_smart(ap: "AutoPlay") -> str:
    """提示钮出牌+抬起确认。'ok'|'none'(无解→pass)|'end'(回合已结束)|'fail'。"""
    img = snap()
    if img is None:
        return "fail"
    ok, _ = my_turn_stable(ap)
    if not ok:
        return "end"  # 决策期间回合已结束(结算/轮到别人)
    for _ in range(2):
        blue = mask_blobs(img, BLUE, 25, 120, 300, 120, 50)
        if not blue:
            return "fail"
        adb("shell", "input", "tap", str(blue[0][0]), str(blue[0][1]))
        time.sleep(1.3)
        img2 = snap()
        lift = lifted_count(img2)
        if lift == 0:
            return "none"
        btns = ap.button_row(img2)
        if not btns["green"]:
            return "fail"
        adb("shell", "input", "tap", str(btns["green"][0]), str(btns["green"][1]))
        time.sleep(2.0)
        if turn_ended(ap):
            return "ok"
        img = img2  # 重试一次用最新帧
    return "fail"


def _att_log(result: str, choice) -> None:
    att = os.environ.get("ATT_DIR")
    if not att:
        return
    try:
        with open(f"{att}/result.csv", "a") as fo:
            fo.write(f"{time.time():.1f},{result},{[c for c in choice.ranks] if choice else []}\n")
    except Exception:  # noqa: BLE001
        pass


def attempt_play(ap: "AutoPlay", hand: list[int], choice: E.Group) -> str:
    """引擎直选+出牌: 点选→1.2s后校验抬起→点绿; 补救≤2次(有抬起只补绿, 无抬起重选)。
    'ok'|'pass'(可不出)|'fail'(卡住)。"""
    img0 = snap()
    if img0 is None:
        return "fail"
    if not ap.play(img0, choice, hand):
        return "fail"
    time.sleep(1.2)
    img2 = snap()
    if img2 is not None and not my_turn(ap, img2):
        _att_log("ok", choice)
        return "ok"
    for _ in range(2):  # 补救: 有抬起→只补点绿钮; 无抬起→整轮重选
        time.sleep(0.4)
        imgv = snap()
        if imgv is None:
            continue
        lift = lifted_count(imgv)
        if lift > 0:
            gv = ap.button_row(imgv)
            if not gv["green"]:
                _att_log("still_myturn", choice)
                continue
            adb("shell", "input", "tap", str(gv["green"][0]), str(gv["green"][1]))
            time.sleep(1.8)
            img3 = snap()
            if img3 is not None and not my_turn(ap, img3):
                _att_log("ok", choice)
                return "ok"
            _att_log("still_myturn", choice)
            continue
        # 抬起丢失(被toggle/动画) → 整轮重选+点绿
        if not ap.play(imgv, choice, hand):
            return "fail"
        time.sleep(1.2)
        img4 = snap()
        if img4 is not None and not my_turn(ap, img4):
            _att_log("ok", choice)
            return "ok"
        _att_log("still_myturn", choice)
    img2 = snap()
    grey2 = ap.button_row(img2)["grey"] if img2 is not None else None
    r = "pass" if grey2 else "fail"
    _att_log(r, choice)
    return r


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


def _dz_init():
    """DouZero 桥接(可选): DOUZERO=1 且权重存在才启用。"""
    try:
        from landlord_counter.logic.douzero_bridge import DouZeroBot

        wdir = os.getenv("DOUZERO_WEIGHTS", "/tmp/dz_w")
        dz = DouZeroBot(wdir, enabled=os.getenv("DOUZERO", "0") == "1")
        if dz.available():
            print(f"▶ DouZero 决策启用 (weights={wdir})")
            return dz
    except Exception as e:  # noqa: BLE001
        print(f"  DouZero 不可用({e}), 用规则/提示")
    return None


def _dz_role_counts(ap: "AutoPlay", hand: list[int]) -> tuple[str, dict]:
    """我方 DouZero 角色 + 各家手数(估)。首动者未定→我方是地主(地主先出)。"""
    seat = ap.landlord_seat if ap.landlord_seat is not None else "human"
    cycle = ["human", "B", "A"]
    li = cycle.index(seat)
    counts = {}
    for i, s in enumerate(cycle):
        if s == seat:
            counts["landlord"] = len(hand) if s == "human" else 20 - ap.seat_played.get(s, 0)
        else:
            role = "down" if (li + 1) % 3 == i else "up"
            counts[role] = len(hand) if s == "human" else 17 - ap.seat_played.get(s, 0)
    if "landlord" not in counts:
        counts["landlord"] = 20 - ap.seat_played.get(seat, 0)
    role_human = "landlord" if seat == "human" else ("down" if (li + 1) % 3 == cycle.index("human") else "up")
    return role_human, counts


def _sanitize_read(tokens: list[str]) -> list[str] | None:
    """合理性检查: 大王/小王各≤1、每点≤4、总∈[1,20]。异常返回 None(弃读)。"""
    from collections import Counter

    c = Counter(tokens)
    if not tokens or not (1 <= len(tokens) <= 20):
        return None
    for t in ("小", "大", "BJ", "RJ"):
        if c.get(t, 0) > 1:
            return None
    for t, n in c.items():
        if n > 4:
            return None
    return sorted(tokens, key=lambda x: E.token_to_rank(x))


def read_hand_sane(rec, img, expected: int = 0) -> list[int]:
    """读数+合理性消毒(最多2次)。返回 rank 升序列表; 失败 []。"""
    for _ in range(2):
        toks = rec.read_hand_vlm(img, expected=expected)
        ok = _sanitize_read(toks)
        if ok is not None:
            return sorted(E.token_to_rank(t) for t in ok)
    return []


PROMPT_RESULT = "这是斗地主结算画面。只回答两个字: 我赢了(输赢) — 输出\"赢\"或\"输\""
_dz_acts_round = 0  # 本局 DouZero 决策次数(统计用)


def _stats_round(ap, img, result: str) -> None:
    """结算统计: CSV 一行 (ts, 角色, 结果, DouZero决策数)。"""
    f = os.environ.get("STATS_FILE")
    if not f:
        return
    try:
        role = "landlord" if ap.landlord_seat is None else "farmer"
        with open(f, "a") as fo:
            fo.write(f"{time.time():.0f},{role},{result},{_dz_acts_round}\n")
    except Exception:  # noqa: BLE001
        pass


def main():
    global _dz_acts_round
    cfg = load_config()
    rec = CardRecognizer(cfg.vision)
    ap = AutoPlay(rec)
    dz = _dz_init()
    hand: list[int] = []  # 当前手牌 belief(升序), 由发牌投票/出牌自减维护
    pending_relandlord = False  # 叫3分可能成地主 → 需按20张重读(含底牌)
    skip_until = 0.0  # 数牌失真防抖暂停截至时刻
    print("▶ auto_play 启动 (完整托管 v1)")
    while True:
        img = snap()
        if img is None:
            time.sleep(1)
            continue
        # 0) 结算: 判胜负(可选统计) + 再来一局
        btn = ap.result_screen(img)
        if btn:
            if os.environ.get("STATS_FILE"):
                txt = rec.recognize_with_vlm(img, PROMPT_RESULT) or ""
                res = "win" if "赢" in txt else ("lose" if "输" in txt else "?")
                print(f"[结算] VLM判: {txt.strip()[:20]!r} → {res}")
                _stats_round(ap, img, res)
            adb("shell", "input", "tap", str(btn[0]), str(btn[1]))
            print("[结算] 点再来一局, 等新发牌…")
            time.sleep(2)
            continue
        row = ap.button_row(img)
        grey, green = row["grey"], row["green"]
        if not grey and not green:
            ap.update_zones(img)  # 机器人回合: 只跟踪牌堆变化
            ap.note_new_plays(img)
            time.sleep(0.8)
            continue
        # 1) 叫分轮(无绿 + 本局尚未有人出牌; 防中局"灰钮瞬态漏检"误判成叫分重置)
        if not green and ap.round_plays == 0:
            if hand:  # 上一局残念 → 新局重置(含 DouZero 回合状态)
                hand = []
                ap.round_reset()
                _dz_acts_round = 0
            if not hand:  # 新局: 发牌已展示, 读一次建立 belief
                hand = read_hand_sane(rec, img)
                if hand:
                    print(f"[新局] 屏读 hand={[E.rank_to_token(r) for r in hand]}")
                    _vd = os.environ.get("AUTO_VERIFY")
                    if _vd:
                        os.makedirs(_vd, exist_ok=True)
                        _k = len(os.listdir(_vd))
                        cv2.imwrite(f"{_vd}/v{_k:02d}.png", img)
                        print(f"  📷 验证帧 → {_vd}/v{_k:02d}.png")
            score = bot.decide_bid(hand)
            # 不叫=灰钮(单色, 恒最左); 3分=红钮(单色, 最右)。禁用多色union(相邻钮会桥接成巨块)
            target, label = grey, "不叫"
            if score > 0:
                reds = ap._color_blocks(img, [(0xD3, 0x2F, 0x2F)], 35, min_w=220, min_h=100)
                if reds:
                    target, label = reds[-1], f"叫 {score}分"
            if target:
                adb("shell", "input", "tap", str(target[0]), str(target[1]))
                print(f"[叫分] {label}@({target[0]},{target[1]})")
                if label.startswith("叫"):
                    pending_relandlord = True  # 可能成地主, 底牌并入后按20张重读
            time.sleep(3.0)  # 等发牌入场动画(逐张滑入 ~3s)落定
            continue
        # 2) 我回合统一处理(稳定双帧判定, 滤机器人头像误报)
        ap.update_zones(img)
        ap.note_new_plays(img)
        turn_ok, st_row = my_turn_stable(ap)
        if not turn_ok:
            time.sleep(0.5)
            continue
        grey, green = st_row["grey"], st_row["green"]
        if pending_relandlord and hand:
            # 等底牌并入手牌后按 20 张重读(现在大概率已是地主回合/立刻会到)
            ranks = read_hand_sane(rec, img, expected=20)
            if len(ranks) >= 18:
                hand = ranks
                pending_relandlord = False
                print(f"[成地主] 重读20张: {[E.rank_to_token(r) for r in hand]}")
            else:
                time.sleep(1.0)
                continue
        if not hand:
            hand = read_hand_sane(rec, img)
            if hand:
                print(f"[建belief] hand={[E.rank_to_token(r) for r in hand]}")
            time.sleep(0.6)
            continue
        # 手牌 belief 长度自检(布局总宽恒定→张数不可由亮宽推出, 仅保留日志)
        # 直选失败根因另查; 此处信任读牌+出牌自减 belief
        # 主动策略(短跑实验): 不读zone, 一律尝试压(提示钮自决); 领打直选
        if grey is None:
            tag = "领打/必出"
        else:
            tag = "跟牌(主动:提示自决)"
        # 执行: 领打=DouZero决策(启用时)→引擎直选; 跟牌=提示钮; 失败回落
        if tag == "领打/必出":
            dz_ok = False
            if dz is not None:
                try:
                    role, counts = _dz_role_counts(ap, hand)
                    htok = [E.rank_to_token(r) for r in hand]
                    out_t = dz.decide(role, htok, counts, {}, None, can_pass=False)
                    if out_t:
                        g = E.identify_str(out_t)
                        if not g.is_invalid and all(hand.count(E.token_to_rank(t)) >= out_t.count(t) for t in set(out_t)):
                            print(f"[领打·DouZero] 决策出 {E.group_to_str(g)} (role={role})")
                            _dz_acts_round += 1
                            st = attempt_play(ap, hand, g)
                            if st == "ok":
                                remove_all(hand, [E.token_to_rank(t) for t in out_t])
                                print("  ✓ DouZero 出牌成功")
                                ap.last_zone_key, ap.zone_acted = None, False
                                time.sleep(1.2)
                                continue
                            print(f"  ✗ DouZero 直选失败({st}) → 回落")
                except Exception as e:  # noqa: BLE001
                    print(f"  DouZero 决策异常({e}) → 回落")
            print("[领打/必出] 规则直选最小单张")
            st = play_lead_direct(ap, hand)
            if st == "ok":
                remove_all(hand, [hand[0]])
                print("  ✓ 领打出牌成功")
                ap.last_zone_key, ap.zone_acted = None, False
                time.sleep(1.2)
                continue
            print(f"  ✗ 直选失败({st}) → 提示钮兜底")
        # 跟牌 DouZero: 读上家牌堆 → 决策(含pass候选) → 直选/不出; 失败回落 play_smart
        if tag.startswith("跟牌") and dz is not None:
            zone = ap.last_played_zone(img)
            if zone:
                ranks = ap.read_zone_cards(img, zone)
                ok_read = 0 < len(ranks) <= 10 and not (
                    len(ranks) >= 9 and E.identify(ranks).type == E.T.STRAIGHT and ranks[-1] == 14)
                if ok_read:
                    try:
                        last_toks = [E.rank_to_token(r) for r in ranks]
                        role, counts = _dz_role_counts(ap, hand)
                        htok = [E.rank_to_token(r) for r in hand]
                        out_t = dz.decide(role, htok, counts, {}, last_toks, can_pass=True)
                        if out_t is None:
                            if tap_pass(ap):
                                print(f"[跟牌·DouZero] 压不过 {last_toks} → 不出 (role={role})")
                                _dz_acts_round += 1
                                ap.zone_acted = True
                                time.sleep(1.2)
                                continue
                            # 无灰钮可不出? 落入 play_smart 提示自决
                        else:
                            g = E.identify_str(out_t)
                            # 跟牌执行走提示钮(100%可靠); DouZero 只负责'出/不出'决策
                            print(f"[跟牌·DouZero] 决策出 {E.group_to_str(g)} 压 {last_toks} (role={role}) → 提示钮执行")
                            _dz_acts_round += 1
                            st = play_smart(ap)
                            if st == "ok":
                                print("  ✓ DouZero 跟牌(提示钮)出牌成功")
                                hand = []
                                ap.last_zone_key, ap.zone_acted = None, False
                                time.sleep(1.2)
                                continue
                            print(f"  ✗ 提示钮执行异常({st})")
                    except Exception as e:  # noqa: BLE001
                        print(f"  DouZero 跟牌异常({e}) → 回落提示钮")
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
