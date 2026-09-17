"""掼蛋视觉感知层: 手牌(切半读+拼接) / 桌面待压牌 / 轮次判定。

坐标基于实测(720x1280, dpr2): 手牌带 y[805,945]; 左半 x[0,370], 右半 x[350,720]
"""
from __future__ import annotations

import cv2
import numpy as np

from .rules import Card, cards_from_tokens

HAND_BAND = (695, 825)
# 手牌行最左边是"你"字小框(浅绿), 它不是牌 → 读牌时从它右边开始
# (实测 2026-09-16: 不裁会把"你"读成一张 8 并盖住第一张牌; 裁 20~65px 都能读全)
HAND_X_PAD = 26   # 实测(2026-09-16 720x1280 掼蛋): 牌面 y≈695..825, 130px 高
SPLITS = [(0, 370), (350, 720)]

PROMPT_HAND = (
    # 2026-09-16 修正: 旧提示词写"每张只露出左上角" → 与本界面(整张可见)不符 ✗
    # → 模型把最左边"你"字小框也当成一张半露的牌(读成 8)、王也读错。
    # 用实测验证过的说法(真值对照: 9 张里 8 张逐张一致 ✓)
    "图里是一排掼蛋扑克牌(最左边的小方框不是牌,请忽略)。"
    "先数一共有几张,再按从左到右列出每张的**点数**,空格分隔,不要解释,不要合并重复。"
    "格式示例: 共9张 | 3 9 10 J Q K A A A 小王。"
    "10 写 10,J/Q/K/A 照写,小王写小王,大王写大王。"
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
    """切牌 token。逗号/顿号/**空白**都当分隔符(实测 2026-09-16: 模型常按空格输出,
    只按逗号切会整句当一个 token → 全被丢掉 ✗)。"""
    import re as _re

    norm = txt.replace("，", ",").replace("、", ",")
    parts = [x for x in _re.split(r"[,\s]+", norm) if x.strip()]
    return [_norm_token(t) for t in parts]


def read_seat_panels(rec, img) -> dict:
    """读四家的**状态面板**(界面直接写着: 座位名 / 张数 / 级牌)。

    实测(2026-09-16 掼蛋, 720x1280): VLM 一次读上半屏 → 稳定得到
        北(队友) 27张 打A / 西 27张 打A / 东 27张 打A
    比"用 27−已出 推算余牌"更直接、更准(而且界面自己标了"队友")。
    返回: {"panels": {座位: {"left": 张数, "level": "A"}}, "level": "A", "raw": 原文}
    """
    y0, y1 = 90, 430
    try:
        txt = _read(rec, img[y0:y1], "读出图中所有文字（面板上的座位名、张数、级牌等），按行原样输出，不要解释")
    except Exception:  # noqa: BLE001
        return {"panels": {}, "level": "", "raw": ""}
    import re
    raw = txt or ""
    panels: dict = {}
    seat = None
    level = ""
    for line in [l.strip() for l in raw.splitlines() if l.strip()]:
        m = re.search(r"(北|西|东|南|上家|下家|对家)", line)
        if m:
            seat = m.group(1)
            if seat not in panels:
                panels[seat] = {}
        m2 = re.search(r"(\d{1,2})\s*张", line)
        if m2 and seat:
            panels[seat]["left"] = int(m2.group(1))
        m3 = re.search(r"打\s*([2-9AJQK]|10)", line)
        if m3:
            level = m3.group(1)
            if seat:
                panels[seat]["level"] = level
    return {"panels": panels, "level": level, "raw": raw}



def _tpl_dir() -> str:
    import os as _os

    root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
    return _os.getenv("TPL_DIR", _os.path.join(root, "data", "templates"))



def load_templates_sr(d: str | None = None) -> dict:
    """加载"花色+点数"模板库: 目录下 *.npy, 文件名 <花色>_<点数>_<序号>.npy。"""
    import os as _os
    # 两个目录都读: 花色+点数(参考图标注) + 点数级(实时真值采集) ✓
    root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), "..", "..", "..", "data"))
    dirs = [d] if d else [_os.path.join(root, "templates_sr"), _os.path.join(root, "templates_rank")]
    bank: dict = {}
    files = []
    for dd in dirs:
        dd = _os.path.abspath(dd)
        if _os.path.isdir(dd):
            files += [_os.path.join(dd, fn) for fn in _os.listdir(dd)]
    for full in files:
        fn = _os.path.basename(full)
        if not fn.endswith(".npy"):
            continue
        # key 取**前两段**(花色_点数): 文件名形如 <花色>_<点数>_<序号>.npy
        # (实时采集的是 0_<点数>_<样本>_<x>.npy → 前两段仍是 0_<点数> ✓)
        parts = fn[:-4].split("_")
        if len(parts) < 2:
            continue
        k = f"{parts[0]}_{parts[1]}"
        try:
            bank.setdefault(k, []).append(np.load(full))
        except Exception:
            continue
    return bank


def tm_read_hand(img, tpl: dict | None = None, max_dist: float = 0.6, templates_dir: str | None = None):
    """**模板匹配**读手牌(纯像素, 不调模型)。

    做法: 实测手牌带 → 实测牌位(卡边界+占用范围) → 裁每张牌露出的**整条竖条**(宽24)
    → 归一化后与模板库比 → 最近者即"花色+点数"。

    实测(2026-09-16): 用户标注的 27 张满手图上 54 类模板库自校验 **27/27 = 100%** ✓✓
    (VLM 只有 64~68% ✗, 且错误是结构性的: 遮挡/王渲染/)

    返回 (list[(花色1-4, 点数2-16, x)], info); 花色: 1♠ 2♣ 3♥ 4♦; 点数 11=J 12=Q 13=K 14=A 15小王 16大王
    """
    tpl = load_templates_norm(templates_dir) if tpl is None else tpl   # 已预归一化 ✓
    info = {"n_slot": 0, "unknown": 0, "max_dist": 0.0, "tpl": len(tpl)}
    if not tpl:
        return [], info
    y0, y1 = hand_band_measured(img)
    xs = card_slots(img, y0, y1)
    out = []
    card_h = y1 - y0 - 16                     # 一条竖条的标准高度(与模板一致)
    for x in xs:
        x0 = max(0, int(x))
        ty = card_top_y(img, x0, y0 + 8)      # 逐牌对准: 用**该牌自己的顶边** ✓
        patch = img[ty + 8:ty + 8 + card_h, x0:x0 + 24]   # +8 与模板采集时一致 ✓
        if patch.size == 0 or patch.shape[0] < 10:
            continue
        if float(patch.std()) < 10.0:            # 纯色块(如"你"字小框)不是牌
            info["unknown"] += 1
            continue
        if float(patch.mean()) < 120:            # 暗的也不是牌(桌面绿 ~59 / 底部标签条 ~40)
            info["unknown"] += 1               # 实测: 右侧"打A"标签区的峰会被误当牌位 ✗
            continue
        a = norm_patch(patch)
        # ① **点数**: 全场取最小距离(花色级/点数级都参与 —— 本局自采的模板距离≈0.000 天然胜出)
        best_k, best_d = None, 1e18
        for k, arrs in tpl.items():
            for b in arrs:                      # arrs 已归一化 ✓
                if b.shape != a.shape:
                    continue
                d = float(np.mean(np.abs(a - b)))
                if d < best_d:
                    best_d, best_k = d, k
        # ② **花色**: 只在"胜出点数"的花色级模板里再确认一次; 无可信候选 → 未知(0) ✓
        #    (审查员实证: suit=0/hua=None 交给决策层会导致"同花顺误判 + 红桃逢人配认不出")
        if best_k is not None:
            _rk = best_k.split("_")[1]
            if best_k.startswith("0_"):
                suit, sd = 0, 1e18
                for k2, arrs in tpl.items():
                    if k2.startswith("0_") or k2.split("_")[1] != _rk:
                        continue
                    for b in arrs:
                        if b.shape != a.shape:
                            continue
                        d = float(np.mean(np.abs(a - b)))
                        if d < sd:
                            sd, suit = d, int(k2.split("_")[0])
                if sd > max_dist:               # 花色级也没有可信候选 → 花色未知, 不瞎猜 ✓
                    suit = 0
            else:
                suit = int(best_k.split("_")[0])
            best_k = f"{suit}_{_rk}"
        if best_k is None or best_d > max_dist:  # 不像任何已知牌 → 丢掉该位(不算一张)
            info["unknown"] += 1
            continue
        suit, rank = (int(v) for v in best_k.split("_"))
        out.append((suit, rank, x0))
        info["max_dist"] = max(info["max_dist"], round(best_d, 3))
    info["n_slot"] = len(out)
    info["keys"] = sorted(tpl)
    return out, info
def _parse_hand_text(raw: str, expected: int = 0) -> list:
    """VLM 原始文本 → 牌 token 列表。

    实测输出形如 '共9张 | 3 A A A Q J 10 9 3' 或 '8\nA A A 6 J 10 Q 2'
    —— 前面常带一行"张数", 后面才是牌 ✗。
    做法: 正则扫出所有像牌的点数/王 → **从后往前取 expected 个**(张数行在前, 天然丢弃 ✓)
    """
    import re as _re

    core = _re.sub(r"共\s*\d+\s*张", " ", raw)
    toks = _re.findall(r"大王|小王|(?:10|[2-9AJQK])(?![0-9A-Za-z])", core)
    if expected and len(toks) > expected:
        toks = toks[-expected:]
    return toks


def _vote_tokens(cands: list) -> list:
    """多采样投票: 按位置取多数(样本长度不一时以最长者为骨架)。"""
    if not cands:
        return []
    if len(cands) == 1:
        return cands[0]
    base = max(cands, key=len)
    return [max(set([c[i] for c in cands if i < len(c)]), key=[c[i] for c in cands if i < len(c)].count)
            for i in range(len(base))]


def _fix_last_card(rec, img, y0: int, y1: int, got: list) -> None:
    """定点复读**最右那张**牌(就地修正 got)。

    为什么: 掼蛋按点数升序排, **大小王排在最后** → 而模型常把王读成 3 ✗
    (实测 2026-09-16: 同一手 9 张, 中间 7 张全对, 只有最右的王读成 3)。
    做法: 用卡边界实测拿到最后一张的 x 区间 → 单独问一句"是不是王" → 是就替换。
    """
    try:
        peaks = card_edges(img, y0, y1)
        if len(peaks) < 2 or not got:
            return
        x_last = peaks[-1]
        x_prev = peaks[-2]
        pad = max(30, (x_last - x_prev) // 2)
        x0 = max(0, x_last - pad)
        x1 = min(img.shape[1], x_last + pad + 20)
        crop = img[max(0, y0 - 6):y1 + 6, x0:x1]
        txt = _read(rec, crop, "这一张扑克牌是: 小王、大王、还是普通点数(2-10/J/Q/K/A)? 只回一个答案, 不要解释")
        t = (txt or "").strip()
        z = None
        if "小王" in t:
            z = 15
        elif "大王" in t:
            z = 16
        if z is None:
            return
        # 替换最后一个 token(旧的是误读) —— 用 zhi 值构造, 与 _norm_token 口径一致
        name = "小王" if z == 15 else "大王"
        if got and str(got[-1]) not in ("小王", "大王"):
            got[-1] = name
    except Exception:  # noqa: BLE001
        return


def read_hand_ordered(rec, img, expected: int = 0) -> list[Card] | None:
    """读手牌: ≤14 张整排直读; 更多则切两半拼接。expected>0 时提示词注入张数。"""
    y0, y1 = hand_band_measured(img)   # 读取也用**实测**带(与探测一致)
    prompt = PROMPT_HAND + (f" 这一排共 {expected} 张。" if expected > 0 else "")
    # 先**整排直读**: 实测(2026-09-16, 27 张满手)一次读全 ✓✓;
    # 旧的"一律切两半"会在每半注入"共27张"→ 模型输出跑偏 → 读出 0 张 ✗
    # 三次采样投票(实测: VLM 单次输出格式/内容抖动大 ✗ → 投票最稳)
    cand_toks = []
    for _i in range(3):
        raw = _read(rec, img[y0:y1, HAND_X_PAD:, :], prompt) or ""
        toks_i = _parse_hand_text(raw, expected)
        if toks_i:
            cand_toks.append(toks_i)
    toks = _vote_tokens(cand_toks) if cand_toks else []
    if toks:
        exp2 = expected                   # 模型自报张数不可靠(实测常少报) → 用期望值清洗
        got = _sanitize(toks, exp2)
        if got and (not expected or len(got) >= expected - 1):
            _fix_last_card(rec, img, y0, y1, got)   # 定点复读最右那张(王常被读错)
            return got
    if expected and expected <= 14:                # ≤14 张: 整排读不行就直接返回
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
    y0, y1 = hand_band_measured(img)   # 读取也用**实测**带(与探测一致)
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
    y0, y1 = hand_band_measured(img)   # 读取也用**实测**带(与探测一致)
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
    # 区域**自适应**(2026-09-16 修): 原来写死 y1=820, 界面布局下移后出牌区落到区域外
    # → 一个出牌事件都记不到 ✗。改为: 下界 = 实测手牌带顶边之上一点(= 出牌区底), 上界 = 面板下方。
    hy0, _hy1 = hand_band_measured(img)
    x0, y0, x1, y1 = 0, 430, img.shape[1], max(560, int(hy0) - 4)
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
            # 座位判定也随实测走(不再写死 620/300/420/480)
            if cy > int(hy0) - 90:          # 紧贴手牌上方 = 我方最近出的牌
                name = "bottom"
            elif cx < img.shape[1] * 0.42:
                name = "left"
            elif cx > img.shape[1] * 0.58:
                name = "right"
            elif cy < y0 + 110:
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
    y0, y1 = hand_band_measured(img)   # 实测带(原来用死常量 → 布局下移后数在空白区 → my_turn 恒 False ✗)
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


def hand_band_measured(img, y_lo: int = 600, y_hi: int = 1120) -> tuple:
    """**实测**手牌带 y 范围: 找"牌面行"。

    牌面行的两个特征(2026-09-16 用 ASCII 能量图实证):
      ① **竖直边缘能量高**(每张牌的左右边界 + 点数花色笔画)
      ② **白占比高**(牌是白底)
    实测(720x1280 掼蛋): 牌面 y≈810..935, x≈180..420 —— 而之前写死/取最大白段
    都圈到了**牌上方约 115px 的空白区** ✗ → 峰全杂 → 读牌全错。
    """
    g = img.mean(axis=2)
    dx = np.abs(np.diff(g, axis=1))
    energy = dx.mean(axis=1)
    white = (g > 200).mean(axis=1)
    lo, hi = max(0, y_lo), min(len(energy), y_hi)
    if hi - lo < 40:
        return HAND_BAND
    seg = energy[lo:hi]
    e_thr = max(1.5, float(np.percentile(seg, 75)))
    rows = [y for y in range(lo, hi) if energy[y] > e_thr and white[y] > 0.06]
    if not rows:
        return HAND_BAND
    best = (rows[0], rows[0]); s0 = prev = rows[0]
    for y in rows[1:]:
        if y - prev <= 6:
            prev = y
        else:
            if prev - s0 > best[1] - best[0]:
                best = (s0, prev)
            s0 = prev = y
    if prev - s0 > best[1] - best[0]:
        best = (s0, prev)
    return best if best[1] - best[0] >= 40 else HAND_BAND



def band_ink_ratio(img, band=None) -> float:
    """手牌带里"牌面内容"占比(非纯白、非纯黑 = 点数/花色/边框)。

    用来挡"大白区被当手牌": 真手牌带实测墨占比 ≈0.15~0.35(上半有字、下半是白底);
    空白/蒙版区 ≈0 → 拒掉。教训(2026-09-16): 光靠边缘规整性会把开始界面的大白块
    也数成 ~25 张 ✗。
    """
    y0, y1 = band if band else hand_band_measured(img)
    g = img[y0:y1].mean(axis=2)
    return float(((g < 205) & (g > 40)).mean())



NORM_H, NORM_W = 96, 24          # 归一化统一尺寸(消除 1 像素高度差)



def card_top_y(img, x: int, y_guess: int, span: int = 60, need: int = 6,
               bright: int = 150) -> int:
    """找某个牌位的**牌面顶边**(逐牌对准: 抬起/不抬起都能定位 ✓)。

    做法: 在 x..x+24 这一列带里, 从 y_guess-span 往下扫, 第一行亮像素 >= need 的行即顶边;
    找不到就返回 y_guess(退化为原行为)。
    实测(2026-09-17): 未选中顶边≈815, 选中(抬起)≈779 —— 差 36px, 正是误读的根源。
    """
    x0 = max(0, int(x))
    x1 = min(img.shape[1], x0 + 24)
    y_from = max(0, int(y_guess) - span)
    y_to = min(img.shape[0], int(y_guess) + span)
    if x1 <= x0 or y_to <= y_from:
        return int(y_guess)
    col = img[y_from:y_to, x0:x1]
    rows = (col.min(axis=2) > bright).sum(axis=1)
    for i, v in enumerate(rows):
        if v >= need:
            return y_from + i
    return int(y_guess)


_TPL_NORM_CACHE: dict = {}      # 模块级缓存: key → {花色_点数: [归一化后的 ndarray, ...]}


def load_templates_norm(d: str | None = None) -> dict:
    """**归一化后的**模板库(进程内构建一次)。

    为什么: 审查员实测 —— 每帧从磁盘读 459 个 .npy(≈45ms) 且对每个槽位把全部模板
    重新归一化(12420 次 ≈ 974ms) ✗ → 预归一化后整次读牌 ≈ 33ms(24 倍) ✓
    采样工具新增模板后需 `clear_templates_cache()` 才能看到新样本 ✓
    """
    import os as _os
    key = _os.path.abspath(d) if d else "__default__"
    hit = _TPL_NORM_CACHE.get(key)
    if hit is not None:
        return hit
    raw = load_templates_sr(d)
    norm = {k: [norm_patch(a) for a in arrs] for k, arrs in raw.items()}
    _TPL_NORM_CACHE[key] = norm
    return norm


def clear_templates_cache() -> None:
    """清空模板缓存(采集器写盘后调用 ✓)。"""
    _TPL_NORM_CACHE.clear()

def norm_patch(p: "np.ndarray") -> "np.ndarray":
    """把牌面竖条归一化(灰度 + 去均值/除标准差)。

    为什么要归一化: 模板可能采自 JPEG(用户发来的截图) 或 PNG(设备实时帧),
    两者压缩/亮度有细差 → 直接比像素会全超阈值 ✗; 归一化后差异被抹平 ✓
    """
    g = cv2.cvtColor(p, cv2.COLOR_RGB2GRAY).astype("float32")
    # ⚠️ 实测(2026-09-16): 实时帧与截图的牌条高度会差 1 像素(104 vs 105) →
    # 形状不等就 continue 会让**全部比对被跳过**(距离恒为 1e18, 一张都读不出) ✗
    # → 归一化前统一到固定尺寸(NORM_H x NORM_W)
    g = cv2.resize(g, (NORM_W, NORM_H), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    g = g - g.mean()
    sd = g.std()
    return g / sd if sd > 1e-6 else g


def card_slots(img, y0: int | None = None, y1: int | None = None, pitch_fallback: float = 24.0):
    """**实测牌位**: 卡边界峰 → 牌距+相位 → 用"手牌实际横向占用"限定, 给出每张牌的左缘 x。

    教训(2026-09-16): 为补首张而往左一直外推, 在实时帧上把 9 张牌推成 21 个位 ✗
    → 改成用白占比高的连续段圈定横范围, 只在该范围内布点 ✓
    """
    if y0 is None or y1 is None:
        y0, y1 = hand_band_measured(img)
    peaks = [int(x) for x in card_edges(img, y0, y1)]
    if not peaks:
        return []
    # 手牌横向占用: 牌面是白的, 桌面/背景不是
    sub = img[y0 + 6:y1 - 6]
    white = (sub.min(axis=2) > 150).mean(axis=0)
    cols = np.where(white > 0.40)[0]
    if len(cols) < 5:
        return peaks
    x_lo, x_hi = int(cols[0]), int(cols[-1])
    pitch = pitch_fallback
    if len(peaks) >= 3:
        gaps = np.diff(peaks)
        good = gaps[(gaps >= 18) & (gaps <= 32)]
        if len(good):
            pitch = float(np.median(good))
    # 先找**最长等距串** = 真正的一排牌(实测: 9 张牌给 9 峰, 右侧"打A"等杂峰被排除 ✓)
    best_chain: list = []
    for i in range(len(peaks)):
        chain = [peaks[i]]
        for j in range(i + 1, len(peaks)):
            if abs((peaks[j] - chain[-1]) - pitch) <= max(3.0, pitch * 0.18):
                chain.append(peaks[j])
        if len(chain) > len(best_chain):
            best_chain = chain
    if len(best_chain) < 2:
        return peaks
    lo, hi = best_chain[0], best_chain[-1]
    # 两端按"是不是牌面(白占比高)"补格, 最多各 2 格(实测: 满手图首尾各缺 1 格 ✓)
    def card_like(x: float) -> bool:
        x = int(round(x))
        if x < 0 or x + 8 >= img.shape[1]:
            return False
        col = img[y0 + 8:y1 - 8, x:x + 8].reshape(-1, 3).astype(int)
        # 判"是不是牌面"用**亮度**(牌面亮, 桌面绿/底部标签条都暗):
        # 实测(2026-09-16) 三代判据的教训:
        #   ①"是否白" → 大小王/黄边级牌不是白的 → 误杀 ✗
        #   ②"是否桌面绿" → 底部黑色标签条不是绿的 → 漏进 2 格 ✗
        #   ③ 亮度 → 牌面 ~180, 桌面绿 ~59, 标签条 ~40 → 一刀切 ✓
        return bool(col.mean() > 120)
    k = 0
    while k < 2 and card_like(lo - pitch * (k + 1)) and (lo - pitch * (k + 1)) >= x_lo - pitch:
        k += 1
    lo = lo - pitch * k
    # ★ 右边**不外扩**(2026-09-17 实测): 最右那张牌是**完整可见**的 → 它的左缘必然被峰检测到
    #   → 再往右扩出来的都是"牌外的亮区"(实测满手 27 张被扩成 29 个位 ✗, 且那两格亮度也够高,
    #     靠亮度/边缘都筛不掉 ✗) → 干脆不扩 ✓
    n = int(round((hi - lo) / pitch)) + 1
    return [int(round(lo + i * pitch)) for i in range(n)]

def card_edges(img, y0: int = 0, y1: int = 0, min_gap: int = 10,
               q: float = 0.93, floor: float = 4.0) -> list:
    """手牌带里所有**竖直边界线**的 x(卡与卡的分界)。

    纯像素、与"公式/张数/布局假设"完全无关 —— 这是能迁移到其它游戏(腾讯掼蛋 App/小程序)
    的做法: 任何把牌叠起来画的手牌区, 卡与卡之间都有一条边界线, 找到它就有牌位。
    """
    if not y0 or not y1:                      # 默认: 实测手牌带(不再用死常量)
        y0, y1 = hand_band_measured(img)
    band = img[y0:y1].mean(axis=2)
    gx = np.abs(np.diff(band, axis=1)).mean(axis=0)
    if gx.size < 20:
        return []
    # 阈值: 分位(自适应) + 中位数下限 + 绝对下限 ——
    # 实测(2026-09-16, 真值 27 张): 旧的 0.35*max 只数出 8~15 个 ✗; 分位 0.93 数出 27 ✓✓
    thr = max(float(np.quantile(gx, q)), float(np.median(gx)) + 1.0, float(floor))
    peaks: list = []
    for x in range(1, gx.size - 1):
        if gx[x] > thr and gx[x] >= gx[x - 1] and gx[x] > gx[x + 1]:
            if peaks and x - peaks[-1] < min_gap:
                if gx[x] > gx[peaks[-1]]:
                    peaks[-1] = x
            else:
                peaks.append(x)
    # 去重: 用**峰间距中位数**(实测牌距)当尺子, 丢掉过近的离群峰
    if len(peaks) >= 5:
        gaps = np.diff(peaks)
        med = float(np.median(gaps))
        if med > 0:
            keep = [peaks[0]]
            for x in peaks[1:]:
                if x - keep[-1] < 0.55 * med:
                    continue
                keep.append(x)
            peaks = keep
    return peaks


def edges_regular(peaks) -> tuple:
    """边界是否**等距规整**(真手牌每张露一截 → 等距; 大片白区噪声 → 不等距)。

    返回 (bool, info)。真值标定(27 张): 中位间距 ≈24px, 规整度 ≈1.0。
    """
    if len(peaks) < 4:
        return False, {"n": len(peaks), "why": "峰太少"}
    gaps = np.diff(np.asarray(peaks, dtype=float))
    med = float(np.median(gaps))
    ok_range = 12.0 <= med <= 46.0
    within = float(np.mean(np.abs(gaps - med) <= max(3.0, 0.25 * med)))
    return (ok_range and within >= 0.7), {"n": len(peaks), "median_gap": round(med, 1),
                                          "regular": round(within, 2), "pitch_ok": ok_range}


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
    ink = band_ink_ratio(img)
    if ink < 0.03:                   # 几乎没有牌面内容 = 白区/蒙版 → 不是手牌
        return 0
    peaks = card_edges(img, min_gap=min_gap)
    ok, info = edges_regular(peaks)
    if not ok:
        return 0                     # 不等距 = 不是手牌(白区/动画) → 0 张
    return len(peaks)                # 峰 = 每张牌的左缘 → 直接就是张数


def hand_is_real(img, tol: int = 2):
    """手牌带是否真是"局内我方手牌": 块宽反推张数 与 边缘计数 是否自洽。

    返回 (bool, info)。实测: 开始界面白区 推23 vs 边缘3(差20) → 假 ✓;
    真手牌(27 张满手) 两者一致 ✓。用途: 挡掉"对着开始界面空转"。
    """
    xl, xr = hand_block(img)
    n_est = hand_card_count_est(img)
    ne = card_edge_count(img)
    ink = band_ink_ratio(img)
    info = {"block": (xl, xr), "n_est": n_est, "n_edges": ne, "diff": abs(n_est - ne),
            "ink": round(ink, 3)}
    if ink < 0.03:                   # 白区/蒙版 → 不是手牌
        return False, info
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



def lifted_xs(img, y0: int | None = None, up: int = 44, min_px: int = 8,
              bright: int = 200) -> list:
    """定位**被抬起的牌** → 返回它们的 x 区间中心列表。

    原理: 选中的牌整张上移(实测约 36px) → 在手牌带**上方**露出该牌面(亮色);
    未选中的牌不会。逐列统计"带上方亮像素数"即可得到抬起牌的 x 范围 ✓
    (用途: 读牌前"点掉残留选中"; 也用于身份校验"抬起的 x 是不是我们想点的 x")
    """
    if y0 is None:
        y0, _ = hand_band_measured(img)
    a = max(0, int(y0) - up)
    b = max(a + 1, int(y0) - 4)
    band = img[a:b]
    if band.size == 0:
        return []
    cols = (band.min(axis=2) > bright).sum(axis=0)
    xs = np.where(cols >= min_px)[0]
    if len(xs) == 0:
        return []
    out, st_, prev = [], int(xs[0]), int(xs[0])
    for x in xs[1:]:
        x = int(x)
        if x - prev > 6:
            if prev - st_ >= 6:
                out.append(int((st_ + prev) / 2))
            st_ = x
        prev = x
    if prev - st_ >= 6:
        out.append(int((st_ + prev) / 2))
    # 只保留**落在手牌横向范围内**的（实测会混进左侧背景的亮点 ✗）
    try:
        xs_all = card_slots(img)
        if len(xs_all) >= 2:
            lo, hi = min(xs_all) - 20, max(xs_all) + 60
            out = [c for c in out if lo <= c <= hi]
    except Exception:  # noqa: BLE001
        pass
    return out

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


def card_bottom_y(img, x: int, y_flat_bottom: int, span: int = 60, need: int = 8,
                  bright: int = 150) -> int:
    """找某个牌位的**牌面底边**(从下往上扫) —— 判"抬没抬起"用它 ✓

    用户 2026-09-17 点破: 牌抬起时**右上角会多露出一小条白** ✗ → 按"顶边"判会把**右边邻牌**
    也误判成抬起(实测: 真值 selected=5 却判出 12 个位抬起 ✗);
    底边干净 ✓: 抬起的整张上移(底边也抬高 ~36px), 没抬的底边在原地, 且**底边不受邻牌遮挡** ✓
    """
    x0 = max(0, int(x))
    x1 = min(img.shape[1], x0 + 24)
    y_lo = max(0, int(y_flat_bottom) - span)
    y_hi = min(img.shape[0], int(y_flat_bottom) + span)
    if x1 <= x0 or y_hi <= y_lo:
        return int(y_flat_bottom)
    col = img[y_lo:y_hi, x0:x1]
    rows = (col.min(axis=2) > bright).sum(axis=1)
    for i in range(len(rows) - 1, -1, -1):
        if rows[i] >= need:
            return y_lo + i
    return int(y_flat_bottom)


def lift_baseline(dys: list) -> float:
    """从一组抬起量里取"放平"基线 = 众数附近的中位数 ✓(抬起是少数)"""
    vals = sorted(float(v) for v in dys if v is not None)
    if not vals:
        return 0.0
    # 取最大的那一簇(平放占多数) → 用上四分位的中位数
    hi = vals[int(len(vals) * 0.5):]
    return float(hi[len(hi) // 2]) if hi else vals[-1]


def slide_best(img, x: int, y0: int, tpl, win_up: int = 56, win_dn: int = 130,
               coarse: int = 4) -> tuple:
    """把**一个**模板在该牌位竖直滑动一次 → 返回 (偏移dy, 距离d)。dy<0 = 比放平位置高 ✓"""
    import cv2 as _cv

    x0 = max(0, int(x))
    win = img[max(0, int(y0) - win_up): int(y0) + win_dn, x0:x0 + 24]
    if tpl is None or win.shape[0] < tpl.shape[0] + 4 or win.shape[1] < 20:
        return None, 1e9
    g = _cv.cvtColor(win, _cv.COLOR_RGB2GRAY).astype("float32")
    g = _cv.GaussianBlur(g, (3, 3), 0)
    h = tpl.shape[0]
    t = _cv.GaussianBlur(_cv.cvtColor(tpl, _cv.COLOR_RGB2GRAY).astype("float32"), (3, 3), 0)[:, :24]
    tn = (t - t.mean()) / (t.std() + 1e-6)
    best_d, best_dy = 1e9, win_up - 3
    for dy in range(0, g.shape[0] - h, coarse):          # 粗扫 ✓
        seg = g[dy:dy + h]
        seg = (seg - seg.mean()) / (seg.std() + 1e-6)
        d = float(np.mean(np.abs(seg - tn)))
        if d < best_d:
            best_d, best_dy = d, dy
    lo, hi = max(0, best_dy - coarse), min(g.shape[0] - h, best_dy + coarse + 1)
    for dy in range(lo, hi):                              # 邻域细化 ✓
        seg = g[dy:dy + h]
        seg = (seg - seg.mean()) / (seg.std() + 1e-6)
        d = float(np.mean(np.abs(seg - tn)))
        if d < best_d:
            best_d, best_dy = d, dy
    return float(best_dy - (win_up - 3)), best_d


def tm_read_hand_with_lift(img, y0: int | None = None, tpl: dict | None = None):
    """**读牌 + 量抬起**(一次滑动同时得到两件事 ⟶ 有牌被抬起时也稳 ✓)

    返回 (cards, info): cards = [(花色, 点数, x, 抬起量px)] ✓
    """
    if y0 is None:
        y0, _y1 = hand_band_measured(img)
    img = mask_you_label(img, y0)   # 精确版(只遮绿框) ✓   # ★ 暂撤(2026-09-17): 它修了 x=76 假抬起, 但把邻近列的读数也搞坏了 ✗ (19~22/27)
    xs = card_slots(img, y0)
    bank = load_templates_sr() if tpl is None else tpl
    if not xs or not bank:
        return [], {"base": 0.0, "n": 0}
    ridx = {}
    try:
        rd, _i = tm_read_hand(img)
        for s_, r_, xx in rd:
            k = min(range(len(xs)), key=lambda i: abs(xs[i] - int(xx)))
            ridx[k] = (s_, r_)
    except Exception:  # noqa: BLE001
        pass
    raw = []
    for i, x in enumerate(xs):
        cands = []
        if i in ridx:
            s_, r_ = ridx[i]
            cands = bank.get(f"{s_}_{r_}") or bank.get(f"0_{r_}") or []
        items = ([(f"{s_}_{r_}", t) for t in cands] if cands
                 else [(k2, t) for k2, arrs in bank.items() for t in arrs][:40])
        best = (1e9, None, None)          # (d, dy, key)
        for key_, t in items:
            dy, d = slide_best(img, int(x), y0, t)
            if dy is not None and d < best[0]:
                best = (d, dy, key_)
        raw.append((best[2], best[1], round(best[0], 3)))
    dys = [dy for _k, dy, _d in raw if dy is not None]
    base = lift_baseline(dys) if dys else 0.0
    cards = []
    for (key_, dy, _d), x in zip(raw, xs):
        if key_ is None:
            continue
        s_, r_ = (int(v) for v in key_.split("_"))
        cards.append((s_, r_, int(x), round(float(base - (dy if dy is not None else base)), 1)))
    return cards, {"base": base, "n": len(cards), "raw": raw}



