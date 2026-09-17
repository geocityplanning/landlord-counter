#!/usr/bin/env python3
"""把直选从"边点边看边补(会滚雪球 ✗)"改成"一次点准 + 用出牌结果判成败" ✓

用户 2026-09-17 点破:
  「你的决策是想打那几张牌，怎么会抬起这些」→ 因为伺服反复"补点", 而"读抬起"本身有误
    → 错误累积, 抬起集合越滚越大 ✗
正解(用户算法第④⑤⑥步): 按决策**点准那几张**(每个点数只点一次, 游戏会整组帮点 ✓)
    → 直接出牌 → 成不成由结果告诉我们 ✓ (错了再归因: 决策错 还是 操作错)
"""
from pathlib import Path

G = Path("src/landlord_counter/platform/gestures.py")
t = G.read_text()

start = t.index("            # ★ 伺服式选牌(用户 2026-09-17 设计)")
end = t.index("            pp = self.btn(\"play\")")
new = '''            # ★ 一次点准(用户 2026-09-17 修正): **按决策点那几张, 每个点数只点一次** ✓
            #   为什么不再"反复补点": 读"抬起"本身有误(UI 元素/分辨率), 边点边补会**滚雪球** ✗
            #   (实测: 决策打单张 6, 抬起却成了 Q A 8 Q 7 6 ✗)
            #   游戏里"点一张会选整组" → 同点数重复点等于反复切换 ✗ → 只点一次 ✓
            _seen = set()
            _tapped = 0
            for _i, _x in zip(idxs, want_x):
                _rk = ranks[_i] if (ranks and _i < len(ranks)) else None
                if _rk is not None and _rk in _seen:
                    continue                      # 同点数只点一次 ✓
                _seen.add(_rk)
                self._tap_card_at(_x, wait=0.6)
                _tapped += 1
            self.log(f"  [gesture] 点准: 目标{len(idxs)}张/{len(_seen)}组 → 实点{_tapped}次 "
                     f"(每个点数只点一次 ✓)")
            self._last_picked = list(want_x)
            time.sleep(0.4)
'''
t = t[:start] + new + t[end:]
G.write_text(t)
print("✓ direct_play: 伺服补点 → 一次点准(同点数只点一次)")
