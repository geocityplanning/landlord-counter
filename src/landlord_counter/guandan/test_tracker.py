"""掼蛋记牌器单测: 去重 / 轮次清空 / 余牌 / 未见池 / 守恒自检。

运行: cd /project1/landlord-counter && PYTHONPATH=src python3 src/landlord_counter/guandan/test_tracker.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from landlord_counter.guandan import rules as R      # noqa: E402
from landlord_counter.guandan.tracker import CardTracker  # noqa: E402

PASS = FAIL = 0
MSGS: list = []


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        MSGS.append(f"✗ {name} {extra}")


def C(zhi, hua=0, i=0):
    return R.Card(zhi, hua, i)


def test_basic() -> None:
    t = CardTracker()
    # 我方手牌 5 张: 5,5,7,A,小王
    t.set_my_hand([C(5), C(5), C(7), C(14), C(15)])
    check("我的手牌计数", t.my_hand[5] == 2 and t.my_hand[14] == 1 and t.my_hand[15] == 1)
    # 对家(北)出一手 999(三张)
    check("首次计入", t.observe("北", [C(9), C(9), C(9)]) is True)
    check("对家已出 9=3", t.played["北"][9] == 3)
    # 同一手牌再看到一次 → 去重
    check("同手牌去重", t.observe("北", [C(9), C(9), C(9)]) is False)
    check("去重计数", t.dup_skipped == 1 and t.played["北"][9] == 3)
    # 一轮结束(桌面清空) → 再出同样的牌应被计入
    t.table_cleared()
    check("轮次+1", t.rounds == 1)
    check("清空后可重复计入", t.observe("北", [C(9), C(9), C(9)]) is True and t.played["北"][9] == 6)


def test_counts() -> None:
    t = CardTracker()
    t.set_my_hand([C(3)] * 4)          # 我方 4 张 3(合法: 每点数共 8 张)
    t.observe("西", [C(3)] * 2)        # 下家出 2 张 3(合法)
    rc = t.remaining_counts()
    check("下家余 25", rc["西"] == 25, str(rc))
    check("对家余 27", rc["北"] == 27)
    st = t.state_for_rl()
    check("RL 状态 5 维(我方=手牌数 4)", len(st) == 5 and st[0] == 4, str(st))
    check("RL 合计 = 各家和", st[4] == sum(st[:4]), str(st))
    pool = t.unseen_pool()
    check("未见池: 3 剩 8-4-2=2", pool.get(3, 0) == 2, str(pool.get(3)))
    check("守恒: 未见 + 我手牌 + 已出 == 108", sum(pool.values()) + sum(t.my_hand.values()) + 2 == 108,
          f"pool={sum(pool.values())}")


def test_conservation() -> None:
    t = CardTracker()
    t.set_my_hand([C(6)] * 8)                       # 我方占满 6
    t.observe("东", [C(6)] * 4)                     # 上家又出 4 张 6 → 超出(8) → 应报警
    ok, viol = t.check()
    check("守恒校验能抓到超量", ok is False and any("上限8" in v for v in viol), str(viol))
    t2 = CardTracker()
    t2.set_my_hand([C(16)])                         # 大王 1 张
    t2.observe("南", [C(16), C(16)])                # 大王 2 → 合计 3 > 2 → 报警
    ok2, v2 = t2.check()
    check("大王上限=2", ok2 is False, str(v2))


def test_hand_keep_max() -> None:
    t = CardTracker()
    t.set_my_hand([C(i) for i in range(3, 13)])     # 10 张
    t.set_my_hand([C(i) for i in range(3, 8)])      # 残影少读 5 张 → 不应覆盖
    check("手牌取较大读数", sum(t.my_hand.values()) == 10, str(sum(t.my_hand.values())))


def test_table_end() -> None:
    """整副核对(用**合法**分布): 每点数 8 张 = 4 家各 2 张; 王各 2 → 每家 27 张。

    27 = 13 个点数 × 2 + 1 张王。四家打完 → 未见池为空。
    """
    t = CardTracker()
    deck = []
    for r in range(2, 15):
        deck += [C(r)] * 2                  # 每家 2 张 × 4 家 = 8 ✓
    # 4 张王(2 小王 + 2 大王)每家 1 张 → 每家 26 + 1 = 27 ✓
    jokers = [C(15, i=1), C(15, i=2), C(16, i=3), C(16, i=4)]
    hand = deck + [jokers[0]]
    t.set_my_hand(hand)
    for k, seat in enumerate(("西", "北", "东")):
        t.observe(seat, deck + [jokers[k + 1]])
    rc = t.remaining_counts()
    check("三家打完 → 余 0", all(rc[s] == 0 for s in ("西", "北", "东")), str(rc))
    ok, viol = t.check()
    check("合法分布无守恒告警", ok, str(viol))
    check("此时未见池 = 我方手牌(27)", sum(t.unseen_pool().values()) == 0,
          str(sum(t.unseen_pool().values())))


if __name__ == "__main__":
    test_basic()
    test_counts()
    test_conservation()
    test_hand_keep_max()
    test_table_end()
    print(f"通过 {PASS} 项, 失败 {FAIL} 项")
    for m in MSGS:
        print(" ", m)
    raise SystemExit(1 if FAIL else 0)
