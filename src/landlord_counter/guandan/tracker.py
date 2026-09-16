"""掼蛋记牌器: 按「点数 × 座位」追踪已出/余牌 + 守恒校验 + 未见牌池(信念输入)。

为什么需要(2026-09-16 评估):
  · 现在喂给 RL 模型状态的 `cards_left` 是**粗估**(按座位累加出牌"张数", 不按点数) ✗;
  · 自家 AI 是**无状态**的(每次决策不看历史) ✗;
  · "辅助队友"必须知道: 队友缺什么、对手还剩什么 ✗ —— 没有记牌器就无从谈起。

数据来源与成本:
  每帧只看**桌面牌块**(纯 CV, 零 VLM); 只有出现**新牌块**时才调 VLM 读那几块 ——
  事件驱动, 成本极低(掼蛋一局约几百次出牌, VLM 只在这些时刻被叫到)。

守恒关系(拿来当"读数正确性"的自检):
  整副 = 2 副牌 = 108 张(= 我方手牌 + 四家已出 + 未见);
  按点数: 我方手牌[r] + 已出[r] ≤ 该点数的总张数(普通 8 张, 大小王各 2 张)。
  违反 ⇒ 说明有一次读牌错了 ⇒ 立刻能发现(而不是等输赢异常)。

用法:
    t = CardTracker()
    t.observe("南", my_play_cards)      # 每次看到某家新出牌就喂一次(内部去重)
    t.set_my_hand(hand_cards)           # 每次读到我的手牌喂一次(整手覆盖)
    t.state_for_rl()                    # → [我, 下家, 对家, 上家, 合计] 余牌张数(喂 RL)
    t.unseen_pool()                     # → Counter{zhi: 张数} 外面还有哪些牌(策略用)
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

# 座位(按出牌顺序: 我 → 下家 → 对家 → 上家) —— 与 games 里 _SEAT_IDX 一致
SEATS = ("南", "西", "北", "东")          # 南=我, 北=队友
TEAM = {"南", "北"}

TOTAL_PER_RANK = {r: 8 for r in range(2, 15)}     # 2..A 各 8 张(两副)
TOTAL_PER_RANK[15] = 2                            # 小王
TOTAL_PER_RANK[16] = 2                            # 大王
DECK_TOTAL = 108
HAND_SIZE = 27


def _zhi(card) -> int:
    """取牌的点数值(2..14=A, 15=小王, 16=大王)。"""
    return int(getattr(card, "zhi", card))


def _sig(cards: Iterable) -> tuple:
    """一手牌的指纹(用于去重: 同一手牌反复出现在画面上只记一次)。"""
    return tuple(sorted(_zhi(c) for c in cards))


@dataclass
class CardTracker:
    """掼蛋记牌器。"""

    played: dict = field(default_factory=lambda: {s: Counter() for s in SEATS})
    my_hand: Counter = field(default_factory=Counter)
    _visible: dict = field(default_factory=lambda: {s: None for s in SEATS})   # 各座位当前可见的一手牌指纹
    rounds: int = 0
    dup_skipped: int = 0              # 去重命中次数(可观测: 高说明采样密, 低说明漏采)
    violations: list = field(default_factory=list)

    # ---------------- 观测 ----------------
    def observe(self, seat: str, cards) -> bool:
        """看到某座位**当前**出的一手牌。同一手牌重复看到只计一次。"""
        if seat not in self.played or not cards:
            return False
        s = _sig(cards)
        if self._visible.get(seat) == s:
            self.dup_skipped += 1
            return False
        self._visible[seat] = s
        self.played[seat].update(_zhi(c) for c in cards)
        self._check()
        return True

    def table_cleared(self) -> None:
        """整桌清空(= 新的一轮开始): 清掉"当前可见"指纹, 使下一手同牌也能被计入。"""
        for s in SEATS:
            self._visible[s] = None
        self.rounds += 1

    def set_my_hand(self, cards) -> None:
        """整手覆盖我方手牌(每次读到就喂; 取最大张数的那次, 防残影少读)。"""
        c = Counter(_zhi(x) for x in cards)
        if sum(c.values()) >= sum(self.my_hand.values()):
            self.my_hand = c
        self._check()

    def reset(self) -> None:
        """新一局。"""
        self.played = {s: Counter() for s in SEATS}
        self.my_hand = Counter()
        self._visible = {s: None for s in SEATS}
        self.rounds = 0
        self.violations = []

    # ---------------- 查询 ----------------
    def remaining_counts(self) -> dict:
        """各座位**余牌张数**(= 27 - 已出张数)。"""
        return {s: HAND_SIZE - sum(self.played[s].values()) for s in SEATS}

    def state_for_rl(self) -> list:
        """喂 RL 状态 token 的 cards_left: [我, 下家, 对家, 上家, 合计]。

        注意: "我方"用**手牌张数**(手牌是直接读到的, 精确); 其他三家用 27-已出(反推)。
        """
        r = self.remaining_counts()
        order = ("南", "西", "北", "东")     # 我, 下家, 对家, 上家
        vals = [max(0, r[s]) for s in order]
        mine = sum(self.my_hand.values())
        if mine:
            vals[0] = mine
        return vals + [sum(vals)]

    def unseen_pool(self) -> Counter:
        """**未见牌池**: 还在别人手里的牌(按点数) —— 策略/信念推理的输入。"""
        pool = Counter()
        for r, tot in TOTAL_PER_RANK.items():
            left = tot - self.my_hand.get(r, 0) - sum(self.played[s].get(r, 0) for s in SEATS)
            if left > 0:
                pool[r] = left
        return pool

    def seat_played(self, seat: str) -> Counter:
        return Counter(self.played.get(seat, Counter()))

    # ---------------- 自检 ----------------
    def _check(self) -> None:
        """守恒校验: 我方手牌 + 四家已出 的每个点数不得超过总数。"""
        for r, tot in TOTAL_PER_RANK.items():
            used = self.my_hand.get(r, 0) + sum(self.played[s].get(r, 0) for s in SEATS)
            if used > tot:
                msg = f"点数{r}(上限{tot}): 手牌{self.my_hand.get(r,0)} + 已出{used - self.my_hand.get(r,0)} = {used}"
                if msg not in [v for v in self.violations]:
                    self.violations.append(msg)

    def check(self) -> tuple[bool, list]:
        self._check()
        return (not self.violations), list(self.violations)

    def summary(self) -> str:
        r = self.remaining_counts()
        return (f"余牌 我{r['南']}/下家{r['西']}/对家{r['北']}/上家{r['东']} | 未见{sum(self.unseen_pool().values())}张"
                f" | 轮次{self.rounds} | 去重{self.dup_skipped} | 校验{'✓' if not self.violations else '✗' + str(self.violations[:2])}")
