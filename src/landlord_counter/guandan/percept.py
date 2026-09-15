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
    """读手牌: ≤14 张整排直读; 更多则切两半拼接。expected>0 时提示词注入张数。"""
    y0, y1 = HAND_BAND
    prompt = PROMPT_HAND + (f" 这一排共 {expected} 张。" if expected > 0 else "")
    if expected and expected <= 14:
        toks = _split_tokens(_read(rec, img[y0:y1, :, :], prompt))
        return _sanitize(toks, expected)
    parts: list[list[str]] = []
    for (x0, x1) in SPLITS:
        txt = _read(rec, img[y0:y1, x0:x1], prompt)
        parts.append(_split_tokens(txt))
    if not any(parts):
        return None
    if not parts[0]:
        return _sanitize(parts[1], expected)
    if not parts[1]:
        return _sanitize(parts[0], expected)
    merged = _merge_halves(parts[0], parts[1])
    return _sanitize(merged, expected)


def read_hand_strips(rec, img, n: int, batch: int = 9) -> list[Card] | None:
    """按**牌位几何**分段读手牌(每段恰好覆盖 batch 张, 无需重叠去重)。

    原理: 每张牌只露出左侧 24px, 最后一张露出完整 88px;
    从第 i 张的左缘裁到第 j-1 张的右缘, 画面里**恰好只有** i..j-1 这几张
    (前一张的露出区在左边界之外) → 段间并集无损、无需重叠拼接, 比"固定切两半"稳。
    """
    y0, y1 = HAND_BAND
    if n <= 0:
        return None
    xs = [int(hand_start_x(n) + i * 24) for i in range(n)]
    toks: list[str] = []
    i = 0
    while i < n:
        j = min(n, i + batch)
        x0 = max(0, xs[i] - 2)
        x1 = min(img.shape[1], xs[j - 1] + 88)
        prompt = PROMPT_HAND + f" 这一段共 {j - i} 张。"
        t = _split_tokens(_read(rec, img[y0:y1, x0:x1], prompt))
        if not t or len(t) > (j - i) + 3 or _looks_cyclic(t):
            return None                      # 单段不可信 → 整次读作废(宁可回落)
        toks.extend(t)
        if len(toks) > n + 3:
            return None
        i = j
    if len(toks) != n:
        return None
    return _sanitize(toks, n)


def read_hand_strips_measured(rec, img, n: int, batch: int = 9) -> list[Card] | None:
    """按**实测牌位**分段读手牌(每段恰好覆盖 batch 张, 段间无损)。

    与 read_hand_strips 的区别: 段边界取自 card_positions() 的**实测**位置,
    不再用 hand_start_x(n) 公式 —— 上游"张数"读错时公式会整排平移, 分段裁切跟着错。
    实测(2026-09-15): 整排直读会**只读左半排**(27 张的手牌只读出 12 张), 故改分段。
    """
    y0, y1 = HAND_BAND
    if n <= 0:
        return None
    xs = card_positions(img, n)
    if not xs or len(xs) != n:
        return None
    toks: list[str] = []
    i = 0
    while i < n:
        j = min(n, i + batch)
        x0 = max(0, xs[i] - 14)
        x1 = min(img.shape[1], xs[j - 1] + (88 if j == n else 26))
        prompt = PROMPT_HAND + f" 这一段共 {j - i} 张。"
        # 单段最多试 3 次: VLM 偶发"空返回/少数"(服务端排队, 见技能库铁律 9),
        # 实测同一裁剪第二次就能读全 → 一次空就整次作废太浪费(直选失败的主因之一)。
        t: list[str] = []
        for _try in range(3):
            t = _split_tokens(_read(rec, img[y0:y1, x0:x1], prompt))
            if t and len(t) <= (j - i) + 3 and not _looks_cyclic(t) and abs(len(t) - (j - i)) <= 1:
                break
            t = []
        if not t:
            return None                      # 重试后仍不可信 → 整次作废(宁可回落)
        toks.extend(t)
        if len(toks) > n + 3:
            return None
        i = j
    if len(toks) != n:
        return None
    return _sanitize(toks, n)


PROMPT_ONE = "这是叠在一起的一小段扑克牌(从左到右1-2张),只输出最左边那张的\"花色+点数\",如 ♠K;点数10写10,大王写大王,小王写小王。不要解释。"


def read_hand_by_columns(rec, img, n: int) -> list[Card] | None:
    """逐列单读(小牌量用): 按 pitch 24 逐张裁露出带 → VLM 单张读 → 汇总。"""
    y0, y1 = HAND_BAND
    sx = hand_start_x(n)
    toks: list[str] = []
    for i in range(n):
        x = int(sx + i * 24)
        x0, x1 = max(0, x - 4), min(img.shape[1], x + 40)
        txt = _read(rec, img[y0:y1, x0:x1], PROMPT_ONE)
        t = _split_tokens(txt)
        if not t:
            return None
        toks.append(t[0])
    return _sanitize(toks)


def _looks_cyclic(toks: list[str], max_period: int = 14, min_repeats: int = 3) -> bool:
    """幻觉特征: 输出整段是短周期重复(实测 VLM 在"空区域"会吐 517 个 token 循环整副牌)。"""
    n = len(toks)
    for p in range(1, max_period + 1):
        if n >= p * min_repeats and all(toks[i] == toks[i - p] for i in range(p, n)):
            return True
    return False


def _sanitize(toks: list[str], expected: int = 0) -> list[Card] | None:
    """解析+消毒: 总≤27, 同点数≤8, 王各≤2; 并拦截幻觉(超量/循环重复)。"""
    if not toks:
        return None
    # —— 幻觉闸门1: 输出远多于应有张数(实测空区域会吐上百个 token) ——
    cap = (expected + 5) if expected else 30
    if len(toks) > max(cap, 30):
        return None
    # —— 幻觉闸门2: 短周期重复(整副牌循环) ——
    if _looks_cyclic(toks):
        return None
    try:
        cards = cards_from_tokens(toks)
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


def blocks_by_seat(img) -> dict:
    """桌面各座位当前牌块: {座位名: (x, y, w, 白像素数)}（无牌则不含该键）。
    用途: 对比相邻两帧 → 哪一家的牌块变了 = 谁刚出牌(用于判定上家是不是队友)。"""
    out = {}
    for name, box, cnt in table_plays(img):
        if name == "bottom":      # bottom 是我方最近出的牌, 不算"别人"
            continue
        pb = out.get(name)
        if pb is None or cnt > pb[3]:
            out[name] = (box[0], box[1], box[2], cnt)
    return out


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
    """我方回合: 手牌白卡够多 **且** 出牌按钮可用。

    仅凭白卡数会在残局误判(手牌仍显示但按钮禁用/非我方回合)。
    """
    return white_count(img) >= thresh and play_button_active(img)


def play_button_active(img) -> bool:
    """出牌按钮是否可用(亮金=可用, 暗金=禁用)。区间实测: x[300,420] y[1090,1150]。

    用途: 残局时手牌仍显示但按钮可能禁用 → 单凭白卡数会把"非我方回合"误判为"我回合"。
    """
    seg = img[1090:1150, 300:420]
    return float(seg[:, :, 1].mean()) > 120.0



WHITE_TURN_MIN = 4000  # 我方回合白卡阈值


def hand_start_x(n: int) -> float:
    """手牌排起点 x(设备像素): 整排居中 = (720 - ((n-1)*24 + 88)) / 2"""
    return (720.0 - ((n - 1) * 24 + 88)) / 2


def card_tap_x(index: int, n: int) -> int:
    """第 index 张手牌的点击 x: 起点(随张数居中变化) + index*24 + 露出区中部(20)"""
    return int(hand_start_x(n) + index * 24 + 20)


def hand_block(img, thr: int = 150, min_col: int = 6):
    """实测我方手牌块的左右边缘(按白卡列轮廓)。取不到返回 (None, None)。"""
    y0, y1 = HAND_BAND
    band = img[y0:y1]
    colsum = (band.min(axis=2) > thr).sum(axis=0)
    xs = np.where(colsum > min_col)[0]
    if len(xs) < 10:
        return None, None
    return int(xs.min()), int(xs.max())


def card_edges(img, y0: int = 805, y1: int = 945, min_gap: int = 10) -> list:
    """手牌带里所有**竖直边界线**的 x(卡与卡的分界)。

    纯像素、与"公式/张数/布局假设"完全无关 —— 这是能迁移到其它游戏(腾讯掼蛋 App/小程序)
    的做法: 任何把牌叠起来画的手牌区, 卡与卡之间都有一条边界线, 找到它就有牌位。
    """
    band = img[y0:y1].mean(axis=2)
    gx = np.abs(np.diff(band, axis=1)).mean(axis=0)
    if gx.size < 20:
        return []
    thr = max(0.35 * float(gx.max()), 1.0)
    peaks: list = []
    for x in range(1, gx.size - 1):
        if gx[x] > thr and gx[x] >= gx[x - 1] and gx[x] > gx[x + 1]:
            if peaks and x - peaks[-1] < min_gap:
                if gx[x] > gx[peaks[-1]]:
                    peaks[-1] = x
            else:
                peaks.append(x)
    return peaks


def card_positions_by_edges(img, n_hint: int = 0) -> list:
    """每张牌的可点 x = **实测卡边界** 规整化后的"左缘 + 半间距"。

    做法: 找边界 → 用相邻间距中位数当 pitch(抗噪) → 以首条边界为起点按 pitch 生成,
    误检的边界自然被剔除。返回空 = 边界不可用(交给上层回落)。
    n_hint 只用于日志/一致性参考, 不参与计算(边界是实测的, 比读数可信)。
    """
    ps = card_edges(img)
    if len(ps) < 2:
        return []
    diffs = sorted(b - a for a, b in zip(ps, ps[1:]) if 8 <= (b - a) <= 120)
    if not diffs:
        return []
    pitch = diffs[len(diffs) // 2]
    # 只用"与 pitch 一致"的边界(逐条滤掉误检/末张宽边), 每条边界 = 一张牌的左缘
    keep = [ps[0]]
    for b in ps[1:]:
        if abs((b - keep[-1]) - pitch) <= max(4.0, pitch * 0.35):
            keep.append(b)
    if not (1 <= len(keep) <= 30):
        return []
    return [int(round(x + pitch / 2)) for x in keep]


def card_positions(img, n: int, pitch: float = 24.0) -> list:
    """每张手牌的可点 x 坐标(**实测**, 与"张数"读数解耦)。

    背景(2026-09-15 实测): 公式 hand_start_x(n) 依赖上游读到的张数, VLM 多读/少读
    1 张 → 整排平移 12px+ → 点到邻牌 → 选出的牌型非法 → 游戏忽略"出牌"按钮
    (表现就是"点选失败/点了没反应")。实测: 手牌块左缘=78, 公式在 n=21 时=76 ✓,
    n=22 时=64 ✗(差 14px), n=17 时=124 ✗(差 46px)。
    左缘实测 + 固定间距(源码: 每张露出 24px, 末张 88px) → 与张数无关 ⇒ 稳。
    """
    pe = card_positions_by_edges(img, n)                 # ① 首选: 卡边界实测(与假设无关)
    if pe:
        return pe
    xl, xr = hand_block(img)
    if xl is None:
        return [card_tap_x(i, n) for i in range(n)]      # ③ 取不到 → 回落公式
    p = float(pitch)                                     # 源码常量(24px/张), 与"张数"读数无关
    if n > 1 and xl + (n - 1) * p + 88.0 > xr + 24:      # 整排溢出实测右缘 = 上游张数偏高
        est = (xr - xl - 88.0) / (n - 1)                 # 才用右缘反推
        if 16.0 <= est <= 40.0:
            p = est
    return [int(round(xl + i * p + p / 2)) for i in range(n)]


def hand_card_count_est(img, pitch: float = 24.0, last_w: float = 88.0) -> int:
    """从手牌块**实测宽度**反推张数 —— 不依赖 VLM 的独立真值。

    源码布局: 整排宽 = (n-1)*24 + 88 且居中。实测块宽 W → n ≈ (W-88)/24 + 1。
    实测(2026-09-15): 块 78..642 = 564 宽 → 21 张 ✓ (而 hand_columns 像素分段只有 17 ✗,
    VLM 也会偶尔少读)。用途: 当读牌的"期望张数"和一致性闸门。
    """
    xl, xr = hand_block(img)
    if xl is None:
        return 0
    w = float(xr - xl)
    if w < 60:
        return 0
    return max(1, int(round((w - last_w) / pitch)) + 1)


def card_edge_count(img, min_gap: int = 12) -> int:
    """手牌带**竖直边缘**(卡与卡的边界线)计数 + 1 → 张数的独立估计。

    与"块宽反推"和"VLM 读数"互相独立: 真手牌每张露出 24px, 边界线等距可数;
    开始界面的大片白区没有这种周期性结构(实测 边缘=3 vs 块宽推 23)。
    """
    y0, y1 = HAND_BAND
    gray = img[y0:y1].mean(axis=2)
    gx = np.abs(np.diff(gray, axis=1)).mean(axis=0)
    if gx.size == 0 or gx.max() <= 0:
        return 0
    thr = 0.45 * float(gx.max())
    peaks: list = []
    for x in range(1, gx.size - 1):
        if gx[x] > thr and gx[x] >= gx[x - 1] and gx[x] > gx[x + 1]:
            if not peaks or x - peaks[-1] >= min_gap:
                peaks.append(x)
            elif gx[x] > gx[peaks[-1]]:
                peaks[-1] = x
    return len(peaks) + 1 if peaks else 0


def hand_is_real(img, tol: int = 2):
    """手牌带是否真是"局内我方手牌": 块宽反推张数 与 边缘计数 是否自洽。

    返回 (bool, info)。实测: 开始界面白区 推23 vs 边缘3(差20) → 假 ✓;
    真手牌(27 张满手) 两者一致 ✓。用途: 挡掉"对着开始界面空转"。
    """
    xl, xr = hand_block(img)
    n_est = hand_card_count_est(img)
    ne = card_edge_count(img)
    info = {"block": (xl, xr), "n_est": n_est, "n_edges": ne, "diff": abs(n_est - ne)}
    if xl is None or n_est < 1 or ne < 1:
        return False, info
    return abs(n_est - ne) <= tol, info


def selected_columns(img, y0: int = 776, y1: int = 802) -> list:
    """当前**已抬起(选中)**的牌位 x —— 绝对测量, 不是帧差。

    原理: 选中的牌整张上移 → 手牌带正上方的窄带里会出现这些牌的卡面/边界。
    用同一套"卡边界"检测读这条带, 就能知道"现在到底选中了哪几张"。
    用途: 按组点选循环 —— 每次点击后据此判断"选中/取消", 而不是靠猜。
    """
    sub = img[y0:y1]
    ps = card_edges(sub, y0=0, y1=sub.shape[0])
    if len(ps) < 1:
        # 边界不行就退化为"白卡列段"
        colsum = (sub.min(axis=2) > 150).sum(axis=0)
        xs = np.where(colsum > 3)[0]
        if len(xs) == 0:
            return []
        runs, st, prev = [], int(xs[0]), int(xs[0])
        for x in xs[1:]:
            x = int(x)
            if x - prev > 6:
                runs.append((st, prev))
                st = x
            prev = x
        runs.append((st, prev))
        return [int((u + v) / 2) for u, v in runs if v - u >= 4]
    diffs = sorted(b - a for a, b in zip(ps, ps[1:]) if 8 <= (b - a) <= 120)
    if not diffs:
        return [int(x + 12) for x in ps]
    pitch = diffs[len(diffs) // 2]
    keep = [ps[0]]
    for b in ps[1:]:
        if abs((b - keep[-1]) - pitch) <= max(4.0, pitch * 0.35):
            keep.append(b)
    return [int(x + pitch / 2) for x in keep]


def lifted_columns(before, after, y0: int = 776, y1: int = 802,
                   min_px: int = 3, gap: int = 6) -> list:
    """帧差定位"刚被抬起的是哪几张牌" → 返回变化列段中心 x 列表。

    原理: 选中的牌整张上移, 手牌带**上方那条带**(默认 y756-806)从"无牌"变"有牌";
    未选中的牌不动。用途: 身份校验 —— 点选后核对"抬起的 x" 是不是"想点的 x"。
    实测: 点"提示"钮选牌 → 该带变化 23k 像素; 点到空地 → 0 像素。
    ⚠️ 带的 y 范围必须紧贴手牌带**正上方**(约 25px): 取太宽(如 756-806)会混进桌面
    牌堆区, 产生"总停在同一列"的幻影(实测 599), 把正确的点选误判成点偏。
    """
    if before is None or after is None:
        return []
    b = before[y0:y1].astype(int)
    a = after[y0:y1].astype(int)
    d = np.abs(a - b).sum(axis=2) > 60
    colsum = d.sum(axis=0)
    xs = np.where(colsum > min_px)[0]
    if len(xs) == 0:
        return []
    runs = []
    st = prev = int(xs[0])
    for x in xs[1:]:
        x = int(x)
        if x - prev > gap:
            runs.append((st, prev))
            st = x
        prev = x
    runs.append((st, prev))
    return [(int((u + v) / 2), v - u + 1) for u, v in runs if (v - u + 1) >= 4]


def hand_columns(img) -> int:
    """像素数手牌张数: 手牌带亮列分段数(仅计宽度≥8px 的段, 滤噪声)"""
    y0, y1 = HAND_BAND
    band = img[y0:y1]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    colsum = ((b > 200) & (g > 200) & (r > 200)).sum(axis=0)
    runs = 0
    st = None
    for x in range(len(colsum)):
        v = colsum[x] > 10
        if v and st is None:
            st = x
        elif not v and st is not None:
            if x - st >= 8:  # 宽度≥8 才算一张牌(滤 1-2px 噪声/阴影)
                runs += 1
            st = None
    if st is not None and len(colsum) - st >= 8:
        runs += 1
    return runs


def lifted_px(img) -> int:
    """选中牌抬起后的亮带宽度(y770-812: 选中牌上移36px后露出)"""
    band = img[770:812]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    return int(((b > 200) & (g > 200) & (r > 200)).sum())


PROMPT_SETTLE = (
    "这是掼蛋结算弹窗。只回答两行: 头游=<谁(我方是南/北, 对手是西/东)>; 我方是否升级=<是/否>。不要解释。"
)


def read_settle(rec, img) -> tuple[str, bool | None]:
    """读结算弹窗 → (原文, 我方是否升级)。

    优先**无障碍文字**(免 VLM, 快且准); 取不到再落 VLM 读图。
    """
    try:
        from ..platform.a11y import A11y

        blob = A11y().text_blob(force=True).replace("&#10;", "\n").replace("<br>", "\n")
        if "头游" in blob:
            import re as _re

            # 分隔符实测有 ':' '：' '=' 三种(踩坑: 只认冒号 → 62 局判成"未判定", A/B 数据白丢)
            m = _re.search(r"头游\s*[:：=]\s*([东南西北])", blob)
            head = m.group(1) if m else ""
            win = True if head in ("南", "北") else (False if head in ("东", "西") else None)
            if win is None:      # 另一种文案: "我方是否升级=是/否"
                mm = _re.search(r"我方是否升级\s*[:：=]\s*(是|否)", blob)
                if mm:
                    win = mm.group(1) == "是"
            m2 = _re.search(r"升级\s*[:：=]?\s*([+\-]?\d+\s*级)", blob)
            up = m2.group(1) if m2 else ""
            return (f"头游={head}; 升级={up}; 我方升级={'是' if win else '否' if win is False else '?'}", win)
    except Exception:  # noqa: BLE001
        pass
    roi = img[300:900, 30:690]
    txt = rec.recognize_with_vlm(roi, PROMPT_SETTLE) or ""
    win = None
    if "头游" in txt:
        if any(k in txt for k in ("南", "北", "你", "队友")):
            win = True
        elif any(k in txt for k in ("西", "东")):
            win = False
    return txt, win


def page_looks_ok(img) -> bool:
    """页面是否处于正常牌桌状态(用于识别白屏/异常, 防空转)。

    判据: ① 手牌带白卡在合理范围(27 张≈66k, 超 80k 视为异常白屏)
          ② 牌桌中部不是整片白(正常为深绿台面)
    """
    try:
        if white_count(img) > 110000:   # 27 张≈66k; 放宽以容忍发牌/动画帧
            return False
        seg = img[300:700, 60:660]
        if seg is None or seg.size == 0:
            return False
        b, g, r = (float(seg[:, :, i].mean()) for i in range(3))
        if r > 200 and g > 200 and b > 200:   # 中部"整片纯白"才算白屏(更严)
            return False
    except Exception:  # noqa: BLE001
        return True
    return True
