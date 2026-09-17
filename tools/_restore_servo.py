#!/usr/bin/env python3
"""恢复伺服(用户算法的③④步) + 纠正"整组帮点"的错误假设。

用户 2026-09-17 纠正: 「每个点数只点一次, 因为游戏会整组帮点」**不对** ✗
  游戏**不会每次都帮点** ✓ → 想选几张就得按实际状态去点, **不能靠假设** ✗
正解(用户算法③④): 量出现状 → 多了回落 / 少了补抬 → 再复核 → 通过才出牌 ✓

同时把「你」字 mask 做成**精确范围**(只遮绿框本身, 不碰邻牌 ✓) —— 之前粗遮把读牌搞坏了 ✗
"""
from pathlib import Path
import re

# ---- ① 恢复伺服选牌(替换"一次点准"那版) ----
G = Path("src/landlord_counter/platform/gestures.py")
t = G.read_text()
start = t.index("            # ★ 一次点准(用户 2026-09-17 修正)")
end = t.index("            pp = self.btn(\"play\")")
new = '''            # ★ 伺服: 量现状 → 少了补抬 / 多了回落 → 复核 ✓ (用户算法③④)
            #   用户纠正(2026-09-17): 游戏**不会每次都帮点整组** ✗ → 绝不能靠假设去重 ✓
            #   一切以"量到的抬起状态"为准 ✓ (滑块匹配量抬起, 不受邻牌遮挡 ✓)
            self._servo_select(want_x, rounds=3)
            t_snap = self._snap()
            st = self._raised_state(t_snap, want_x)
            if all(v is True for v in st):
                self.log(f"  [servo] ✓ 复核通过({len(want_x)}张都抬起)")
            else:
                self.log(f"  [servo] ⚠ 复核未完({st}) → 仍按现状出牌, 由出牌回执终判 ✓")
            time.sleep(0.3)
'''
t = t[:start] + new + t[end:]
G.write_text(t)
print("✓ 伺服已恢复(量现状→补抬/回落→复核)")

# ---- ② mask 只遮"绿框精确范围" ----
P = Path("src/landlord_counter/guandan/percept.py")
s = P.read_text()
m = re.search(r"\ndef mask_you_label\(.*?(?=\ndef |\Z)", s, re.S)
NEW = '''

def mask_you_label(img, y0: int | None = None, pad: int = 2):
    """把「你」字绿框(浅绿)遮成周围色 —— **只遮绿框精确范围**, 不碰邻牌 ✓

    用户 2026-09-17: ① x=76 的假抬起来自「你」字的人字旁 ✗ ② 但粗遮会把邻牌读数搞坏 ✗
    → 先找"浅绿"连通域的**精确外接矩形**, 只在该矩形内填色 ✓
    """
    import cv2 as _cv

    out = img.copy()
    if y0 is None:
        y0, _y1 = hand_band_measured(img)
    y_a, y_b = max(0, int(y0) - 46), int(y0) + 6
    x_a, x_b = 0, 200
    box = out[y_a:y_b, x_a:x_b]
    if box.size == 0:
        return out
    r, g, b = box[:, :, 0].astype(int), box[:, :, 1].astype(int), box[:, :, 2].astype(int)
    light_green = ((g > 120) & (g - r > 18) & (g - b > 18)).astype("uint8")
    if int(light_green.sum()) < 30:
        return out
    n, _lab, stats, _c = _cv.connectedComponentsWithStats(light_green, 8)
    if n <= 1:
        return out
    k = 1 + int(np.argmax(stats[1:, 4]))            # 最大的那块绿 ✓
    x_, y_, w_, h_, area_ = stats[k]
    if area_ < 30:
        return out
    yy0 = max(0, y_a + int(y_) - pad)
    yy1 = min(out.shape[0], y_a + int(y_) + int(h_) + pad)
    xx0 = max(0, x_a + int(x_) - pad)
    xx1 = min(out.shape[1], x_a + int(x_) + int(w_) + pad)
    sub = out[yy0:yy1, xx0:xx1]
    gray = ((sub[:, :, 1].astype(int) - sub[:, :, 0].astype(int) > 15)
            & (sub[:, :, 1].astype(int) - sub[:, :, 2].astype(int) > 15))
    keep = sub[~gray]
    if keep.size:
        sub[gray] = np.median(keep.reshape(-1, 3), axis=0).astype("uint8")
    out[yy0:yy1, xx0:xx1] = sub
    return out
'''
s = s[:m.start()] + NEW + s[m.end():]
s = s.replace("    # img = mask_you_label(img, y0)",
              "    img = mask_you_label(img, y0)   # 精确版(只遮绿框) ✓")
P.write_text(s)
print("✓ mask_you_label 改为精确范围并启用")
