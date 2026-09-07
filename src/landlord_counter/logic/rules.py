"""游戏规则抽象层：不同牌类游戏通过实现 GameRules 接口接入。

设计思想（对齐 AgentOS 工具总线）:
    感知层（截屏/识别）与游戏无关，规则层按游戏插拔。
    新增游戏 = 实现一个 GameRules 子类，无需改动识别代码。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class GameRules(ABC):
    """游戏规则接口——所有牌类游戏实现此接口"""

    name: str
    total_cards: int          # 总牌数（如斗地主54、掼蛋108）
    ranks: list[str]          # 点数列表（从小到大）
    jokers: list[str] = field(default_factory=list)  # 大小王
    cards_per_player: int = 17  # 每人手牌数
    num_players: int = 3      # 玩家数

    @abstractmethod
    def build_deck(self) -> Counter:
        """构建完整牌堆"""

    @abstractmethod
    def validate_play(self, cards: list[str]) -> tuple[bool, str]:
        """校验出牌是否合法，返回 (是否合法, 牌型描述)"""

    @abstractmethod
    def beats(self, current: list[str], previous: list[str]) -> bool:
        """判断 current 是否能压过 previous"""

    @abstractmethod
    def infer_opponents(self, remaining: Counter, known: dict[str, Counter]) -> dict[str, Counter]:
        """根据剩余牌推理对手可能持有的牌"""

    def hand_size(self, is_landlord: bool = False) -> int:
        return self.cards_per_player


class DouDizhuRules(GameRules):
    """斗地主规则"""

    def __init__(self):
        super().__init__(
            name="斗地主",
            total_cards=54,
            ranks=["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"],
            jokers=["BJ", "RJ"],
            cards_per_player=17,
            num_players=3,
        )

    def build_deck(self) -> Counter:
        deck = Counter({r: 4 for r in self.ranks})
        deck.update({j: 1 for j in self.jokers})
        return deck

    def validate_play(self, cards: list[str]) -> tuple[bool, str]:
        c = Counter(cards)
        if not cards:
            return False, "空牌"
        # 王炸
        if sorted(cards) == ["BJ", "RJ"]:
            return True, "王炸"
        # 炸弹：四张同点数
        if len(c) == 1 and list(c.values())[0] == 4:
            return True, f"炸弹[{cards[0]}]"
        # 单张
        if len(cards) == 1:
            return True, f"单牌[{cards[0]}]"
        # 对子
        if len(c) == 1 and list(c.values())[0] == 2:
            return True, f"对子[{cards[0]}]"
        # 三带
        if len(c) == 1 and list(c.values())[0] == 3:
            return True, f"三张[{cards[0]}]"
        return False, "暂不支持复杂牌型(顺子/连对/三带一)"

    def beats(self, current: list[str], previous: list[str]) -> bool:
        cur, prev = self._type_key(current), self._type_key(previous)
        if not prev:
            return True
        if cur[0] == "王炸":
            return True
        if prev[0] == "王炸":
            return False
        if cur[0] == "炸弹" and prev[0] != "炸弹":
            return True
        if cur[0] != prev[0] or cur[1] != prev[1]:
            return False  # 类型不同不能压（炸弹除外）
        return self._rank_index(cur[2]) > self._rank_index(prev[2])

    def _type_key(self, cards: list[str]) -> tuple:
        c = Counter(cards)
        if sorted(cards) == ["BJ", "RJ"]:
            return ("王炸", 0, "BJ")
        if len(c) == 1:
            n = list(c.values())[0]
            if n == 4:
                return ("炸弹", 0, cards[0])
            if n == 2:
                return ("对子", 1, cards[0])
            if n == 3:
                return ("三张", 1, cards[0])
        if len(cards) == 1:
            return ("单牌", 1, cards[0])
        return ("未知", -1, "")

    def _rank_index(self, rank: str) -> int:
        if rank == "BJ":
            return 14
        if rank == "RJ":
            return 15
        return self.ranks.index(rank) if rank in self.ranks else -1

    def infer_opponents(self, remaining: Counter, known: dict[str, Counter]) -> dict[str, Counter]:
        result = {}
        total_unknown = sum(remaining.values())
        for player in known:
            est = known[player].copy()
            n_unknown = 17 - sum(known[player].values())
            if total_unknown > 0:
                for rank, cnt in remaining.items():
                    est[rank] += round(cnt * n_unknown / total_unknown)
            result[player] = est
        return result


class GuanDanRules(GameRules):
    """掼蛋规则（简化版：4人两副牌、级牌、红桃万能牌）"""

    def __init__(self, level: int = 2):
        super().__init__(
            name="掼蛋",
            total_cards=108,
            ranks=["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"],
            jokers=["BJ", "BJ", "RJ", "RJ"],  # 两副牌 = 2小王+2大王
            cards_per_player=27,
            num_players=4,
        )
        self.level = str(level)  # 当前级牌

    def build_deck(self) -> Counter:
        deck = Counter({r: 8 for r in self.ranks})  # 两副牌每点数8张
        deck.update(self.jokers)  # jokers 含重复项（2小王+2大王）
        return deck

    def validate_play(self, cards: list[str]) -> tuple[bool, str]:
        c = Counter(cards)
        if not cards:
            return False, "空牌"
        n = len(c)
        # 炸弹：4张以上同点数
        if n == 1 and list(c.values())[0] >= 4:
            return True, f"炸弹[{cards[0]}]{len(cards)}张"
        if len(cards) == 1:
            return True, f"单牌[{cards[0]}]"
        if n == 1 and list(c.values())[0] == 2:
            return True, f"对子[{cards[0]}]"
        if n == 2 and sorted(c.values()) == [2, 3]:
            return True, "三带二(简化)"
        return False, "暂不支持顺子/同花顺/连对"

    def beats(self, current: list[str], previous: list[str]) -> bool:
        # 简化版：炸弹(>=4张同点数)压一切非炸弹；同类型比点数
        def key(cards):
            c = Counter(cards)
            if not cards:
                return (0, 0, "")
            n_same = list(c.values())[0] if len(c) == 1 else 0
            if len(c) == 1 and n_same >= 4:
                return (3, n_same, cards[0])  # 炸弹: (类型3, 张数, 点数)
            if len(c) == 1 and n_same == 2:
                return (2, 1, cards[0])  # 对子
            if len(cards) == 1:
                return (1, 1, cards[0])  # 单牌
            if len(c) == 2 and sorted(c.values()) == [2, 3]:
                return (2, 1, cards[0])  # 三带二(简化按对子比)
            return (0, 0, "")
        ck, pk = key(current), key(previous)
        if not previous:
            return True
        if ck[0] == 3 and pk[0] != 3:
            return True  # 炸弹压非炸弹
        if pk[0] == 3 and ck[0] != 3:
            return False
        if ck[0] != pk[0]:
            return False
        if ck[0] == 3:
            # 都是炸弹: 先比张数再比点数
            if ck[1] != pk[1]:
                return ck[1] > pk[1]
            return self._rank_index(ck[2]) > self._rank_index(pk[2])
        return self._rank_index(ck[2]) > self._rank_index(pk[2])

    def _rank_index(self, rank: str) -> int:
        if rank in ("BJ", "RJ"):
            return 20 if rank == "RJ" else 19
        return self.ranks.index(rank) if rank in self.ranks else -1

    def infer_opponents(self, remaining: Counter, known: dict[str, Counter]) -> dict[str, Counter]:
        result = {}
        total_unknown = sum(remaining.values())
        for player in known:
            est = known[player].copy()
            n_unknown = 27 - sum(known[player].values())
            if total_unknown > 0:
                for rank, cnt in remaining.items():
                    est[rank] += round(cnt * n_unknown / total_unknown)
            result[player] = est
        return result


RULES_REGISTRY: dict[str, type[GameRules]] = {
    "doudizhu": DouDizhuRules,
    "guandan": GuanDanRules,
}
