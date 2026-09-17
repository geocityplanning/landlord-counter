#!/usr/bin/env python3
"""一次性: ① 新增 lifted_xs()(定位"哪张牌被抬起"的 x 区间) ② sense 读牌前先清掉残留选中。

为什么: 抬起的牌会盖住右侧邻牌的竖条 → 抬着的时候读牌必然漏 ✗(实测 Q J 10 9 只读出 J)
      → 读牌时机必须钉在"牌都放平"; 清选中的手段 = 点**被抬起的那张**(再点一次=取消 ✓)
      抬起牌的位置: 它在手牌带**上方**露出亮色 → 按列统计就能定位 ✓
"""
import re

A = "src/landlord_counter/guandan/percept.py"
s = open(A).read()

FN = '''

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
    return out
'''
if "def lifted_xs(" not in s:
    m = re.search(r"\ndef lifted_columns\(", s)
    if m is None:
        m = re.search(r"\ndef lifted_px\(", s)
    s = (s[:m.start()] + FN + s[m.start():]) if m else (s + FN)
open(A, "w").write(s)
print("✓ percept.py: 新增 lifted_xs()")

B = "src/landlord_counter/platform/games/guandan_adapter.py"
t = open(B).read()
old = """        if not _tm_first and not self._band_looks_like_hand(frame):
            return Observation(frame=frame, my_turn=False)   # 假\"我回合\" → 跳过, 不空转"""
new = """        if not _tm_first and not self._band_looks_like_hand(frame):
            return Observation(frame=frame, my_turn=False)   # 假\"我回合\" → 跳过, 不空转
        # ★ 读牌时机闸门(2026-09-17): 有牌被抬起时**读不准** —— 抬起的牌会盖住右侧邻牌的
        #   竖条(实测 Q J 10 9 里抬起 10 → 只读出 J ✗) → 先点掉抬起的那张, 再重取帧读 ✓
        try:
            lifted = P.lifted_xs(frame)
            if lifted:
                for lx in lifted:
                    self._ex.dev.tap(int(lx), (self._ex.L.hand_y or 875) + 8, wait=0.35) \\
                        if self._ex is not None else None
                frame2 = self.device.snap() if lifted else frame
                if frame2 is not None and not P.lifted_xs(frame2):
                    frame = frame2      # 清干净了 → 用放平后的帧读 ✓
                else:
                    print(f\"  [读牌] 有牌被抬起({len(lifted)} 处)且未清掉 → 本帧先不读(下帧再试)\", flush=True)
                    return Observation(frame=frame, my_turn=True, hand=None, extra={\"lifted\": True})
        except Exception:  # noqa: BLE001
            pass"""
if old in t and "读牌时机闸门" not in t:
    t = t.replace(old, new)
    open(B, "w").write(t)
    print("✓ adapter: sense 读牌前先清抬起(时机闸门)")
else:
    print("· adapter 已含该闸门或锚点未命中(跳过)")
