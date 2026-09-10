"""掼蛋视觉感知层: 手牌(切半读+拼接) / 桌面待压牌 / 轮次判定。

坐标基于实测(720x1280, dpr2): 手牌带 y[805,945]; 左半 x[0,370], 右半 x[350,720]
"""
from __future__ import annotations

import cv2
import numpy as np

from .rules import Card, cards_from_tokens

HAND_BAND = (805, 945)
SPLITS = [(0, 370), (350, 720)]

PROMPT_HAND = (
    "这是一排掼蛋手牌的一部分(从左到右,相互重叠,每张只露出左上角的花色符号+点数)。"
    "逐张输出\"花色+点数\",逗号分隔,不要解释,不要合并重复。花色用♠♥♦♣,10写10,大王写大王,小王写小王。"
)
PROMPT_TABLE = (
    "这是掼蛋牌桌的出牌区(四家)。请找出**当前需要被压过的那一手牌**(桌上最后打出的、不是\"不出\"的牌),"
    "按\"花色+点数\"逗号分隔输出,如 ♠K,♠K;若四家均无牌或都是不出,只输出: 无。不要解释。"
)


def _read(rec, roi, prompt: str) -> str:
    if roi is None or roi.size == 0:
        return ""
    up = cv2.resize(roi, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)
    return rec.recognize_with_vlm(up, prompt) or ""


def _merge_halves(left: list[str], right: list[str]) -> list[str]:
    """拼接左右半: 找最大重叠(右半开头与左半结尾的公共段)后去重。"""
    for k in range(min(len(left), len(right), 4), 0, -1):
        if left[-k:] == right[:k]:
            return left + right[k:]
    return left + right


_HUA = "♠♥♣♦"


def _norm_token(t: str) -> str:
    """VLM 常输出"花色在前"(♠J), 引擎要"点数在前"(J♠) → 归一化; 并纠 '1'→'10'。"""
    t = t.strip()
    if t and t[0] in _HUA:
        t = t[1:] + t[0]
    if t and t[0] in ("1", "l", "I") and (len(t) == 1 or t[1] in _HUA):
        t = "10" + t[1:]
    return t


def _split_tokens(txt: str) -> list[str]:
    return [_norm_token(t) for t in txt.replace("，", ",").replace("、", ",").split(",") if t.strip()]


def read_hand_ordered(rec, img, expected: int = 0) -> list[Card] | None:
    """切两半读手牌 → 拼接 → 消毒。expected>0 时提示词注入张数。返回左→右顺序 Card 或 None。"""
    y0, y1 = HAND_BAND
    prompt = PROMPT_HAND + (f" 这一排共 {expected} 张。" if expected > 0 else "")
    parts: list[list[str]] = []
    for (x0, x1) in SPLITS:
        txt = _read(rec, img[y0:y1, x0:x1], prompt)
        parts.append(_split_tokens(txt))
    if not parts[0] or not parts[1]:
        return None
    merged = _merge_halves(parts[0], parts[1])
    # 消毒: 总≤27, 同点数≤8, 王各≤2
    try:
        cards = cards_from_tokens(merged)
    except Exception:  # noqa: BLE001
        return None
    if not cards or len(cards) > 27:
        return None
    from collections import Counter

    cnt = Counter(c.zhi for c in cards)
    if cnt.get(15, 0) > 2 or cnt.get(16, 0) > 2:
        return None
    if any(v > 8 for v in cnt.values()):
        return None
    return cards[:27]


PROMPT_REGION = (
    "这是掼蛋某位玩家的出牌区截图。逐张输出这手牌的\"花色+点数\",逗号分隔(如 ♠K,♥K);"
    "如果这里没有牌(空白或只有\"不出\"字样),只输出: 无。不要解释。"
)

# 四家出牌区(设备像素, 实测桌面区 y≈160..800): 右=东(我上家) 上=北(队友) 左=西 下=我
REGIONS = {
    "right": (380, 360, 700, 720),
    "top": (80, 180, 640, 460),
    "left": (20, 360, 340, 720),
    "bottom": (80, 600, 640, 800),
}


def _region_cards(img, box) -> int:
    x0, y0, x1, y1 = box
    sub = img[y0:y1, x0:x1]
    b, g, r = sub[:, :, 0].astype(int), sub[:, :, 1].astype(int), sub[:, :, 2].astype(int)
    white = ((b > 200) & (g > 200) & (r > 200)).astype(np.uint8)
    n = int(white.sum())
    if n < 2500:
        return 0
    ys, xs = np.where(white > 0)
    if len(xs) == 0:
        return 0
    w = xs.max() - xs.min()
    h = ys.max() - ys.min()
    if w < 80 or h < 60:  # 太小的白块(文字"不出")不算牌
        return 0
    return n


def _split_box(mask, box, y0):
    """把合并的牌块按"无白列的竖直间隙(≥6px)"拆成子块; 返回子块列表。"""
    x, y, w, h = box
    sub = mask[y:y + h, x:x + w]
    cols = sub.any(axis=0)
    boxes = []
    st = None
    gap = 0
    for i, v in enumerate(cols):
        if v:
            if st is None:
                st = i
            gap = 0
        else:
            if st is not None:
                gap += 1
                if gap >= 6:
                    boxes.append((x + st, y, i - gap - st + 1, h))
                    st = None
                    gap = 0
    if st is not None:
        boxes.append((x + st, y, len(cols) - st, h))
    out = []
    for (bx, by, bw, bh) in boxes:
        if bw < 60 or bh < 60:
            continue
        # 子块内白像素数
        cnt = int(mask[by:by + bh, bx:bx + bw].sum())
        if cnt >= 1800:
            out.append((bx, by, bw, bh, cnt))
    return out


def table_plays(img):
    """桌面牌块检测: 返回 [(区域名, bbox, 白像素数)] — 聚类后按竖直间隙拆块再归属玩家区。
    同一玩家只保留最大块(每轮每人至多一手)。"""
    x0, y0, x1, y1 = 0, 150, 720, 820
    sub = img[y0:y1, x0:x1]
    b, g, r = sub[:, :, 0].astype(int), sub[:, :, 1].astype(int), sub[:, :, 2].astype(int)
    m = ((b > 200) & (g > 200) & (r > 200)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
    cands = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a < 2500 or w < 80 or h < 60:
            continue
        for (bx, by, bw, bh, cnt) in _split_box(m > 0, (x, y, w, h), y0):
            cx, cy = bx + bw // 2, by + bh // 2 + y0
            if cy > 620:
                name = "bottom"
            elif cx < 300:
                name = "left"
            elif cx > 420:
                name = "right"
            elif cy < 480:
                name = "top"
            else:
                continue  # 中心混合块忽略
            cands.append((name, (bx, by + y0, bw, bh), cnt))
    # 每区域保留最大块
    best = {}
    for name, box, cnt in cands:
        if name not in best or cnt > best[name][1]:
            best[name] = (box, cnt)
    return [(name, box, cnt) for name, (box, cnt) in best.items()]


def read_region_cards(rec, img, box) -> list[Card] | None:
    """读指定出牌区(内容感知外扩) → 牌列表; 读不出 None。"""
    x, y, w, h = box
    pad = 8
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(img.shape[1], x + w + pad), min(img.shape[0], y + h + pad)
    for _ in range(2):
        txt = _read(rec, img[y0:y1, x0:x1], PROMPT_REGION)
        if not txt:
            continue
        if "无" in txt:
            return None
        try:
            return cards_from_tokens(_split_tokens(txt))
        except Exception:  # noqa: BLE001
            continue
    return None


def read_table_last(rec, img) -> list[Card] | None:
    """找到最近一手非"不出": 用桌面牌块聚类按逆出牌序(东→北→西)取最近一块。
    返回牌列表; 三家皆无牌(我领出) → []; 读失败 → None。"""
    plays = {name: box for name, box, _ in table_plays(img)}
    for name in ("right", "top", "left"):
        box = plays.get(name)
        if not box:
            continue
        cards = read_region_cards(rec, img, box)
        if cards is not None:
            return cards
        return None
    return []


def white_count(img) -> int:
    y0, y1 = HAND_BAND
    band = img[y0:y1]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    return int(((b > 200) & (g > 200) & (r > 200)).sum())


def my_turn(img, thresh: int = 4000) -> bool:
    return white_count(img) >= thresh


WHITE_TURN_MIN = 4000  # 我方回合白卡阈值


def card_tap_x(index: int) -> int:
    """第 index 张手牌的点击 x(实测: 起点2, 步距24, 取露出区中部)"""
    return 2 + index * 24 + 20


def hand_columns(img) -> int:
    """像素数手牌张数: 手牌带亮列分段数(实测27张→27段)"""
    y0, y1 = HAND_BAND
    band = img[y0:y1]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    colsum = ((b > 200) & (g > 200) & (r > 200)).sum(axis=0)
    runs = 0
    st = False
    for v in colsum > 10:
        if v and not st:
            runs += 1
        st = v
    return runs


def lifted_px(img) -> int:
    """选中牌抬起后的亮带宽度(y770-812: 选中牌上移36px后露出)"""
    band = img[770:812]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    return int(((b > 200) & (g > 200) & (r > 200)).sum())
