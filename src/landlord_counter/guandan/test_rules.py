"""掼蛋规则/AI 属性测试(≥20 用例 + 500 局随机属性测试)。

运行: cd /project1/landlord-counter && PYTHONPATH=src python3 src/landlord_counter/guandan/test_rules.py
全部通过时打印 "通过 N 项, 失败 0 项" 并以 0 退出; 有失败则以 1 退出。
"""
from __future__ import annotations

import random
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from landlord_counter.guandan import rules as R                      # noqa: E402
from landlord_counter.guandan.ai import GameState, choose_play, NAN_DU  # noqa: E402

PASS = 0
FAIL = 0
FAIL_MSGS: list = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAIL_MSGS.append(f"✗ {name}: {detail}")
        print(f"✗ {name}: {detail}")


def C(tokens):                       # 令牌 -> Card 列表
    return R.cards_from_tokens(tokens)


def G(tokens):                       # 令牌 -> Group
    return R.identify(C(tokens))


def ids(cards):
    return sorted(c.id for c in cards)


def run():
    R.she_zhi_ji_pai(2)              # 本局级牌 = 2

    # ---------------- 牌组 / 发牌 ----------------
    deck = R.chuang_jian_pai_zu()
    check("牌组108张", len(deck) == 108, f"got {len(deck)}")
    check("牌组id唯一", len({c.id for c in deck}) == 108)
    cnt = R.tong_ji_paizhi(deck)
    check("每点数8张(2..A)", all(cnt[z] == 8 for z in range(2, 15)),
          str({z: cnt[z] for z in range(2, 15)}))
    check("王各2张", cnt[15] == 2 and cnt[16] == 2)
    fp = R.fa_pai(random.Random(1))
    check("发牌4家x27", all(len(v) == 27 for v in fp.values()), str({k: len(v) for k, v in fp.items()}))

    # ---------------- 级牌 / 主牌语义 ----------------
    check("王>级牌>A>普通",
          R.huo_qu_shiji_paizhi(16) > R.huo_qu_shiji_paizhi(15) > R.huo_qu_shiji_paizhi(2)
          > R.huo_qu_shiji_paizhi(14) > R.huo_qu_shiji_paizhi(13) > R.huo_qu_shiji_paizhi(10))
    check("shi_ji_pai", R.shi_ji_pai(2) and not R.shi_ji_pai(3))
    h2, s2 = R.parse_card("2h"), R.parse_card("2s")
    check("红桃级牌=主牌", R.shi_zhu_pai(h2) and not R.shi_zhu_pai(s2))
    check("非级牌红桃非主牌", not R.shi_zhu_pai(R.parse_card("5h")))
    px = R.pai_xu(C(["3s", "2s", "As", "RJ", "Ks"]))
    check("排序:王>级牌>A>K>3",
          px[0].zhi == 16 and px[1].zhi == 2 and px[2].zhi == 14 and px[3].zhi == 13,
          str([c.zhi for c in px]))

    # ---------------- 牌型识别 ----------------
    check("单张", G(["5s"]).xing == R.PAI_XING["DAN_ZHANG"])
    check("对子", G(["5s", "5h"]).xing == R.PAI_XING["DUI_ZI"])
    check("三张", G(["5s", "5h", "5c"]).xing == R.PAI_XING["SAN_ZHANG"])
    check("三带二", G(["5s", "5h", "5c", "8s", "8h"]).xing == R.PAI_XING["SAN_DAI_ER"])
    check("炸弹4", G(["5s", "5h", "5c", "5d"]).xing == R.PAI_XING["ZHA_DAN"]
          and G(["5s", "5h", "5c", "5d"]).chang_du == 4)
    check("炸弹5", G(["5s", "5h", "5c", "5d", "5s"]).chang_du == 5)
    g6 = G(["5s", "5h", "5c", "5d", "5s", "5h"])
    check("炸弹6", g6.xing == R.PAI_XING["ZHA_DAN"] and g6.chang_du == 6)
    check("天王炸", G(["BJ", "BJ", "RJ", "RJ"]).xing == R.PAI_XING["TIAN_WANG_ZHA"])
    check("顺子5(混合花色)", G(["3s", "4h", "5c", "6d", "7s"]).xing == R.PAI_XING["SHUN_ZI"])
    gs6 = G(["9s", "10h", "Jc", "Qd", "Ks", "As"])
    check("顺子6(9..A)", gs6.xing == R.PAI_XING["SHUN_ZI"] and gs6.chang_du == 6)
    check("顺子含2非法", G(["10s", "Jh", "Qc", "Kd", "2s"]).xing != R.PAI_XING["SHUN_ZI"])
    gld = G(["3s", "3h", "4s", "4h", "5s", "5h"])
    check("连对3", gld.xing == R.PAI_XING["LIAN_DUI"] and gld.chang_du == 3)
    gsl = G(["3s", "3h", "3c", "4s", "4h", "4c", "5s", "5h", "5c"])
    check("三连3", gsl.xing == R.PAI_XING["SAN_LIAN"] and gsl.chang_du == 3)
    ggb = G(["3s", "3h", "3c", "4s", "4h", "4c"])
    check("钢板(两连三)", ggb.xing == R.PAI_XING["GANG_BAN"] and ggb.chang_du == 2)
    gfj = G(["5s", "5h", "5c", "6s", "6h", "6c", "8s", "9h"])
    check("飞机(单翼)", gfj.xing == R.PAI_XING["FEI_JI"] and gfj.chang_du == 2)
    gfj2 = G(["5s", "5h", "5c", "6s", "6h", "6c", "8s", "8h", "9s", "9h"])
    check("飞机(对翼)", gfj2.xing == R.PAI_XING["FEI_JI"] and gfj2.chang_du == 2)
    ths = G(["3s", "4s", "5s", "6s", "7s"])
    check("同花顺", ths.xing == R.PAI_XING["TONG_HUA_SHUN"] and ths.chang_du == 5 and ths.hua == 0)
    check("四带二", G(["5s", "5h", "5c", "5d", "3s", "8h"]).xing == R.PAI_XING["SI_DAI_ER"])
    check("无效(2+3)", G(["2s", "3h"]).is_invalid)

    # ---------------- 主牌(红桃级牌)万能 ----------------
    gw1 = G(["2h", "5s"])
    check("主牌万能:成对子", gw1.xing == R.PAI_XING["DUI_ZI"] and gw1.zhu_zhi == 5 and gw1.wild_used == 1)
    gw2 = G(["2h", "2h", "5s", "5h", "5c"])
    check("主牌万能:凑5张炸弹", gw2.xing == R.PAI_XING["ZHA_DAN"] and gw2.chang_du == 5 and gw2.wild_used == 2)
    gw3 = G(["3s", "4s", "5s", "6s", "2h"])
    check("主牌万能:补同花顺缺口", gw3.xing == R.PAI_XING["TONG_HUA_SHUN"] and gw3.wild_used == 1)
    check("主牌不能变王", R.identify(C(["2h", "2h", "BJ", "RJ"])).is_invalid)

    # ---------------- 压牌比较 ----------------
    check("单张A压K", R.can_beat(G(["As"]), G(["Ks"])))
    check("单张K不压A", not R.can_beat(G(["Ks"]), G(["As"])))
    check("级牌单张压A", R.can_beat(G(["2s"]), G(["As"])) and not R.can_beat(G(["As"]), G(["2s"])))
    check("对子不压单张", not R.can_beat(G(["9s", "9h"]), G(["Ks"])))
    check("炸弹压单张", R.can_beat(G(["3s", "3h", "3c", "3d"]), G(["As"])))
    check("5炸压4炸", R.can_beat(G(["5s", "5h", "5c", "5d", "5s"]), G(["9s", "9h", "9c", "9d"])))
    check("4炸不压5炸", not R.can_beat(G(["9s", "9h", "9c", "9d"]), G(["5s", "5h", "5c", "5d", "5s"])))
    check("6炸压5炸", R.can_beat(G(["5s", "5h", "5c", "5d", "5s", "5h"]), G(["9s", "9h", "9c", "9d", "9s"])))
    check("天王炸压6炸", R.can_beat(G(["BJ", "BJ", "RJ", "RJ"]),
                                 G(["9s", "9h", "9c", "9d", "9s", "9h"])))
    check("天王炸不互压", not R.can_beat(G(["BJ", "BJ", "RJ", "RJ"]), G(["BJ", "BJ", "RJ", "RJ"])))
    check("同花顺压4炸/5炸",
          R.can_beat(ths, G(["9s", "9h", "9c", "9d"])) and
          R.can_beat(ths, G(["9s", "9h", "9c", "9d", "9s"])))
    check("6炸压同花顺", R.can_beat(G(["9s", "9h", "9c", "9d", "9s", "9h"]), ths)
          and not R.can_beat(ths, G(["9s", "9h", "9c", "9d", "9s", "9h"])))
    check("顺子长度不同不可比",
          not R.can_beat(G(["4s", "5h", "6c", "7d", "8s"]),
                         G(["3s", "4h", "5c", "6d", "7s", "8h"])))

    # ---------------- 出牌校验 yan_zheng_chu_pai ----------------
    shou = C(["3s", "3h", "3c", "3d", "5s"])
    ok, reason, g = R.yan_zheng_chu_pai([shou[0], shou[1], shou[2], shou[3]], shou, None)
    check("校验:自由出炸弹合法", ok and g.xing == R.PAI_XING["ZHA_DAN"], reason)
    ok, reason, _ = R.yan_zheng_chu_pai([R.Card(R.PAI_ZHI["JIU"], R.HUA_SE["HEI_TAO"], 999)], shou, None)
    check("校验:没有的牌", not ok and "没有" in reason, reason)
    ok, reason, _ = R.yan_zheng_chu_pai([R.parse_card("2s"), R.parse_card("3h")], shou, None)
    check("校验:无效牌型", not ok, reason)
    ok, reason, _ = R.yan_zheng_chu_pai(C(["5s"]), shou, G(["As"]))
    check("校验:压不过", not ok and "压不过" in reason, reason)

    # ---------------- 候选生成 find_all_plays ----------------
    hand = C(["3s", "3h", "3c", "3d", "4s", "5s", "6s", "7s", "8h", "10c", "Jd", "Qs", "Ks", "As", "2h"])
    cands = R.find_all_plays(hand, G(["5s"]), 2)
    ok_all = bool(cands) and all(R.can_beat(c, G(["5s"])) and not c.is_invalid for c in cands)
    check("find_all_plays:全部合法且能压", ok_all, f"{len(cands)}个候选")
    hid = ids(hand)
    inside = True
    for c in cands:
        for card in c.cards:
            if card.id not in hid:
                inside = False
    check("find_all_plays:候选牌均来自手牌", inside)
    empty = R.find_all_plays(C(["3s", "4h"]), G(["9s", "9h", "9c", "9d", "9s", "9h"]), 2)
    check("find_all_plays:无可压牌时为空", len(empty) == 0)

    # ---------------- AI 决策 choose_play ----------------
    lp = G(["5s"])
    ai = choose_play(hand, lp, GameState(shi_dui_you=False, nan_du=NAN_DU["ZHONG_DENG"],
                                         rng=random.Random(3)))
    check("AI:非队友必出合法牌", ai is not None and R.can_beat(ai, lp), str(ai))
    first = choose_play(hand, None, GameState(rng=random.Random(1)))
    check("AI:首出返回合法牌型", first is not None and not first.is_invalid, str(first))
    team_pass = choose_play(hand, lp, GameState(shi_dui_you=True, nan_du=NAN_DU["ZHONG_DENG"],
                                                rng=random.Random(0)))
    check("AI:队友出牌时让牌(None)", team_pass is None, str(team_pass))
    no_beat = choose_play(C(["3s", "4h"]), G(["9s", "9h", "9c", "9d"]),
                          GameState(rng=random.Random(1)))
    check("AI:无解不出", no_beat is None, str(no_beat))

    # ---------------- 贡牌 / 升级 / 队伍 ----------------
    gong_hand = C(["3s", "2s", "As"])
    _gong = R.zhao_zui_da_pai(gong_hand, 2)
    check("贡牌=最大牌(级牌)", _gong is not None and _gong.zhi == 2)
    huan_hand = C(["3s", "4s", "5s"])
    ex = huan_hand[0].id           # 排除 3
    _huan = R.zhao_zui_xiao_pai(huan_hand, ex, 2)
    check("还牌=最小牌(排除贡牌)", _huan is not None and _huan.zhi == 4)
    check("升级:双上=3", R.ji_suan_sheng_ji(1, 2) == 3)
    check("升级:双下=3", R.ji_suan_sheng_ji(3, 4) == 3)
    check("升级:单下=2", R.ji_suan_sheng_ji(1, 4) == 2)
    check("升级:普通=1", R.ji_suan_sheng_ji(1, 3) == 1)
    check("下一级牌:逢A必打", R.huo_qu_xia_yi_ji_pai(14) == 14 and R.huo_qu_xia_yi_ji_pai(5) == 6)
    check("队友/对手位置",
          R.huo_qu_dui_you(0) == 2 and R.huo_qu_dui_shou(0) == [1, 3]
          and R.shi_fou_dui_you(1, 3) and not R.shi_fou_dui_you(0, 1))
    res1 = R.ji_suan_jie_guo([R.WEI_ZHI["NAN"], R.WEI_ZHI["BEI"], R.WEI_ZHI["XI"], R.WEI_ZHI["DONG"]], 2)
    check("结算:南北双上升3级", res1["sheng_fang"] == "dui_wu1" and res1["sheng_ji_shu"] == 3
          and res1["xin_ji_pai"] == 5, str(res1))
    res2 = R.ji_suan_jie_guo([R.WEI_ZHI["XI"], R.WEI_ZHI["DONG"], R.WEI_ZHI["NAN"], R.WEI_ZHI["BEI"]], 2)
    check("结算:东西双上", res2["sheng_fang"] == "dui_wu2" and res2["sheng_ji_shu"] == 3, str(res2))
    gx = R.huo_qu_gong_huan_xin_xi(3, 0)
    check("贡还:末游向头游贡", gx["xu_yao_gong_pai"] and gx["gong_pai_zhe"] == 3 and gx["shou_pai_zhe"] == 0)
    gx2 = R.huo_qu_gong_huan_xin_xi(2, 0)
    check("贡还:同队不贡", gx2["xu_yao_gong_pai"] is False)

    # ---------------- 随机属性测试: 500 局压牌候选 ----------------
    rng = random.Random(20240910)
    bad = 0
    bad_re = 0
    bad_hand = 0
    rounds_with_cand = 0
    total_cand = 0
    for _ in range(500):
        d = R.chuang_jian_pai_zu()
        rng.shuffle(d)
        h = d[:27]
        lg = None
        for _try in range(8):                      # 尽量取到一个合法的"上家牌型"
            pool = d[27 + _try * 9: 27 + _try * 9 + rng.randrange(1, 7)]
            if len(pool) < 1:
                break
            cand_last = R.identify(pool, 2)
            if not cand_last.is_invalid:
                lg = cand_last
                break
        if lg is None:
            continue
        cs = R.find_all_plays(h, lg, 2)
        if cs:
            rounds_with_cand += 1
        total_cand += len(cs)
        hids = ids(h)
        for c in cs:
            if c.is_invalid or not R.can_beat(c, lg):
                bad += 1
                if bad <= 3:
                    print(f"  ✗ 非法候选: 压 {lg} 却出 {c}")
            re = R.identify(c.cards, 2)
            if (re.xing, re.zhu_zhi, re.chang_du) != (c.xing, c.zhu_zhi, c.chang_du):
                bad_re += 1
                if bad_re <= 3:
                    print(f"  ✗ 重识别不一致: {c} -> {re}")
            for card in c.cards:
                if card.id not in hids:
                    bad_hand += 1
                    if bad_hand <= 3:
                        print(f"  ✗ 候选含手牌外牌: {card}")
    check("500局:候选全部合法且能压上家", bad == 0, f"非法 {bad} 个")
    check("500局:候选重识别自洽", bad_re == 0, f"不一致 {bad_re} 个")
    check("500局:候选牌均来自手牌", bad_hand == 0, f"越界 {bad_hand} 个")
    print(f"  [属性] 500 局: 出现候选的局数 {rounds_with_cand}, 候选总数 {total_cand}")

    # ---------------- 随机属性测试: 500 局自由出牌候选 ----------------
    bad2 = 0
    bad2_hand = 0
    for _ in range(500):
        d = R.chuang_jian_pai_zu()
        rng.shuffle(d)
        h = d[:27]
        cs = R.find_all_plays(h, None, 2)
        hids = ids(h)
        for c in cs:
            if c.is_invalid or not R.can_beat(c, None):
                bad2 += 1
            for card in c.cards:
                if card.id not in hids:
                    bad2_hand += 1
    check("500局:自由出牌候选合法", bad2 == 0, f"非法 {bad2} 个")
    check("500局:自由出牌候选来自手牌", bad2_hand == 0, f"越界 {bad2_hand} 个")

    # ---------------- 随机属性测试: 200 局 AI 决策 ----------------
    bad_ai = 0
    ai_rng = random.Random(99)
    for _ in range(200):
        d = R.chuang_jian_pai_zu()
        ai_rng.shuffle(d)
        h = d[:27]
        pool = d[27:27 + ai_rng.randrange(1, 9)]
        lg = R.identify(pool, 2)
        last = None if lg.is_invalid else lg
        mv = choose_play(h, last, GameState(shi_dui_you=bool(ai_rng.getrandbits(1)),
                                          nan_du=ai_rng.choice([1, 2, 3]), rng=ai_rng))
        if mv is not None:
            if mv.is_invalid or not R.can_beat(mv, last):
                bad_ai += 1
            for card in mv.cards:
                if card.id not in ids(h):
                    bad_ai += 1
    check("200局:AI 返回必合法且能压(或不出)", bad_ai == 0, f"非法 {bad_ai} 个")

    print(f"\n通过 {PASS} 项, 失败 {FAIL} 项")
    if FAIL_MSGS:
        sys.exit(1)


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
