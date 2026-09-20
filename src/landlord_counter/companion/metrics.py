"""伴随应用: **策略指标**(团队口径 ✓)—— 回答"打得好不好", 不是"出得对不对"

用户 2026-09-18 定: 掼蛋是 2v2 组队游戏 ⇒ **不能用胜负判断** ✗, 必须用**队伍口径** ✓
用户 2026-09-20 定: 先建指标, 之后任何策略优化才有尺子 ✓

口径
----
· 我方 = 座位 0 与 2(对家) / 对方 = 座位 1 与 3
· **主指标: 场均升级数(有符号)** —— 我方升级为正, 被对方升级为负 ✓
· 辅指标: 头游率 / **双上率**(前两名都被我方包揽 ✓) / 被双下率 / 队友名次分布

数据源
------
全部来自 `deal.result_json`(结算时由真值写入 ✓); 没有结算的局**不计入** ✓
本模块只做**统计** ✗ —— 不算牌型/不做决策(越界检验同 store.py ✓)
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 我方(座位 0)与对家(座位 2)是一队 ✓
MY_TEAM = (0, 2)
OPP_TEAM = (1, 3)


def team_of(seat: int) -> str:
    return "mine" if int(seat) in MY_TEAM else "opp"


@dataclass
class DealMetric:
    """一局的策略指标(团队口径 ✓)"""
    gid: str
    won: bool | None = None           # 我方是否获胜(队伍口径 ✓)
    sheng_ji: int = 0                 # 升级数(有符号: 正=我方升, 负=被对方升 ✓)
    tou_you: int | None = None        # 头游是哪家座位
    my_best: int | None = None        # 我方最好名次(1=头游)
    shuang_shang: bool = False        # 双上: 我方两人包揽前两名 ✓
    shuang_xia: bool = False          # 被双下: 对方包揽前两名 ✗
    ranks: list = field(default_factory=list)   # 四家名次: ranks[seat] = 名次


def metric_of_deal(gid: str, result: dict, my_seat: int = 0) -> DealMetric | None:
    """把一局的结算结果 → 策略指标 ✓(结算缺失/格式不全都返回 None, 不猜 ✗)"""
    if not result:
        return None
    m = DealMetric(gid=gid)
    won = result.get("won")
    m.won = None if won is None else bool(won)

    sj = result.get("shengJiShu")
    if sj is not None:
        # 我方赢 ⇒ 我方升级为正 ✓; 输 ⇒ 被对方升级, 记负 ✓
        m.sheng_ji = int(sj) * (1 if m.won else -1)

    youci = result.get("youCiList")          # 游次列表: 按出完牌的顺序排的座位号 ✓
    if isinstance(youci, list) and len(youci) == 4:
        ranks = [0] * 4
        for i, seat in enumerate(youci):
            if 0 <= int(seat) < 4:
                ranks[int(seat)] = i + 1
        m.ranks = ranks
        m.tou_you = int(youci[0])
        mine = [ranks[s] for s in MY_TEAM]
        m.my_best = min(mine)
        m.shuang_shang = mine[0] <= 2 and mine[1] <= 2      # 我方两人都在前两名 ✓
        opp = [ranks[s] for s in OPP_TEAM]
        m.shuang_xia = opp[0] <= 2 and opp[1] <= 2          # 对方包揽前两名 ✗
    else:
        ty = result.get("touYou")
        m.tou_you = int(ty) if ty is not None else None
        if m.tou_you is not None:
            m.my_best = 1 if team_of(m.tou_you) == "mine" else None
    return m


def aggregate(metrics: list[DealMetric]) -> dict:
    """汇总 —— **只统计有结算的局** ✓(没结算的不算, 不拿没打完的充数 ✗)"""
    ms = [x for x in metrics if x is not None and (x.won is not None or x.ranks)]
    n = len(ms)
    if not n:
        return {"deals": 0, "note": "还没有带结算的牌局"}
    wins = sum(1 for x in ms if x.won)
    shang = sum(1 for x in ms if x.shuang_shang)
    xia = sum(1 for x in ms if x.shuang_xia)
    tou = sum(1 for x in ms if x.tou_you in MY_TEAM)
    ranks = [x.ranks for x in ms if x.ranks]
    my_rank_avg = (sum(sum(r[s] for s in MY_TEAM) / 2 for r in ranks) / len(ranks)
                   if ranks else None)
    return {
        "deals": n,
        "main_sheng_ji_per_deal": round(sum(x.sheng_ji for x in ms) / n, 2),  # ★ 主指标
        "win_rate": round(wins / n, 3),
        "tou_you_rate": round(tou / n, 3),
        "shuang_shang_rate": round(shang / n, 3),        # ★ 双上率(最强局面)
        "bei_shuang_xia_rate": round(xia / n, 3),
        "my_avg_rank": round(my_rank_avg, 2) if my_rank_avg else None,
    }


def from_store(store, game_type: str = "guandan", limit: int = 200) -> dict:
    """从本地牌局库直接算(库是唯一数据源 ✓)"""
    out = []
    for g in store.list_games(game_type=game_type, limit=limit):
        m = metric_of_deal(g["gid"], g.get("result") or {})
        if m is not None:
            out.append(m)
    return aggregate(out)
