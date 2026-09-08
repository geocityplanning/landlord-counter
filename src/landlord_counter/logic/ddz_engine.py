"""斗地主牌型引擎 —— 由 wishday 源码 CardRuleEngine.kt 逐行移植(保证与游戏校验器一致)。

rank 编码(与 wishday 一致): 3..10=3..10, 11=J, 12=Q, 13=K, 14=A, 15=2, 16=小(BJ), 17=大(RJ)
牌型: ROCKET(火箭) SINGLE PAIR TRIPLE TRIPLE_ONE(三带一) TRIPLE_TWO(三带二)
      STRAIGHT(顺子≥5) STRAIGHT_PAIR(连对≥3对) PLANE/PLANE_SINGLE/PLANE_PAIR(飞机)
      BOMB INVALID。注意: wishday 不支持"四带二"。

length 语义: 顺子=张数, 连对=对数, 飞机=连数, 其余=1。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class T(Enum):
    INVALID = 0
    SINGLE = 1
    PAIR = 2
    TRIPLE = 3
    TRIPLE_ONE = 4
    TRIPLE_TWO = 5
    STRAIGHT = 6
    STRAIGHT_PAIR = 7
    PLANE = 8
    PLANE_SINGLE = 9
    PLANE_PAIR = 10
    BOMB = 11
    ROCKET = 12


# 我们的牌面字符串 <-> rank int (rank 即 wishday Card.rank)
TOK = ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2", "BJ", "RJ"]


def token_to_rank(t: str) -> int:
    if t in ("BJ", "小"):
        return 16
    if t in ("RJ", "大"):
        return 17
    try:
        return int(t)
    except ValueError:
        return "JQKA".index(t) + 11


def rank_to_token(r: int) -> str:
    if r == 16:
        return "小"
    if r == 17:
        return "大"
    if r <= 10:
        return str(r)
    return "JQKA"[r - 11]


@dataclass
class Group:
    type: T = T.INVALID
    main_rank: int = 0
    length: int = 0
    ranks: list[int] = field(default_factory=list)  # 参与的所有 rank(排好序)

    @property
    def is_invalid(self) -> bool:
        return self.type == T.INVALID

    def __repr__(self) -> str:
        return f"<{self.type.name} [{','.join(rank_to_token(r) for r in self.ranks)}]>"


INVALID = Group()


def identify(cards: list[int]) -> Group:
    if not cards:
        return INVALID
    s = sorted(cards)
    n = len(s)
    rc = {}
    for r in s:
        rc[r] = rc.get(r, 0) + 1
    counts = sorted(rc.values(), reverse=True)

    if n == 2 and s[0] == 16 and s[1] == 17:
        return Group(T.ROCKET, 17, 1, s)
    if n == 1:
        return Group(T.SINGLE, s[0], 1, s)
    if n == 2 and counts == [2]:
        return Group(T.PAIR, s[0], 1, s)
    if n == 4 and counts == [4]:
        return Group(T.BOMB, s[0], 1, s)
    if n == 3 and counts == [3]:
        return Group(T.TRIPLE, s[1], 1, s)
    if n == 4 and counts == [3, 1]:
        main = next(k for k, v in rc.items() if v == 3)
        return Group(T.TRIPLE_ONE, main, 1, s)
    if n == 5 and counts == [3, 2]:
        main = next(k for k, v in rc.items() if v == 3)
        return Group(T.TRIPLE_TWO, main, 1, s)
    if n >= 5 and all(v == 1 for v in counts) and _consecutive(s) and all(r <= 14 for r in s):
        return Group(T.STRAIGHT, s[0], n, s)
    if n >= 6 and n % 2 == 0 and all(v == 2 for v in counts) and _consecutive_group(s, 2) and all(r <= 14 for r in s):
        return Group(T.STRAIGHT_PAIR, s[0], n // 2, s)
    return _identify_plane(s, rc, n)


def _consecutive(s: list[int]) -> bool:
    return all(s[i] == s[i - 1] + 1 for i in range(1, len(s)))


def _consecutive_group(s: list[int], gs: int) -> bool:
    if len(s) % gs != 0:
        return False
    g = [s[i] for i in range(0, len(s), gs)]
    return _consecutive(g)


def _identify_plane(s: list[int], rc: dict[int, int], n: int) -> Group:
    triples = sorted(k for k, v in rc.items() if v >= 3)
    if len(triples) < 2:
        return INVALID
    best_start, best_len = -1, 0
    for i in range(len(triples)):
        if triples[i] > 14:
            break
        ln = 1
        for j in range(i + 1, len(triples)):
            if triples[j] == triples[j - 1] + 1 and triples[j] <= 14:
                ln += 1
            else:
                break
        if ln >= 2 and ln > best_len:
            best_start, best_len = i, ln
    if best_len < 2:
        return INVALID
    plane_ranks = triples[best_start:best_start + best_len]
    rem = n - best_len * 3
    if rem == 0:
        cards = [r for r in s if r in plane_ranks]
        return Group(T.PLANE, plane_ranks[0], best_len, cards)
    if rem == best_len:
        non = [r for r in s if r not in plane_ranks]
        nc = {}
        for r in non:
            nc[r] = nc.get(r, 0) + 1
        if all(v == 1 for v in nc.values()) and len(nc) == best_len:
            return Group(T.PLANE_SINGLE, plane_ranks[0], best_len, s)
        return INVALID
    if rem == best_len * 2:
        non = [r for r in s if r not in plane_ranks]
        nc = {}
        for r in non:
            nc[r] = nc.get(r, 0) + 1
        if len(nc) == best_len and all(v == 2 for v in nc.values()):
            return Group(T.PLANE_PAIR, plane_ranks[0], best_len, s)
        return INVALID
    return INVALID


def compare(g1: Group, g2: Group) -> int:
    """正=g1大, 负=g2大, 0=不可比。"""
    if g1.type == T.ROCKET:
        return 1
    if g2.type == T.ROCKET:
        return -1
    if g1.type == T.BOMB and g2.type != T.BOMB:
        return 1
    if g2.type == T.BOMB and g1.type != T.BOMB:
        return -1
    if g1.type == g2.type and g1.length == g2.length:
        return (g1.main_rank > g2.main_rank) - (g1.main_rank < g2.main_rank)
    return 0


def is_valid_play(played: Group, last: Group | None) -> bool:
    if played.is_invalid:
        return False
    if last is None or last.is_invalid:
        return True
    if played.type == T.ROCKET:
        return True
    if played.type == T.BOMB and last.type != T.BOMB and last.type != T.ROCKET:
        return True
    if played.type == last.type and played.length == last.length:
        return played.main_rank > last.main_rank
    if played.type == T.BOMB and last.type == T.BOMB:
        return played.main_rank > last.main_rank
    return False


# ---------------- 候选生成 ----------------

def find_all_valid_plays(hand: list[int], last: Group | None) -> list[Group]:
    if not hand:
        return []
    s = sorted(hand)
    cm = {}
    for r in s:
        cm[r] = cm.get(r, 0) + 1
    if last is None or last.is_invalid:
        return _all_possible(s, cm)
    res: list[Group] = []
    lt = last.type
    if lt == T.SINGLE:
        for c in s:
            if c > last.main_rank:
                res.append(Group(T.SINGLE, c, 1, [c]))
    elif lt == T.PAIR:
        for r, cnt in cm.items():
            if cnt >= 2 and r > last.main_rank:
                res.append(Group(T.PAIR, r, 1, [r, r]))
    elif lt == T.TRIPLE:
        for r, cnt in cm.items():
            if cnt >= 3 and r > last.main_rank:
                res.append(Group(T.TRIPLE, r, 1, [r] * 3))
    elif lt == T.TRIPLE_ONE:
        for r, cnt in cm.items():
            if cnt >= 3 and r > last.main_rank:
                k = next((x for x in s if x != r), None)
                if k is not None:
                    res.append(Group(T.TRIPLE_ONE, r, 1, [r] * 3 + [k]))
    elif lt == T.TRIPLE_TWO:
        for r, cnt in cm.items():
            if cnt >= 3 and r > last.main_rank:
                pk = next((x for x, c in cm.items() if x != r and c >= 2), None)
                if pk is not None:
                    res.append(Group(T.TRIPLE_TWO, r, 1, [r] * 3 + [pk, pk]))
    elif lt == T.STRAIGHT:
        res += _find_straights(s, cm, last.length, last.main_rank)
    elif lt == T.STRAIGHT_PAIR:
        res += _find_straight_pairs(s, cm, last.length, last.main_rank)
    elif lt == T.BOMB:
        for r, cnt in cm.items():
            if cnt >= 4 and r > last.main_rank:
                res.append(Group(T.BOMB, r, 1, [r] * 4))
    elif lt in (T.PLANE, T.PLANE_SINGLE, T.PLANE_PAIR):
        res += _find_planes(s, cm, last)
    if last.type != T.ROCKET:
        for r, cnt in cm.items():
            if cnt >= 4:
                bomb = Group(T.BOMB, r, 1, [r] * 4)
                if last.type != T.BOMB or r > last.main_rank:
                    if not any(g.type == T.BOMB and g.main_rank == r for g in res):
                        res.append(bomb)
        if 16 in cm and 17 in cm:
            res.append(Group(T.ROCKET, 17, 1, [16, 17]))
    return res


def _all_possible(s: list[int], cm: dict[int, int]) -> list[Group]:
    res: list[Group] = []
    for r in sorted(cm):
        res.append(Group(T.SINGLE, r, 1, [r]))
    for r, cnt in cm.items():
        if cnt >= 2:
            res.append(Group(T.PAIR, r, 1, [r, r]))
    for r, cnt in cm.items():
        if cnt >= 3:
            trip = [r] * 3
            res.append(Group(T.TRIPLE, r, 1, trip))
            k = next((x for x in s if x != r), None)
            if k is not None:
                res.append(Group(T.TRIPLE_ONE, r, 1, trip + [k]))
            pk = next((x for x, c in cm.items() if x != r and c >= 2), None)
            if pk is not None:
                res.append(Group(T.TRIPLE_TWO, r, 1, trip + [pk, pk]))
    for r, cnt in cm.items():
        if cnt >= 4:
            res.append(Group(T.BOMB, r, 1, [r] * 4))
    if 16 in cm and 17 in cm:
        res.append(Group(T.ROCKET, 17, 1, [16, 17]))
    res += _short_straights(s, cm)
    res += _short_straight_pairs(s, cm)
    res += _free_planes(s, cm)
    return res


def _short_straights(s: list[int], cm: dict[int, int]) -> list[Group]:
    res = []
    ranks = sorted(r for r in cm if 3 <= r <= 14)
    i = 0
    while i < len(ranks):
        j = i
        while j + 1 < len(ranks) and ranks[j + 1] == ranks[j] + 1:
            j += 1
        run = j - i + 1
        if run >= 5:
            for ln in range(5, run + 1):
                cards = [next(x for x in s if x == ranks[i + k]) for k in range(ln)]
                res.append(Group(T.STRAIGHT, ranks[i], ln, cards))
        i = j + 1
    return res


def _short_straight_pairs(s: list[int], cm: dict[int, int]) -> list[Group]:
    res = []
    pr = sorted(r for r, c in cm.items() if c >= 2 and 3 <= r <= 14)
    i = 0
    while i < len(pr):
        j = i
        while j + 1 < len(pr) and pr[j + 1] == pr[j] + 1:
            j += 1
        run = j - i + 1
        if run >= 3:
            for ln in range(3, run + 1):
                cards = [r for k in range(ln) for r in [pr[i + k]] * 2]
                res.append(Group(T.STRAIGHT_PAIR, pr[i], ln, cards))
        i = j + 1
    return res


def _free_planes(s: list[int], cm: dict[int, int]) -> list[Group]:
    res = []
    tr = sorted(r for r, c in cm.items() if c >= 3 and 3 <= r <= 14)
    i = 0
    while i < len(tr):
        j = i
        while j + 1 < len(tr) and tr[j + 1] == tr[j] + 1:
            j += 1
        run = j - i + 1
        if run >= 2:
            for ln in range(2, run + 1):
                pr = tr[i:i + ln]
                pc = [r for k in range(ln) for r in [pr[k]] * 3]
                res.append(Group(T.PLANE, pr[0], ln, pc))
                used = set(pr)
                wings = sorted(r for r in cm if r not in used and 3 <= r <= 14)[:ln]
                if len(wings) >= ln:
                    res.append(Group(T.PLANE_SINGLE, pr[0], ln, pc + wings))
                pw = [r for r in sorted(cm) if r not in used and 3 <= r <= 14 and cm[r] >= 2][:ln]
                if len(pw) >= ln:
                    res.append(Group(T.PLANE_PAIR, pr[0], ln, pc + [r for k in range(ln) for r in [pw[k]] * 2]))
        i = j + 1
    return res


def _find_straights(s: list[int], cm: dict[int, int], length: int, min_rank: int) -> list[Group]:
    res = []
    avail = sorted(r for r in cm if 3 <= r <= 14)
    for si in range(len(avail)):
        start = avail[si]
        if start <= min_rank or start + length - 1 > 14:
            continue
        seq = [r for r in range(start, start + length) if r in cm]
        if len(seq) >= length:
            cards = [next(x for x in s if x == r) for r in seq[:length]]
            res.append(Group(T.STRAIGHT, seq[0], length, cards))
    return res


def _find_straight_pairs(s: list[int], cm: dict[int, int], length: int, min_rank: int) -> list[Group]:
    res = []
    pr = sorted(r for r, c in cm.items() if c >= 2 and 3 <= r <= 14)
    for si in range(len(pr)):
        start = pr[si]
        if start <= min_rank or start + length - 1 > 14:
            continue
        seq = [r for r in range(start, start + length) if r in cm and cm[r] >= 2]
        if len(seq) >= length:
            cards = [r for k in range(length) for r in [seq[k]] * 2]
            res.append(Group(T.STRAIGHT_PAIR, seq[0], length, cards))
    return res


def _find_planes(s: list[int], cm: dict[int, int], last: Group) -> list[Group]:
    res = []
    tr = sorted(r for r, c in cm.items() if c >= 3 and 3 <= r <= 14)
    for si in range(len(tr)):
        start = tr[si]
        if start <= last.main_rank or start + last.length - 1 > 14:
            continue
        seq = [r for r in range(start, start + last.length) if r in cm and cm[r] >= 3]
        if len(seq) < last.length:
            continue
        pc = [r for k in range(last.length) for r in [seq[k]] * 3]
        if last.type == T.PLANE:
            res.append(Group(T.PLANE, seq[0], last.length, pc))
        elif last.type == T.PLANE_SINGLE:
            wings = [r for r in s if r not in seq][:last.length]
            if len(wings) >= last.length:
                res.append(Group(T.PLANE_SINGLE, seq[0], last.length, pc + wings))
        elif last.type == T.PLANE_PAIR:
            used = set(seq)
            pw = [r for r in sorted(cm) if r not in used and cm[r] >= 2][:last.length]
            if len(pw) >= last.length:
                res.append(Group(T.PLANE_PAIR, seq[0], last.length, pc + [r for k in range(last.length) for r in [pw[k]] * 2]))
    return res


# ---------------- 便捷接口(字符串层) ----------------

def identify_str(cards_tokens: list[str]) -> Group:
    return identify([token_to_rank(t) for t in cards_tokens])


def find_all_valid_str(hand_tokens: list[str], last_tokens: list[str] | None) -> list[Group]:
    last = identify_str(last_tokens) if last_tokens else None
    return find_all_valid_plays([token_to_rank(t) for t in hand_tokens], last)


def group_to_str(g: Group) -> str:
    return " ".join(rank_to_token(r) for r in g.ranks)
