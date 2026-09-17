#!/usr/bin/env python3
"""把 card_bottom_y / flat_bottom_baseline 追加到 percept.py 末尾(模块级 ✓)。"""
from pathlib import Path

P = Path("src/landlord_counter/guandan/percept.py")
s = P.read_text()
if "def card_bottom_y(" in s:
    print("· 已存在, 跳过")
else:
    s += '''

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


def flat_bottom_baseline(img, y0: int | None = None) -> int:
    """本帧"牌放平"时的底边基线(取所有牌位底边的中位数 → 抗个别抬起/异常 ✓)"""
    if y0 is None:
        y0, _y1 = hand_band_measured(img)
    y1 = y0 + 120                     # 手牌带约 120px 高
    vals = [card_bottom_y(img, x, y1) for x in card_slots(img)]
    if not vals:
        return y1
    vals.sort()
    return int(vals[len(vals) // 2])
'''
    P.write_text(s)
    print("✓ 已追加 card_bottom_y + flat_bottom_baseline")
