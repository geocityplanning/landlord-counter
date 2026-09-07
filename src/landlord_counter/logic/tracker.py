"""记牌逻辑：斗地主牌型定义、剩余牌追踪、概率推理。

牌编码: 3-10 → '3'..'10', J/Q/K/A/2, 小王 'BJ', 大王 'RJ'
花色只影响视觉识别，记牌只关心点数。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

# 标准 54 张牌
RANKS = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"]
JOKERS = ["BJ", "RJ"]  # 小王、大王
ALL_RANKS = RANKS + JOKERS

FULL_DECK = Counter({r: 4 for r in RANKS})
FULL_DECK.update({JOKERS[0]: 1, JOKERS[1]: 1})


@dataclass
class GameState:
    """对局状态"""

    remaining: Counter = field(default_factory=lambda: FULL_DECK.copy())
    played: Counter = field(default_factory=Counter)
    # 每个玩家已出的牌
    played_by: dict[str, Counter] = field(
        default_factory=lambda: {"self": Counter(), "left": Counter(), "right": Counter()}
    )
    landlord: str = "self"  # 地主身份
    my_hand: Counter = field(default_factory=Counter)  # 自己手牌（已知）
    known_hand: dict[str, Counter] = field(
        default_factory=lambda: {"left": Counter(), "right": Counter()}
    )
    round_num: int = 0

    def reset(self):
        self.remaining = FULL_DECK.copy()
        self.played = Counter()
        for k in self.played_by:
            self.played_by[k] = Counter()
        self.known_hand = {"left": Counter(), "right": Counter()}
        self.round_num = 0

    def record_play(self, who: str, cards: list[str]):
        """记录某人出牌"""
        c = Counter(cards)
        self.played_by[who] += c
        self.played += c
        self.remaining -= c
        # 从已知手牌中扣除
        if who in self.known_hand:
            self.known_hand[who] -= c

    def record_my_hand(self, cards: list[str]):
        """更新自己手牌（识别到手牌变化时）"""
        self.my_hand = Counter(cards)

    def unknown_remaining(self) -> Counter:
        """未知区域的牌 = 剩余牌 - 已知他人手牌"""
        known = Counter()
        for c in self.known_hand.values():
            known += c
        return self.remaining - known

    def infer_opponents(self) -> dict[str, Counter]:
        """推理对手可能的牌（简化：未知牌按剩余分配，地主多3张）"""
        unknown = self.unknown_remaining()
        total_unknown = sum(unknown.values())
        result = {}
        for player in ["left", "right"]:
            known = self.known_hand[player]
            n_unknown = 17 - sum(known.values())  # 农民17张，地主20张
            if self.landlord == player:
                n_unknown = 20 - sum(known.values())
            # 未知牌按比例估算
            est = known.copy()
            if total_unknown > 0:
                for rank, cnt in unknown.items():
                    est[rank] += round(cnt * n_unknown / total_unknown)
            result[player] = est
        return result

    def summary(self) -> str:
        """生成记牌摘要文本"""
        lines = [f"===== 第{self.round_num}局 记牌器 ====="]
        lines.append(f"地主: {self.landlord}")
        lines.append(
            "剩余牌: "
            + " ".join(
                f"{r}×{c}" for r, c in sorted(self.remaining.items()) if c > 0
            )
        )
        key_ranks = ["2", "A", "K", "BJ", "RJ"]
        lines.append(
            "关键牌剩余: "
            + " ".join(
                f"{r}={self.remaining.get(r, 0)}" for r in key_ranks
            )
        )
        for p in ["left", "right"]:
            est = self.infer_opponents()[p]
            lines.append(
                f"{p} 可能持有: "
                + " ".join(
                    f"{r}×{c}" for r, c in sorted(est.items()) if c > 0
                )
            )
        return "\n".join(lines)
