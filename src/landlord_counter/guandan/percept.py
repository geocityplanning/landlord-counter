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


def read_hand_ordered(rec, img) -> list[Card] | None:
    """切两半读手牌 → 拼接 → 消毒。返回按左→右顺序的 Card 列表或 None。"""
    y0, y1 = HAND_BAND
    parts: list[list[str]] = []
    for (x0, x1) in SPLITS:
        txt = _read(rec, img[y0:y1, x0:x1], PROMPT_HAND)
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


def read_table_last(rec, img) -> list[Card] | None:
    """读桌面"待压的那一手"; 无牌/均不出 → []。失败 None(重试2次)。"""
    roi = img[180:800, :, :]
    for _ in range(2):
        txt = _read(rec, roi, PROMPT_TABLE)
        if not txt:
            continue
        if "无" in txt:
            return []
        toks = _split_tokens(txt)
        try:
            return cards_from_tokens(toks)
        except Exception:  # noqa: BLE001
            continue
    return None


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
