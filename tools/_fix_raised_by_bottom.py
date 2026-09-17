#!/usr/bin/env python3
"""修"抬起检测": 判据从**顶边**改成**底边**(用户 2026-09-17 点破的真正机制)。

为什么顶边不行(用户原话 + 图示验证):
  右边的牌压在左边的牌上; 牌被抬起时, **右上角会多露出一小条白** ✓
  → 我按"列里第一行亮像素"找顶边时, 右边邻牌的列**上方**正好有这一小条白 ✗
  → 于是把没抬起的邻牌也判成"抬起了" ✗ (实测: 真值 selected=5 却判出 12 个位抬起)

底边为什么可靠:
  抬起的牌**整张上移**, 底边也跟着抬高 36px ✓; 没抬起的牌底边在原地 ✓
  而**底边不会被任何邻牌遮挡物影响** ✓ (被盖住的只是左右两侧, 底边是自己的 ✓)
"""
import re
from pathlib import Path

P = Path("src/landlord_counter/guandan/percept.py")
s = P.read_text()

FN = '''

def card_bottom_y(img, x: int, y_flat_bottom: int, span: int = 60, need: int = 8,
                  bright: int = 150) -> int:
    """找某个牌位的**牌面底边**(从下往上扫) —— 判"抬没抬起"用它 ✓

    用户 2026-09-17 点破: 抬起时右上角会多露一小条白 ✗ → 按"顶边"判会把邻牌误判成抬起;
    底边则干净: 抬起的整张上移(底边也抬高), 没抬的底边在原地, 且**底边不受邻牌遮挡** ✓
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


def flat_bottom_baseline(img, y0: int | None = None) -> int:
    """本帧"牌放平"时的底边基线(取所有牌位底边的**众数/中位**, 抗个别抬起/异常) ✓"""
    if y0 is None:
        y0, _y1 = hand_band_measured(img)
    y1 = y0 + 120                     # 手牌带高度约 120px
    vals = []
    for x in card_slots(img):
        vals.append(card_bottom_y(img, x, y1))
    if not vals:
        return y1
    vals.sort()
    return int(vals[len(vals) // 2])  # 中位数 = 放平那群牌 ✓
'''
if "def card_bottom_y(" not in s:
    m = re.search(r"\ndef card_top_y\(", s)
    s = (s[:m.start()] + FN + s[m.start():]) if m else (s + FN)

# _raised_state 改用底边判定
G = Path("src/landlord_counter/platform/gestures.py")
t = G.read_text()
old = '''    def _raised_state(self, img, xs: list) -> list:
        """逐张判断: 这些牌位现在"已抬起(True) / 平放(False) / 看不出(None)" ✓

        只看**状态**(不纠结是谁抬的 ✗ —— 游戏自己的提示高亮也会抬起 ✓)。
        判据: 该牌位的牌面顶边是否比"放平基线"高 >=20px ✓
        """
        from ..guandan import percept as _P

        if img is None:
            return [None] * len(xs)
        y0, _y1 = _P.hand_band_measured(img)
        if not self._flat_top():
            self._top_flat = float(y0) + 3.0            # 首次: 记下放平基线 ✓
        out = []
        for x in xs:
            try:
                ty = _P.card_top_y(img, int(x), y0 + 8)
            except Exception:  # noqa: BLE001
                out.append(None)
                continue
            d = self._flat_top() - ty
            out.append(True if d >= 20 else (False if d <= 8 else None))
        return out'''
new = '''    def _raised_state(self, img, xs: list) -> list:
        """逐张判断: 这些牌位现在"已抬起(True) / 平放(False) / 看不出(None)" ✓

        ⚠️ 判据 = **底边**(不是顶边! 用户 2026-09-17 点破 ✗→✓):
           牌抬起时右边会多露一小条白 ✗ → 按"顶边"判会把**右边邻牌**也误判成抬起 ✗
           (实测 真值 selected=5 却判出 12 个抬起)
           底边不受任何邻牌遮挡影响 ✓: 抬起的整张上移 → 底边也抬高 ✓
        """
        from ..guandan import percept as _P

        if img is None:
            return [None] * len(xs)
        y0, _y1 = _P.hand_band_measured(img)
        base = _P.flat_bottom_baseline(img, y0)      # 本帧的"放平底边"(中位, 抗个别抬起 ✓)
        self._flat_bottom = float(base)
        out = []
        for x in xs:
            try:
                by = _P.card_bottom_y(img, int(x), base)
            except Exception:  # noqa: BLE001
                out.append(None)
                continue
            d = base - by                                # 底边比基线高多少
            out.append(True if d >= 20 else (False if d <= 8 else None))
        return out'''
assert old in t, "找不到 _raised_state"
t = t.replace(old, new, 1)
G.write_text(t)
print("✓ 抬起检测: 顶边 → **底边**(用户点破的机制)")
