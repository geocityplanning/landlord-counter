"""ddz_engine 属性测试: 移植合法性 + 候选生成自洽性。"""
import random
import sys
import traceback

from landlord_counter.logic import ddz_engine as E

PASS = 0
FAIL = 0
FAIL_MSGS = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAIL_MSGS.append(f"✗ {name}: {detail}")
        print(f"✗ {name}: {detail}")


def random_hand(n=17, seed=None):
    if seed is not None:
        random.seed(seed)
    deck = []
    for r in range(3, 16):
        deck += [r] * 4
    deck += [16, 17]
    random.shuffle(deck)
    return deck[:n]


def run():
    # ---- 牌型识别 ----
    cases = [
        ([3], "SINGLE"), ([11, 11], "PAIR"), ([12, 12, 12], "TRIPLE"),
        ([15, 15, 15, 15], "BOMB"), ([16, 17], "ROCKET"),
        ([3, 3, 3, 9], "TRIPLE_ONE"), ([5, 5, 5, 8, 8], "TRIPLE_TWO"),
        ([3, 4, 5, 6, 7], "STRAIGHT"), ([3, 3, 4, 4, 5, 5], "STRAIGHT_PAIR"),
        ([9, 10, 11, 12, 13, 14], "STRAIGHT"),           # 9..A
        ([10, 10, 10, 11, 11, 11], "PLANE"),            # 飞机2连不带
        ([8, 8, 8, 9, 9, 9, 3], "PLANE_SINGLE"),        # 2连+1翼?? 翼数需=len=2
        ([3, 4, 4, 4, 5, 5, 5], "PLANE_SINGLE"),        # 2连+2翼(3,4?) no: 4,5 三张已在飞机里
    ]
    # 上面的案例里 444555+3 只有1翼 → INVALID; 444555+3+6(3,6=2翼) → PLANE_SINGLE
    check("单张", E.identify([3]).type == E.T.SINGLE)
    check("对子", E.identify([11, 11]).type == E.T.PAIR)
    check("三张", E.identify([12, 12, 12]).type == E.T.TRIPLE)
    check("炸弹", E.identify([15, 15, 15, 15]).type == E.T.BOMB)
    check("火箭", E.identify([16, 17]).type == E.T.ROCKET)
    check("三带一", E.identify([3, 3, 3, 9]).type == E.T.TRIPLE_ONE)
    check("三带二", E.identify([5, 5, 5, 8, 8]).type == E.T.TRIPLE_TWO)
    check("顺子5", E.identify([3, 4, 5, 6, 7]).type == E.T.STRAIGHT)
    check("顺子6(9..A)", E.identify([9, 10, 11, 12, 13, 14]).type == E.T.STRAIGHT)
    check("顺子含2非法", E.identify([10, 11, 12, 13, 14, 15]).type != E.T.STRAIGHT)
    check("连对3", E.identify([3, 3, 4, 4, 5, 5]).type == E.T.STRAIGHT_PAIR)
    check("飞机不带", E.identify([10, 10, 10, 11, 11, 11]).type == E.T.PLANE)
    g = E.identify([4, 4, 4, 5, 5, 5, 3, 6])
    check("飞机带单(2翼)", g.type == E.T.PLANE_SINGLE, str(g))
    g = E.identify([4, 4, 4, 5, 5, 5, 3])
    check("2连+1翼非法", g.type != E.T.PLANE_SINGLE, str(g))
    g = E.identify([4, 4, 4, 5, 5, 5, 7, 7, 8, 8])
    check("飞机带对(2连+2对)", g.type == E.T.PLANE_PAIR, str(g))
    g = E.identify([10, 10, 10, 11, 11, 11, 12, 12, 12])
    check("飞机3连", g.type == E.T.PLANE and g.length == 3, str(g))

    # ---- 比较 ----
    check("炸弹压单", E.compare(E.Group(E.T.BOMB, 9, 1, []), E.Group(E.T.SINGLE, 15, 1, [])) > 0)
    check("火箭最大", E.compare(E.Group(E.T.ROCKET, 17, 1, []), E.Group(E.T.BOMB, 15, 1, [])) > 0)
    check("同型比点", E.compare(E.Group(E.T.PAIR, 12, 1, []), E.Group(E.T.PAIR, 10, 1, [])) > 0)
    check("不可比=0", E.compare(E.Group(E.T.STRAIGHT, 3, 5, []), E.Group(E.T.PAIR, 15, 1, [])) == 0)

    # ---- 管牌: 属性测试 ----
    bad = 0
    for seed in range(300):
        random.seed(seed)
        hand = random_hand()
        # 随机上家: 从随机牌组挑
        r = random.randrange(1, 20)
        pool = random_hand(n=r, seed=seed + 999)
        last = E.identify(pool)
        if last.is_invalid:
            continue
        cands = E.find_all_valid_plays(hand, last)
        for c in cands:
            if not E.is_valid_play(c, last):
                bad += 1
                if bad <= 3:
                    print(f"  ✗ 非法候选: 压 {last} 却出 {c}")
            # 自身重识别一致
            if not c.is_invalid:
                re = E.identify(c.ranks)
                if re.type != c.type or re.main_rank != c.main_rank or re.length != c.length:
                    bad += 1
                    print(f"  ✗ 重识别不一致: {c} → {re}")
    check("300局管牌候选全合法且自洽", bad == 0, f"非法 {bad} 个")

    # 自由出牌候选: 也需自身合法(自由出牌=任何合法牌型)
    bad2 = 0
    for seed in range(200):
        random.seed(seed + 5000)
        hand = random_hand()
        cands = E.find_all_valid_plays(hand, None)
        for c in cands:
            if not E.is_valid_play(c, None) or c.is_invalid:
                bad2 += 1
                if bad2 <= 3:
                    print(f"  ✗ 自由出牌非法候选: {c}")
            # 牌必须来自手牌
            hc = {}
            for x in hand:
                hc[x] = hc.get(x, 0) + 1
            cc = {}
            for x in c.ranks:
                cc[x] = cc.get(x, 0) + 1
            if any(v > hc.get(k, 0) for k, v in cc.items()):
                bad2 += 1
                print(f"  ✗ 候选含手牌外牌: {c}")
    check("200局自由出牌候选合法", bad2 == 0, f"非法 {bad2} 个")

    print(f"\n通过 {PASS} 项, 失败 {FAIL} 项")
    if FAIL_MSGS:
        sys.exit(1)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
