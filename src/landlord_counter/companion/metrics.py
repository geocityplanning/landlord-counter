"""伴随应用: **策略指标**(团队口径 ✓)—— 回答"打得好不好", 不是"出得对不对"

用户 2026-09-18 定: 掼蛋是 2v2 组队游戏 ⇒ **不能用胜负判断** ✗, 必须用**队伍口径** ✓
用户 2026-09-20 定: 先建指标, 之后任何策略优化才有尺子 ✓

口径
----
· 我方 = 座位 0 与 2(对家) / 对方 = 座位 1 与 3
· **主指标(2026-09-22 用户定): 双上率 + 场均升级数(有符号)** —— 两个并列 ✓
    · 双上率   = "一波带走"的能力(前两名全是我们 ⇒ 直接升 3 级 ✓)
    · 场均升级 = 净升级收益(我方升级为正, 被对方升级为负 ✓)
  ⇒ 为什么不用胜负当主指标: ① 掼蛋是队伍游戏, 胜负太粗 ✓
    ② 实测(09-21 夜跑 8~10 局/臂) 胜负要 150~200 局才能分清 50% vs 60% ✗
       而"双上率/场均升级"灵敏得多, 同样样本就能看出趋势 ✓
· 辅指标: 胜负 / 头游率 / 被双下率 / 队友名次分布

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

# 座位名 → 座位号(GameLog.seats 顺序 ✓); 库里 deal.seat 存的是名字("南")
SEAT_INDEX = {"南": 0, "西": 1, "北": 2, "东": 3}


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
    # ---- 整场(大循环: 从打2一路到过A ✓ 2026-09-21 用户指出) ----
    ji_pai: int | None = None         # 本局打几(级牌) ✓
    match_games: int = 0              # 这一场打到第几局 ✓
    match_over: dict | None = None    # 整场结束信息(过A), 没结束为 None ✓
    match_won: bool | None = None     # 本局是否**整场获胜**(过A) ✓✓


def metric_of_deal(gid: str, result: dict, my_seat: int = 0) -> DealMetric | None:
    """把一局的结算结果 → 策略指标 ✓(结算缺失/格式不全都返回 None, 不猜 ✗)"""
    if not result:
        return None
    m = DealMetric(gid=gid)
    won = result.get("won")
    m.won = None if won is None else bool(won)
    # ★ 整场信息(2026-09-21): 级牌 / 本场局数 / 过A ✓
    m.ji_pai = result.get("jiPai")
    m.match_games = int(result.get("matchGames") or 0)
    mo = result.get("matchOver")
    if isinstance(mo, dict):
        m.match_over = mo
        m.match_won = (mo.get("winner") == "duiWu1")

    sj = result.get("shengJiShu")
    if sj is not None:
        # 我方赢 ⇒ 我方升级为正 ✓; 输 ⇒ 被对方升级, 记负 ✓
        m.sheng_ji = int(sj) * (1 if m.won else -1)

    youci = result.get("youCiList")   # 游次列表: 按出完牌顺序的座位号 ✓
    # ★ 2026-09-20 修正: **掼蛋双上/双下时立即结算** ⇒ youCiList 只有 2 个是正常的 ✓
    #   (页面 main.js: length>=2 就结束本局 —— 后两名不用再打 ✓)
    #   原来的 len(youci)==4 写死了 ✗ ⇒ 把正常局判成"不合格、不计入" ✗
    if isinstance(youci, list) and 2 <= len(youci) <= 4:
        ranks = [0] * 4
        for i, seat in enumerate(youci):
            if 0 <= int(seat) < 4:
                ranks[int(seat)] = i + 1
        # 没出现在列表里的家 ⇒ 按剩余名次补(3 / 4) ✓
        rest = [3, 4]
        for s_ in range(4):
            if ranks[s_] == 0:
                ranks[s_] = rest.pop(0) if rest else 4
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
    # ★★ 2026-09-21: 分成**两套口径**(原来一套, 导致"过A-only"的局被入口就滤掉 ✗)
    #   ① 单局口径: 只用"有结算(won/名次)"的局 ✓ —— 否则过A-only 的局会把胜率/头游率带偏 ✗
    #   ② 整场口径: 用**全量** ✓ —— "只有过A、没等到结算"的局, 恰恰是过A率的唯一来源 ✓✓
    ms_all = [x for x in metrics
              if x is not None and (x.won is not None or x.ranks or x.match_over)]
    ms = [x for x in ms_all if x.won is not None or x.ranks] or ms_all
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
    # 整场(过A)统计 ✓ —— 只统计"本场最后一局"那些(它们才带 matchOver)
    overs = [x for x in ms_all if x.match_over]
    n_over = len(overs)
    n_match_won = sum(1 for x in overs if x.match_won)
    return {
        "deals": n,
        # ★ 整场指标(掼蛋真正的"赢" ✓)
        "matches_finished": n_over,
        "matches_won": n_match_won,
        "pass_a_rate": (round(n_match_won / n_over, 3) if n_over else None),
        "games_per_match": (round(sum(x.match_games for x in overs) / n_over, 1)
                            if n_over else None),
        # ★★ 两个主指标(2026-09-22 用户定, 谁读数都先看这两个 ✓)
        "shuang_shang_rate": round(shang / n, 3),        # ★ 主指标1: 双上率
        "main_sheng_ji_per_deal": round(sum(x.sheng_ji for x in ms) / n, 2),  # ★ 主指标2: 场均升级
        "primary": ["shuang_shang_rate", "main_sheng_ji_per_deal"],   # 给前端/脚本的显式标记 ✓
        # 以下为辅指标(参考, 别拿它们下结论 ✓ 样本需求大)
        "win_rate": round(wins / n, 3),
        "tou_you_rate": round(tou / n, 3),
        "bei_shuang_xia_rate": round(xia / n, 3),
        "my_avg_rank": round(my_rank_avg, 2) if my_rank_avg else None,
    }


def from_store(store, game_type: str = "guandan", limit: int = 200) -> dict:
    """从本地牌局库直接算(库是唯一数据源 ✓)"""
    out = []
    for g in store.list_games(game_type=game_type, limit=limit):
        my_seat = SEAT_INDEX.get(str(g.get("seat") or "南"), 0)   # ★ 按实际座位算队伍 ✓
        m = metric_of_deal(g["gid"], g.get("result") or {}, my_seat)
        if m is not None:
            out.append(m)
    return aggregate(out)
