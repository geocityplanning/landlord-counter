#!/usr/bin/env python3
"""一次性修复:
① **牌条形状不一致** → 归一化前统一缩放到固定高度(实测差 1 像素就全跳过 ✗)
② **牌位多算** → 先取"最长等距串"(真正的一排牌), 只在串两端按"是不是牌面(白)"扩 ≤2 格
"""
import re

P = "src/landlord_counter/guandan/percept.py"
s = open(P).read()

# ---- ① 归一化时统一尺寸 ----
old_norm = '''    g = cv2.cvtColor(p, cv2.COLOR_RGB2GRAY).astype("float32")
    g = cv2.GaussianBlur(g, (3, 3), 0)
    g = g - g.mean()
    sd = g.std()
    return g / sd if sd > 1e-6 else g'''
new_norm = '''    g = cv2.cvtColor(p, cv2.COLOR_RGB2GRAY).astype("float32")
    # ⚠️ 实测(2026-09-16): 实时帧与截图的牌条高度会差 1 像素(104 vs 105) →
    # 形状不等就 continue 会让**全部比对被跳过**(距离恒为 1e18, 一张都读不出) ✗
    # → 归一化前统一到固定尺寸(NORM_H x NORM_W)
    g = cv2.resize(g, (NORM_W, NORM_H), interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    g = g - g.mean()
    sd = g.std()
    return g / sd if sd > 1e-6 else g'''
assert old_norm in s, "找不到 norm_patch 主体"
s = s.replace(old_norm, new_norm)

# ---- ② 牌位: 最长等距串 + 两端白面扩格 ----
old_slots = '''    if len(peaks) >= 3:
        gaps = np.diff(peaks)
        good = gaps[(gaps >= 18) & (gaps <= 32)]
        pitch = float(np.median(good)) if len(good) else pitch_fallback
        ph = float(np.median([p % pitch for p in peaks]))
    else:
        pitch, ph = pitch_fallback, float(peaks[0] % pitch_fallback)
    k0 = int(np.ceil((x_lo - ph) / pitch - 0.25))
    k1 = int(np.floor((x_hi - ph) / pitch + 0.25))
    return [int(round(ph + k * pitch)) for k in range(k0, k1 + 1)]'''
new_slots = '''    pitch = pitch_fallback
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
        col = img[y0 + 8:y1 - 8, x:x + 8]
        return bool(col.size and float((col.min(axis=2) > 150).mean()) > 0.5)
    k = 0
    while k < 2 and card_like(lo - pitch * (k + 1)) and (lo - pitch * (k + 1)) >= x_lo - pitch:
        k += 1
    lo = lo - pitch * k
    k = 0
    while k < 2 and card_like(hi + pitch * (k + 1)) and (hi + pitch * (k + 1)) <= x_hi + pitch:
        k += 1
    hi = hi + pitch * k
    n = int(round((hi - lo) / pitch)) + 1
    return [int(round(lo + i * pitch)) for i in range(n)]'''
assert old_slots in s, "找不到 card_slots 网格段"
s = s.replace(old_slots, new_slots)

# 常量
if "NORM_H, NORM_W" not in s:
    s = s.replace("def norm_patch(", "NORM_H, NORM_W = 96, 24          # 归一化统一尺寸(消除 1 像素高度差)\n\n\ndef norm_patch(", 1)

open(P, "w").write(s)
print("✓ 已修: 统一归一化尺寸 + 牌位取最长等距串")
