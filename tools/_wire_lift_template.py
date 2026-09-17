#!/usr/bin/env python3
"""把"模板滑动测抬起量"接进 percept(供伺服用) + 接进 _raised_state。

关键点(用户 2026-09-17 逼出来的正解):
  · 顶边会被"抬起牌右上角露出的那条白"污染 ✗; 底边会被"下方被压的邻牌"污染 ✗
  · **只有牌面上自己的图案/点数会跟着牌一起上移** ✓ —— 用模板竖直滑动量它 ✓
  · 双峰实测: 平放 +11px / 抬起 -25px, 相差 36px, 干净可分 ✓
"""
from pathlib import Path

# ---- ① percept: 新增 card_lift_dy + lift_baseline ----
P = Path("src/landlord_counter/guandan/percept.py")
s = P.read_text()
if "def card_lift_dy(" not in s:
    s += '''

def card_lift_dy(img, x: int, y0: int, tpl_list: list, norm_h: int = 96,
                 win_up: int = 56, win_dn: int = 130) -> float:
    """量某张牌"抬起了多少像素"(模板竖直滑动, 不受邻牌遮挡 ✓)。

    做法: 取该牌位竖直窗口 → 对每个候选起始行, 截"模板自身高度"一段 → 各自缩放对齐后比
          → 最优起始行 - "放平参考行"(win_up-3) = 抬起量(负 = 抬起) ✓
    实测: 平放 +11 / 抬起 -25 (相差 36px) ✓
    """
    import cv2 as _cv
    gray = _cv.cvtColor(img, _cv.COLOR_RGB2GRAY).astype("float32")
    gray = _cv.GaussianBlur(gray, (3, 3), 0)
    x0 = max(0, int(x))
    win = gray[max(0, int(y0) - win_up): int(y0) + win_dn, x0:x0 + 24]
    if win.shape[0] < 40 or win.shape[1] < 24:
        return 0.0
    best_d, best_dy = 1e9, 0
    flat_ref = win_up - 3
    for tpl in (tpl_list or []):
        h = tpl.shape[0]
        if win.shape[0] < h + 4:
            continue
        tn = _cv.GaussianBlur(_cv.cvtColor(tpl, _cv.COLOR_RGB2GRAY).astype("float32"), (3, 3), 0)
        tn = _cv.resize(tn, (24, norm_h), interpolation=_cv.INTER_AREA)
        tn = (tn - tn.mean()) / (tn.std() + 1e-6)
        for dy in range(0, win.shape[0] - h):
            seg = _cv.resize(win[dy:dy + h], (24, norm_h), interpolation=_cv.INTER_AREA)
            seg = (seg - seg.mean()) / (seg.std() + 1e-6)
            d = float(np.mean(np.abs(seg - tn)))
            if d < best_d:
                best_d, best_dy = d, dy
    return float(best_dy - flat_ref)


def lift_baseline(dys: list) -> float:
    """从一组抬起量里取"放平"基线 = 众数附近的中位数 ✓(抬起是少数)"""
    vals = sorted(float(v) for v in dys if v is not None)
    if not vals:
        return 0.0
    # 取最大的那一簇(平放占多数) → 用上四分位的中位数
    hi = vals[int(len(vals) * 0.5):]
    return float(hi[len(hi) // 2]) if hi else vals[-1]
'''
    P.write_text(s)
    print("✓ percept: 新增 card_lift_dy / lift_baseline")

# ---- ② gestures: _raised_state 用模板滑动 ----
G = Path("src/landlord_counter/platform/gestures.py")
t = G.read_text()
start = t.index("    def _raised_state(self, img, xs: list) -> list:")
end = t.index("    def _servo_select(")
new_fn = '''    def _raised_state(self, img, xs: list) -> list:
        """逐张判断: "已抬起(True) / 平放(False) / 看不出(None)" ✓

        ⚠️ 判据 = **模板竖直滑动量**(用户 2026-09-17 逼出来的正解 ✓):
           顶边会被"抬起牌右上角露出的一条白"污染 ✗; 底边会被"下方被压的邻牌"污染 ✗;
           **只有牌面自己的图案跟着牌上移** ✓ → 用该牌点数的模板滑一遍量偏移 ✓
           实测双峰: 平放 +11px / 抬起 -25px(相差 36px) ✓
        """
        from ..guandan import percept as _P

        if img is None:
            return [None] * len(xs)
        y0, _y1 = _P.hand_band_measured(img)
        bank = _P.load_templates_sr()
        # 先整手读**一次**(拿 x → 点数) → 每张只滑它那个点数的模板(快 ✓)
        by_x = {}
        try:
            rd, _i = _P.tm_read_hand(img)
            by_x = {int(xx): (s_, r_) for s_, r_, xx in rd}
        except Exception:  # noqa: BLE001
            pass
        dys = []
        for x in xs:
            hit = None
            for xx, sr in by_x.items():
                if abs(xx - int(x)) <= 2:
                    hit = sr
                    break
            cands = []
            if hit:
                cands = bank.get(f"{hit[0]}_{hit[1]}") or bank.get(f"0_{hit[1]}") or []
            if not cands:
                cands = [v[0] for v in bank.values() if v][:6]
            dys.append(_P.card_lift_dy(img, int(x), y0, cands))
        base = _P.lift_baseline(dys)
        self._flat_lift = base
        out = []
        for d in dys:
            rel = base - d
            out.append(True if rel >= 18 else (False if rel <= 8 else None))
        return out

'''
t = t[:start] + new_fn + t[end:]
G.write_text(t)
print("✓ gestures: _raised_state 改用模板滑动量")
