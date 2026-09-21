#!/usr/bin/env python3
#!/usr/bin/env python3
"""一致性核对: **我们的 rules.identify** vs **游戏本体 GameRules.jieXiPaiXing**

用户要求: "检查一下现有的这一套规则和我们用的掼蛋小游戏这个项目是否一致"

做法: 同一批牌(同点数/花色)分别喂给两边, 比 (牌型, 长度, 主值) ✓
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from landlord_counter.guandan import rules as R       # noqa: E402
from landlord_counter.platform.cdp import CDP        # noqa: E402

JIPAI = 2

# (名字, "点数+花色" 列表)  hua: 0♠ 1♥ 2♣ 3♦   zhi: 3..14(A), 2, 15小王, 16大王
CASES = [
    ("单张",            "5s"),
    ("对子",            "5s 5h"),
    ("三张",            "5s 5h 5c"),
    ("三带二",          "5s 5h 5c 9s 9h"),
    ("顺子5张",         "3s 4h 5c 6d 7s"),
    ("顺子6张(应无效)",  "3s 4h 5c 6d 7s 8h"),
    ("顺子10JQKA",      "10s Jh Qc Kd As"),
    ("连对3对",         "3s 3h 4c 4d 5s 5h"),
    ("连对2对(应无效)",  "3s 3h 4c 4d"),
    ("连对4对(应无效)",  "3s 3h 4c 4d 5s 5h 6c 6d"),
    ("钢板2组",         "5s 5h 5c 6s 6h 6c"),
    ("三连3组(应无效)",  "5s 5h 5c 6s 6h 6c 7s 7h 7c"),
    ("飞机(应无效)",     "5s 5h 5c 6s 6h 6c 3s 4h"),
    ("四带二(应无效)",   "5s 5h 5c 5d 3s 8h"),
    ("炸弹4张",         "5s 5h 5c 5d"),
    ("炸弹5张",         "5s 5h 5c 5d 5s"),
    ("炸弹6张",         "5s 5h 5c 5d 5s 5h"),
    ("炸弹7张",         "5s 5h 5c 5d 5s 5h 5c"),
    ("炸弹8张",         "5s 5h 5c 5d 5s 5h 5c 5d"),
    ("同花顺5张",       "3s 4s 5s 6s 7s"),
    ("同花顺6张(应无效)", "3s 4s 5s 6s 7s 8s"),
    ("天王炸",          "15s 15h 16s 16h"),
    ("无效2+3",         "2s 3h"),
    ("逢人配→三张5",    "WJ 5s 5h"),
    ("逢人配→炸弹5",    "WJ 5s 5h 5c 5d"),
]

HUA = {"s": 0, "h": 1, "c": 2, "d": 3}


def parse(spec):
    spec = spec.replace("WJ", f"{JP[0]}h")           # WJ = 红桃级牌(逢人配) ✓
    out = []
    for i, tok in enumerate(spec.split()):
        t = tok[:-1]
        h = tok[-1]
        z = {"A": 14, "K": 13, "Q": 12, "J": 11, "T": 10}.get(t.upper())
        if z is None:
            z = int(t)
        out.append({"zhi": z, "hua": HUA[h], "id": i + 1})
    return out


JP = [2]          # 级牌(运行时用游戏的实际级牌填进来 ✓)


def ours(cards):
    cs = [R.Card(zhi=c["zhi"], hua=c["hua"], id=c["id"]) for c in cards]
    g = R.identify(cs, JP[0])
    return (g.xing, g.chang_du, g.zhu_zhi)


def main() -> int:
    c = CDP()
    c.find_truth()
    # ★ 级牌**以游戏为准**(不去改游戏 ✗): 用"谁是逢人配"反推它的级牌 ✓
    #   (上次踩坑: 我 set 了游戏侧没生效 ⇒ 两边级牌不同 ⇒ 主值/逢人配全歪 ✗)
    jp = c.eval_js("(() => { for (let z = 2; z <= 14; z++) { "
                   "try { if (GameRules.shiZhuPai({zhi: z, hua: 1})) return z; } catch(e){} } "
                   "return 2; })()")
    jp = int(jp or 2)
    R.she_zhi_ji_pai(jp)
    JP[0] = jp
    print(f"  两边级牌统一为: {jp} (以游戏为准 ✓)")

    bad = 0
    print(f"  {'用例':<20}{'我们(型/长/主)':<20}{'游戏(型/长/主)':<20}判定")
    for name, spec in CASES:
        cards = parse(spec)
        try:
            o = ours(cards)
        except Exception as e:  # noqa: BLE001
            o = ("炸", str(e), "")
        js = json.dumps([[x["zhi"], x["hua"], x["id"]] for x in cards])
        try:
            r = c.eval_js(
                "(() => { const a = %s.map(x => ({zhi: x[0], hua: x[1], id: x[2]}));"
                " const r = GameRules.jieXiPaiXing(a);"
                " return [r.xing, r.changDu, r.zhuZhi]; })()" % js)
            g = tuple(r) if isinstance(r, list) else ("?",)
        except Exception as e:  # noqa: BLE001
            g = ("炸JS", str(e)[:20], "")
        same = (o == g)
        bad += (not same)
        print(f"  {name:<20}{str(o):<20}{str(g):<20}{'✓ 一致' if same else '✗ **不一致**'}")

    print()
    print(f"  ⇒ {len(CASES) - bad}/{len(CASES)} 一致" + ("  ✓✓ 两边规则完全对齐" if not bad else "  ⚠ 有不一致"))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
