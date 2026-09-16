#!/usr/bin/env python3
"""一次性: 升级 percept.py 的读牌 —— ① 牌位改为"实测占用范围"限定 ② 归一化匹配。

背景(2026-09-16 实测):
- 参考图(用户标注, 满手 27 张): card_edges 给出干净 27 峰 → 100% ✓
- 实时帧(9 张手牌): 旧代码为了补首张, 往左一直外推到 x<=30 → 9 张牌推出 **21 个位** ✗
  → 根本读的不是牌 ✗
修正: 牌位网格用"手牌实际横向占用"(白占比高的连续段)限定, 不外推 ✓
"""
import re

P = "src/landlord_counter/guandan/percept.py"
s = open(P).read()

HELPERS = '''

def norm_patch(p: "np.ndarray") -> "np.ndarray":
    """把牌面竖条归一化(灰度 + 去均值/除标准差)。

    为什么要归一化: 模板可能采自 JPEG(用户发来的截图) 或 PNG(设备实时帧),
    两者压缩/亮度有细差 → 直接比像素会全超阈值 ✗; 归一化后差异被抹平 ✓
    """
    g = cv2.cvtColor(p, cv2.COLOR_RGB2GRAY).astype("float32")
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
    if len(peaks) >= 3:
        gaps = np.diff(peaks)
        good = gaps[(gaps >= 18) & (gaps <= 32)]
        pitch = float(np.median(good)) if len(good) else pitch_fallback
        ph = float(np.median([p % pitch for p in peaks]))
    else:
        pitch, ph = pitch_fallback, float(peaks[0] % pitch_fallback)
    k0 = int(np.ceil((x_lo - ph) / pitch - 0.25))
    k1 = int(np.floor((x_hi - ph) / pitch + 0.25))
    return [int(round(ph + k * pitch)) for k in range(k0, k1 + 1)]
'''

m = re.search(r"\ndef card_edges\(", s)
if m is None:
    raise SystemExit("找不到 card_edges")
if "def norm_patch(" not in s:
    s = s[:m.start()] + HELPERS + s[m.start():]

NEW_FN = '''def tm_read_hand(img, tpl: dict | None = None, max_dist: float = 1.35, templates_dir: str | None = None):
    """**模板匹配**读手牌(纯像素, 不调模型)。

    做法: 实测手牌带 → 实测牌位(卡边界+占用范围) → 裁每张牌露出的**整条竖条**(宽24)
    → 归一化后与模板库比 → 最近者即"花色+点数"。

    实测(2026-09-16): 用户标注的 27 张满手图上 54 类模板库自校验 **27/27 = 100%** ✓✓
    (VLM 只有 64~68% ✗, 且错误是结构性的: 遮挡/王渲染/)

    返回 (list[(花色1-4, 点数2-16, x)], info); 花色: 1♠ 2♣ 3♥ 4♦; 点数 11=J 12=Q 13=K 14=A 15小王 16大王
    """
    tpl = load_templates_sr(templates_dir) if tpl is None else tpl
    info = {"n_slot": 0, "unknown": 0, "max_dist": 0.0, "tpl": len(tpl)}
    if not tpl:
        return [], info
    y0, y1 = hand_band_measured(img)
    xs = card_slots(img, y0, y1)
    out = []
    for x in xs:
        x0 = max(0, int(x))
        patch = img[y0 + 8:y1 - 8, x0:x0 + 24]
        if patch.size == 0 or patch.shape[0] < 10:
            continue
        if float(patch.std()) < 10.0:            # 纯色块(如"你"字小框)不是牌
            info["unknown"] += 1
            continue
        a = norm_patch(patch)
        best_k, best_d = None, 1e18
        for k, arrs in tpl.items():
            for t in arrs:
                b = norm_patch(t)
                if b.shape != a.shape:
                    continue
                d = float(np.mean(np.abs(a - b)))
                if d < best_d:
                    best_d, best_k = d, k
        if best_k is None or best_d > max_dist:  # 不像任何已知牌 → 丢掉该位(不算一张)
            info["unknown"] += 1
            continue
        suit, rank = (int(v) for v in best_k.split("_"))
        out.append((suit, rank, x0))
        info["max_dist"] = max(info["max_dist"], round(best_d, 3))
    info["n_slot"] = len(out)
    info["keys"] = sorted(tpl)
    return out, info
'''

m2 = re.search(r"\ndef tm_read_hand\(.*?\n(?=def |\Z)", s, re.S)
if m2 is None:
    raise SystemExit("找不到 tm_read_hand")
s = s[:m2.start()] + "\n" + NEW_FN + s[m2.end():]

# 模板库加载: 支持 "花色_点数" 目录(多文件/多版本)
LOADER = '''

def load_templates_sr(d: str | None = None) -> dict:
    """加载"花色+点数"模板库: 目录下 *.npy, 文件名 <花色>_<点数>_<序号>.npy。"""
    import os as _os
    if d is None:
        d = _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "data", "templates_sr")
    d = _os.path.abspath(d)
    bank: dict = {}
    if not _os.path.isdir(d):
        return bank
    for fn in _os.listdir(d):
        if not fn.endswith(".npy"):
            continue
        k = fn.rsplit("_", 1)[0]
        try:
            bank.setdefault(k, []).append(np.load(_os.path.join(d, fn)))
        except Exception:
            continue
    return bank
'''
if "def load_templates_sr(" not in s:
    m3 = re.search(r"\ndef load_templates\(", s)
    s = (s[:m3.start()] + LOADER + s[m3.start():]) if m3 else (s + LOADER)

open(P, "w").write(s)
print("✓ percept.py 已升级: 实测牌位(占用范围限定) + 归一化匹配 + 花色模板库加载")
