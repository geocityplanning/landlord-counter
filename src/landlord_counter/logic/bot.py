"""斗地主托管策略 bot v1（规则启发式, M3 换 DouZero）。

接口全部走 ddz_engine, 决策保证合法。策略(简单优先):
  - 叫分: 固定不叫(v1); 手上 ≥2 炸弹或 (A≥2 且 2≥2) 时叫 3 分
  - 领打(无上家): 最小单张; 若只有王/2能拆……v1 直接最小单张
  - 跟牌: 同型最小能压的组合; 无普通牌可压时: 若炸弹能压且(只剩≤3张 或 对方只剩≤2张)才炸, 否则不出
"""
from __future__ import annotations

from landlord_counter.logic import ddz_engine as E


def decide_bid(hand_ranks: list[int]) -> int:
    """0=不叫 1/2/3=叫分"""
    cm = {}
    for r in hand_ranks:
        cm[r] = cm.get(r, 0) + 1
    bombs = sum(1 for v in cm.values() if v >= 4) + (1 if 16 in cm and 17 in cm else 0)
    strong = cm.get(14, 0) >= 2 and cm.get(15, 0) >= 2
    return 3 if bombs >= 2 or strong else 0


def _score(g: E.Group) -> tuple:
    """排序键: 越小越优先。普通牌型>炸弹>火箭; 同力量比点数。"""
    power = {E.T.BOMB: 2, E.T.ROCKET: 3}.get(g.type, 1)
    return (power, g.main_rank)


def pick_lead(hand_ranks: list[int]) -> E.Group:
    """领打: 最小单张(除2/王外的散牌优先, 只有2/王时出最小)。"""
    singles = sorted(r for r in hand_ranks)
    # 优先出 3..A 里的最小; 无则出最小(2或王)
    prefer = [r for r in singles if r <= 14]
    r = prefer[0] if prefer else singles[0]
    return E.Group(E.T.SINGLE, r, 1, [r])


def pick_follow(hand_ranks: list[int], last: E.Group | None) -> E.Group | None:
    """跟牌: 返回要出的组, None=不出。保证合法。"""
    if last is None or last.is_invalid:
        return pick_lead(hand_ranks)
    cands = [g for g in E.find_all_valid_plays(hand_ranks, last)]
    if not cands:
        return None
    normal = [g for g in cands if g.type not in (E.T.BOMB, E.T.ROCKET)]
    if normal:
        return min(normal, key=_score)
    # 只剩炸弹/火箭可压
    if len(hand_ranks) <= 3 or (len(cands) and any(g.type == E.T.BOMB for g in cands) and len(last.ranks) >= 4):
        bombs = [g for g in cands if g.type in (E.T.BOMB, E.T.ROCKET)]
        return min(bombs, key=_score) if bombs else None
    return None
