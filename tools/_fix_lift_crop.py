#!/usr/bin/env python3
"""一次性: 把读牌/取位改成"逐牌按自身顶边裁切"(抬起/不抬起都能读)。

根因(2026-09-17 用户人工确认 + 实测):
  牌被选中会**上移约 36px**; 而裁切用的是固定带(y0+8..y1-8) → 对抬起的那张切到错位部位
  → 误读(实测把 Q J 10 9 读成 ♥J/A) + 多出假位 + 直选校验读 0

修法: 每个牌位先在它自己的 x 范围内**从上往下找"牌面顶边"**(该列出现连续亮像素的第一行),
      然后从该顶边往下裁固定高度的"整条竖条" ✓
"""
import re

P = "src/landlord_counter/guandan/percept.py"
s = open(P).read()

HELPER = '''

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
'''

if "def card_top_y(" not in s:
    m = re.search(r"\ndef norm_patch\(", s)
    s = (s[:m.start()] + HELPER + s[m.start():]) if m else (s + HELPER)

# tm_read_hand: 裁切改为"逐牌顶边 + 固定高度"
old = """    out = []
    for x in xs:
        x0 = max(0, int(x))
        patch = img[y0 + 8:y1 - 8, x0:x0 + 24]
        if patch.size == 0 or patch.shape[0] < 10:"""
new = """    out = []
    card_h = y1 - y0 - 16                     # 一条竖条的标准高度(与模板一致)
    for x in xs:
        x0 = max(0, int(x))
        ty = card_top_y(img, x0, y0 + 8)      # 逐牌对准: 用**该牌自己的顶边** ✓
        patch = img[ty + 8:ty + 8 + card_h, x0:x0 + 24]   # +8 与模板采集时一致 ✓
        if patch.size == 0 or patch.shape[0] < 10:"""
assert old in s, "找不到 tm_read_hand 裁切段"
s = s.replace(old, new)

open(P, "w").write(s)
print("✓ 已改为逐牌按自身顶边裁切(抬起/不抬起都能读)")
