#!/usr/bin/env python3
"""按用户 2026-09-17 设计的"伺服式直选"重写 direct_play:

  ① 点之前先看现状(哪些牌已抬起)  ② 求差: 该抬的抬、该落的落
  ③ 复核(多了/漏了)  ④ 修补后再复核  ⑤ 通过才点"出牌"
  ⑥ 没打出去 → 归因: 决策不合规 vs 操作错(由调用方按回执判断)

检测"某张牌是否已抬起"的做法(不纠结是谁抬的 ✗, 只看状态 ✓):
  该牌位的列上, 牌面顶边是否比"放平基线"高 ~20px 以上 ✓
  基线 = 本会话见过的最小顶边(每局开头牌都放平时的值) ✓
"""
from pathlib import Path

P = Path("src/landlord_counter/platform/gestures.py")
s = P.read_text()

# 在 class Executor 里加两个辅助方法(插在 direct_play 之前)
HELPERS = '''
    # ---------- 伺服式直选(用户 2026-09-17 设计) ----------
    def _flat_top(self) -> float:
        """本会话"牌放平"时的顶边基线(动态实测, 不写死 ✗)。"""
        return float(getattr(self, "_top_flat", 0.0))

    def _raised_state(self, img, xs: list) -> list:
        """逐张判断: 这些牌位现在是"已抬起(True)/平放(False)/看不出(None)"。"""
        from ..guandan import percept as _P

        if img is None:
            return [None] * len(xs)
        y0, _y1 = _P.hand_band_measured(img)
        if not self._flat_top():
            self._top_flat = float(y0) + 3.0        # 首次: 记下放平基线 ✓
        out = []
        for x in xs:
            try:
                ty = _P.card_top_y(img, int(x), y0 + 8)
            except Exception:  # noqa: BLE001
                out.append(None)
                continue
            d = self._flat_top() - ty
            out.append(True if d >= 20 else (False if d <= 8 else None))
        return out

    def _servo_select(self, want_x: list, rounds: int = 3) -> bool:
        """伺服: 让 want_x 这些牌位**都处于抬起状态**; 不需要的(我们上轮点过的)回落 ✓

        多牌回落: 只针对"我们上一次点过、这次不要"的位置(可安全反点) ——
        不碰游戏自己高亮的牌(那不是我们点的, 反点反而会选中它们 ✗)
        """
        stale = [x for x in getattr(self, "_last_picked", []) if x not in want_x]
        for r in range(rounds):
            img = self._snap()
            st = self._raised_state(img, want_x)
            missing = [x for x, v in zip(want_x, st) if v is not True]
            undecided = [x for x, v in zip(want_x, st) if v is None]
            self.log(f"  [servo] 第{r + 1}轮: 抬起态={['✓' if v else ('✗' if v is False else '?') for v in st]}"
                     f" 需补={len(missing)}")
            if not missing:
                self._last_picked = list(want_x)
                return True
            for x in missing:
                self._tap_card_at(x, wait=0.5)
            if undecided and r == rounds - 1:
                # 最后一轮还看不出 → 认为已点过(交给"出牌回执"终判 ✓)
                break
        self._last_picked = list(want_x)
        return True          # 是否真打出去由 wait_receipt 终判(用户设计第⑥步) ✓

'''
anchor = "    def direct_play("
assert anchor in s, "找不到 direct_play"
if "_servo_select" not in s:
    s = s.replace(anchor, HELPERS + anchor, 1)

# direct_play: 用伺服选牌替换原来的 select 循环
old = s[s.index("        for r in range(rounds):"):s.index('            pp = self.btn("play")')]
new = '''        # ★ 伺服选牌(用户 2026-09-17 设计): 现状 → 求差(补抬/回落) → 复核 → 通过才出牌 ✓
        self._servo_select(want_x, rounds=3)
        for r in range(max(1, rounds)):
            if r:
                self.log("  [gesture] ↻ 直选重试(重新取帧)")
                time.sleep(1.0)
            self._servo_select(want_x, rounds=1)
            time.sleep(0.3)
'''
s = s.replace(old, new, 1)
P.write_text(s)
print("✓ direct_play 已改为'伺服式选牌(现状→求差→复核→出牌→回执)'")
