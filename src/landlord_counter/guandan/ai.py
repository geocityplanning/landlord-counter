"""掼蛋 AI 决策 —— 由开源项目 ``yangfanconan/guandan`` 的 ``www/js/aiLogic.js`` 移植,
并整合 ``teamLogic.js`` 的队友/位置配合思路。

移植对应关系:
  * ``fen_xi_shou_pai``   ← fenXiShouPai(手牌组合分析, 按牌型归类)
  * ``zhao_ke_chu_de_pai``← zhaoKeChuDePai(找出能压过上家的所有牌)
  * ``choose_play``       ← xuanZeChuPai / shouCiChuPai / jianDanCeLue / zhongDengCeLue
                            (困难策略在 JS 里等同中等策略, 此处保持一致)
  * ``xuan_ze_gong_pai``  ← xuanZeGongPai(贡最大的牌)
  * ``xuan_ze_huan_pai``  ← xuanZeHuanPai(还最小的牌)

API:
  NAN_DU: {JIAN_DAN:1, ZHONG_DENG:2, KUN_NAN:3}
  GameState(shi_dui_you=False, nan_du=NAN_DU['ZHONG_DENG'], rng=None, jipai=None)
  choose_play(hand, last_play=None, state=None) -> Group | None   # None = 不出
  zhao_ke_chu_de_pai(hand, last_play=None, jipai=None) -> list[Group]
  fen_xi_shou_pai(hand, jipai=None) -> dict[str, list[Group]]
  xuan_ze_gong_pai(hand, jipai=None) -> Card | None
  xuan_ze_huan_pai(hand, exclude_id=-1, jipai=None) -> Card | None
  she_zhi_nan_du(zhi) / huo_qu_nan_du()

设计说明(与 JS 的差异):
  * JS 的 ``Math.random`` 让牌用参数 ``state.rng`` 注入, 默认全局 ``random``;
    测试可传入 ``random.Random(seed)`` 得到确定性结果。
  * JS 首出会优先甩同花顺/顺子等大牌; 此处保留该优先级但用"同类型取最小主值"
    代替 JS 的数组下标(数组顺序在 Python 侧无意义)。
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from . import rules as R

NAN_DU = {"JIAN_DAN": 1, "ZHONG_DENG": 2, "KUN_NAN": 3}

_DANG_QIAN_NAN_DU = NAN_DU["ZHONG_DENG"]

# 可作"备选普通牌型"的类型(非炸弹/非同花顺)
_BOMB_LIKE = (R.PAI_XING["ZHA_DAN"], R.PAI_XING["TIAN_WANG_ZHA"], R.PAI_XING["TONG_HUA_SHUN"])


def she_zhi_nan_du(nan_du: int) -> None:
    """设置全局默认难度(对应 JS sheZhiNanDu)。"""
    global _DANG_QIAN_NAN_DU
    _DANG_QIAN_NAN_DU = int(nan_du)


def huo_qu_nan_du() -> int:
    return _DANG_QIAN_NAN_DU


@dataclass
class GameState:
    """AI 决策上下文。"""
    shi_dui_you: bool = False          # 上家(当前出牌者)是否队友
    nan_du: int | None = None          # 难度, None 用全局默认
    rng: "random.Random | None" = None  # 随机源(random.Random), None 用全局 random
    jipai: int | None = None           # 本局级牌, None 用 rules 全局

    def get_nan_du(self) -> int:
        return _DANG_QIAN_NAN_DU if self.nan_du is None else int(self.nan_du)

    def get_rng(self):
        return self.rng if self.rng is not None else random


# --------------------------------------------------------------------------- #
# 手牌分析 / 管牌
# --------------------------------------------------------------------------- #

def fen_xi_shou_pai(hand: list, jipai: int | None = None) -> dict:
    """手牌组合分析: 返回 {牌型名: [Group, ...]}(等价 JS fenXiShouPai)。"""
    out: dict = {}
    for g in R.find_all_plays(hand, None, jipai):
        out.setdefault(g.name, []).append(g)
    return out


def zhao_ke_chu_de_pai(hand: list, last_play: "R.Group | None" = None,
                       jipai: int | None = None) -> list:
    """找出能压过 ``last_play`` 的所有出牌(对应 JS zhaoKeChuDePai)。"""
    return R.find_all_plays(hand, last_play, jipai)


# --------------------------------------------------------------------------- #
# 出牌策略
# --------------------------------------------------------------------------- #

def _pai_dai_jia(g) -> tuple:
    """候选"代价"键(越小越优先): (王张数, 万能消耗) — 避免早早拆王/动主牌。"""
    wang = sum(1 for c in g.cards if getattr(c, "zhi", 0) >= 15)
    return (wang, getattr(g, "wild_used", 0))


def _ke_yi_bo_wang(hand: list, cands: list):
    """存在"一手走完"的候选 → 直接返回它(不管张数类型)。"""
    n = len(hand)
    for g in cands:
        if len(g.cards) >= n:
            return g
    return None


def _jian_dan_ce_lue(cands: list) -> "R.Group":
    """简单策略: 挑主值最小者, 尽量避免天王炸。"""
    norm = [g for g in cands if g.xing != R.PAI_XING["TIAN_WANG_ZHA"]] or cands
    return sorted(norm, key=lambda g: (_pai_dai_jia(g), g.zhu_zhi, g.chang_du))[0]


def _zhong_deng_ce_lue(cands: list, hand: list):
    """中等策略: 牌少全压; 否则优先普通牌型, 尽量不动炸弹; 只剩炸弹时视手牌决定。"""
    if len(hand) <= 5:
        return max(cands, key=lambda g: (g.zhu_zhi, g.chang_du))
    pu_tong = [g for g in cands if g.xing not in _BOMB_LIKE]
    if pu_tong:
        return _jian_dan_ce_lue(pu_tong)
    if len(hand) <= 8:
        return cands[0]
    return None


def _shou_ci_chu_pai(hand: list, jipai: int | None = None) -> "R.Group":
    """首出策略(对应 JS shouCiChuPai): 优先成型的顺/连, 最后出单张。"""
    cands = R.find_all_plays(hand, None, jipai)
    if not cands:
        # 兜底: 出一张最小的牌
        return R.identify([R.pai_xu(hand, jipai)[-1]], jipai)

    # 一手走完(残局) → 直接出
    fin = _ke_yi_bo_wang(hand, cands)
    if fin is not None:
        return fin

    def smallest(xing_list):
        return sorted(xing_list, key=lambda g: (_pai_dai_jia(g), g.zhu_zhi, g.chang_du))[0]

    priority = [
        R.PAI_XING["TONG_HUA_SHUN"],
        R.PAI_XING["SHUN_ZI"],
        R.PAI_XING["LIAN_DUI"],
        R.PAI_XING["GANG_BAN"],
        R.PAI_XING["SAN_LIAN"],
        R.PAI_XING["FEI_JI"],
        R.PAI_XING["SAN_DAI_ER"],
        R.PAI_XING["SAN_ZHANG"],
        R.PAI_XING["DUI_ZI"],
        R.PAI_XING["DAN_ZHANG"],
        R.PAI_XING["SI_DAI_ER"],
        R.PAI_XING["ZHA_DAN"],
    ]
    for xing in priority:
        bucket = [g for g in cands if g.xing == xing]
        if bucket:
            return smallest(bucket)
    return cands[0]


def choose_play(hand: list, last_play: "R.Group | None" = None,
                state: "GameState | None" = None):
    """AI 选择出牌(对应 JS xuanZeChuPai)。

    返回压过上家的 ``Group``; 返回 ``None`` 表示不出(过牌)。
    上家是队友且队友牌型有效时, 中/高难度下有 70% 概率直接让牌。
    """
    st = state or GameState()
    jipai = st.jipai
    jp = R.huo_qu_ji_pai() if jipai is None else jipai

    # 首出
    if last_play is None or last_play.is_invalid:
        return _shou_ci_chu_pai(hand, jp)

    cands = R.find_all_plays(hand, last_play, jp)
    if not cands:
        return None

    # 残局: 能一手走完 → 出(不分队友/难度)
    fin = _ke_yi_bo_wang(hand, cands)
    if fin is not None:
        return fin

    # 队友出牌: 确定性让牌 — 队友牌型有效且我们不是"必须走"时让队友领出
    # (旧版是 70% 随机; 现在: 手里还有牌(>3)就让, 除非上面已判定能走完)
    if st.shi_dui_you and not last_play.is_invalid and len(hand) > 3:
        return None

    if st.get_nan_du() == NAN_DU["JIAN_DAN"]:
        return _jian_dan_ce_lue(cands)
    return _zhong_deng_ce_lue(cands, hand)     # 困难 = 中等(与 JS 一致)


def xuan_ze_gong_pai(hand: list, jipai: int | None = None):
    """AI 选择贡牌(最大牌)。"""
    return R.zhao_zui_da_pai(hand, jipai)


def xuan_ze_huan_pai(hand: list, exclude_id: int = -1, jipai: int | None = None):
    """AI 选择还牌(最小牌)。"""
    return R.zhao_zui_xiao_pai(hand, exclude_id, jipai)
