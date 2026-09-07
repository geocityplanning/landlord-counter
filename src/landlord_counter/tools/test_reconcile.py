"""合成噪声测试 v2：量化 reconcile + 三读投票 的纠错收益。

错误模型(对齐 glm-4v-plus 实测): 漏读对子其中一张 + 幻觉补张(张数守恒), 基线逐张 ~90-92%。

场景:
  A   单帧观测(无 prior) —— 基线
  A3  发牌静止连读3次 → 多数投票建 prior
  B   从投票 prior 出发, 出牌1-3张后再观测 → 单调性+数量锚校正
用法: uv run python -m landlord_counter.tools.test_reconcile [轮数]
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from landlord_counter.logic.reconcile import reconcile_hand, vote_initial_hand  # noqa: E402

RANKS = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2", "BJ", "RJ"]
CAPS = {r: 4 for r in RANKS[:13]}; CAPS["BJ"] = 1; CAPS["RJ"] = 1


def deal_hand(n: int = 17) -> Counter:
    hand = Counter()
    while sum(hand.values()) < n:
        r = random.choice(RANKS)
        if hand[r] < CAPS[r]:
            hand[r] += 1
    return hand


def add_noise(hand: Counter) -> list[str]:
    cards = list(hand.elements())
    if not cards:
        return []
    n_drop = random.randint(1, 2)
    dup = [r for r in hand if hand[r] >= 2]
    pool = dup or list(hand.keys())
    for _ in range(n_drop):
        if not cards:
            break
        r = random.choice(pool)
        if r in cards:
            cards.remove(r)
    for _ in range(n_drop):
        r = "RJ" if random.random() < 0.08 else random.choice(RANKS[:13])
        cards.append(r)
    random.shuffle(cards)
    return cards


def acc(belief: Counter, truth: Counter) -> tuple[float, bool]:
    n = sum(truth.values())
    wrong = sum(abs(belief[r] - truth[r]) for r in set(belief) | set(truth)) // 2
    return (1.0 - wrong / n if n else 1.0, belief == truth)


def run(rounds: int = 2000) -> None:
    stat = {"A": [[], 0], "A3": [[], 0], "B": [[], 0]}
    for _ in range(rounds):
        truth = deal_hand(17)

        # A: 单帧观测基线
        obs = add_noise(truth)
        a, ea = acc(Counter(obs), truth)
        stat["A"][0].append(a); stat["A"][1] += ea

        # A3: 三读投票 prior
        prior = vote_initial_hand([add_noise(truth) for _ in range(3)], expected=17)
        a3, ea3 = acc(prior, truth)
        stat["A3"][0].append(a3); stat["A3"][1] += ea3

        # B: 出牌后, 从投票 prior 单调校正
        truth2 = truth.copy()
        for p in random.sample(list(truth2.elements()), k=random.randint(1, 3)):
            truth2[p] -= 1
        truth2 = Counter({r: c for r, c in truth2.items() if c > 0})
        obs2 = add_noise(truth2)
        belief, _ = reconcile_hand(obs2, prior, expected=sum(truth2.values()))
        b, eb = acc(belief, truth2)
        stat["B"][0].append(b); stat["B"][1] += eb

    print(f"合成测试 {rounds} 轮:")
    for name, label in [("A", "A  单帧观测(基线)"),
                        ("A3", "A3 三读投票 prior"),
                        ("B", "B  出牌后(投票prior+单调校正)")]:
        accs, ex = stat[name]
        print(f"  {label:<22} 逐张 {sum(accs)/len(accs)*100:6.2f}%   完全一致 {ex/rounds*100:6.2f}%")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 2000)
