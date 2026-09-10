"""掼蛋规则引擎 —— 由开源项目 ``yangfanconan/guandan`` 的 ``www/js/gameRules.js`` 移植并补全。

与 JS 源一致的部分(逐条对应):
  * 牌值常量 ``PAI_ZHI`` / 花色常量 ``HUA_SE`` / 牌型常量 ``PAI_XING``(同名同值)
  * ``huo_qu_shiji_paizhi`` 级牌实际牌值(王 +100, 级牌 +50, A +30)
  * ``shi_ji_pai`` / ``shi_zhu_pai``(红桃级牌=主牌/万能牌)
  * ``chuang_jian_pai_zu``(108 张)/ ``xi_pai`` / ``fa_pai``(每人 27)
  * ``pai_xu`` / ``tong_ji_paizhi`` / ``fen_zu``
  * ``identify``(对应 ``jieXiPaiXing``)/ ``bi_jiao_pai_xing`` / ``yan_zheng_chu_pai``
  * 贡牌 ``zhao_zui_da_pai`` / 还牌 ``zhao_zui_xiao_pai`` / 升级 ``ji_suan_sheng_ji``
  * ``huo_qu_xia_yi_ji_pai`` / ``get_pai_mian`` / ``get_hua_se_fu_hao`` / ``shi_hong_se``
  * teamLogic: 位置/队友/对手/队伍/结算/贡还信息

在 JS 基础上**补全/修正**的点(详见 ``gaps`` 说明, 测试已覆盖):
  1. 主牌(红桃级牌)万能牌语义: ``identify`` 会自动尝试用主牌顶替任意点数完成牌型;
     ``Group.wild_used`` 记录当万能牌用掉的张数。JS 只定义了 ``shiZhuPai`` 未落地。
  2. 炸弹比大小: 同型炸弹(4/5/6 张)按张数优先再比点数; 同花顺同理按长度。
     JS 的 ``biJiaoPaiXing`` 对长度不同的同型炸弹返回 ``null``(互不可压), 与本项目
     AI 端的 ``zhaoKeChuDePai``(显式按 ``changDu`` 比较炸弹)矛盾, 故此处按 AI 语义修正。
  3. 天王炸对天王炸返回 0(不可互压), 修正 JS 无条件返回 1 的 bug。

API 一览(函数名即文档):
  常量       PAI_ZHI / HUA_SE / PAI_XING / PAI_XING_NAME
  牌对象     Card(zhi, hua, id)   — zhi: 2..14(A), 15 小王, 16 大王; hua: 0♠1♥2♣3♦4王
  牌型对象   Group(xing, zhu_zhi, chang_du, cards, hua, wild_used)
  级牌       she_zhi_ji_pai(zhi) / huo_qu_ji_pai() / huo_qu_shiji_paizhi(zhi, jipai=None)
             shi_ji_pai(zhi, jipai=None) / shi_zhu_pai(card, jipai=None)
  发牌       chuang_jian_pai_zu() / xi_pai(cards, rng=None) / fa_pai(rng=None)
  工具       pai_xu(cards, jipai=None) / tong_ji_paizhi(cards) / fen_zu(cards)
             parse_card(token) / cards_from_tokens(tokens) / card_to_token(card) / card_to_str(card)
  牌型       identify(cards, jipai=None) -> Group        # 识别(含主牌万能)
             bi_jiao_pai_xing(g1, g2) -> int|None         # 1/0/-1/None
             can_beat(cand, last) -> bool                 # 候选能否压过上家
             yan_zheng_chu_pai(chu, shou, shang) -> (bool, reason, Group)
             find_all_plays(hand, last=None, jipai=None) -> list[Group]
             group_to_str(group) -> str
  贡/升级    zhao_zui_da_pai / zhao_zui_xiao_pai / ji_suan_sheng_ji / huo_qu_xia_yi_ji_pai
  队伍       huo_qu_dui_you / huo_qu_dui_shou / shi_fou_dui_you / huo_qu_dui_wu
             xia_yi_ge_wei_zhi / ji_suan_jie_guo / huo_qu_gong_huan_xin_xi / huo_qu_wei_zhi_ming_cheng
  展示       get_pai_mian / get_hua_se_fu_hao / shi_hong_se

``chang_du`` 语义: 顺子/同花顺=张数; 连对=对数; 三连/钢板/飞机=连数; 炸弹=张数; 其余=1。
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# 常量(与 JS 一致)
# --------------------------------------------------------------------------- #

PAI_ZHI = {
    "ER": 2, "SAN": 3, "SI": 4, "WU": 5, "LIU": 6, "QI": 7, "BA": 8, "JIU": 9, "SHI": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14,
    "XIAO_WANG": 15, "DA_WANG": 16,
}

HUA_SE = {"HEI_TAO": 0, "HONG_TAO": 1, "MEI_HUA": 2, "FANG_KUAI": 3, "WANG": 4}

PAI_XING = {
    "WU_XIAO": 0,          # 无效牌型
    "DAN_ZHANG": 1,        # 单张
    "DUI_ZI": 2,           # 对子
    "SAN_ZHANG": 3,        # 三张
    "SAN_DAI_ER": 4,       # 三带二(三 + 对)
    "SHUN_ZI": 5,          # 顺子(>=5 张连续单张)
    "LIAN_DUI": 6,         # 连对(>=3 对连续对子)
    "SAN_LIAN": 7,         # 三连(>=3 个连续三张)
    "FEI_JI": 8,           # 飞机(三连 + 翅膀)
    "GANG_BAN": 9,         # 钢板(两个连续三张)
    "ZHA_DAN": 10,         # 炸弹(4-6 张同点)
    "TONG_HUA_SHUN": 11,   # 同花顺(>=5 张同花色顺子)
    "TIAN_WANG_ZHA": 12,   # 天王炸(4 个王)
    "SI_DAI_ER": 13,       # 四带二
}

PAI_XING_NAME = {
    0: "无效", 1: "单张", 2: "对子", 3: "三张", 4: "三带二", 5: "顺子", 6: "连对",
    7: "三连", 8: "飞机", 9: "钢板", 10: "炸弹", 11: "同花顺", 12: "天王炸", 13: "四带二",
}

# 花色符号 / 令牌映射
_HUA_LETTER = {"s": HUA_SE["HEI_TAO"], "h": HUA_SE["HONG_TAO"],
               "c": HUA_SE["MEI_HUA"], "d": HUA_SE["FANG_KUAI"]}
_HUA_UNI = {"♠": HUA_SE["HEI_TAO"], "♥": HUA_SE["HONG_TAO"],
            "♣": HUA_SE["MEI_HUA"], "♦": HUA_SE["FANG_KUAI"]}
_HUA_FU_HAO = {0: "♠", 1: "♥", 2: "♣", 3: "♦", 4: ""}
_TOKEN2ZHI = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14,
}

# 顺子/连对/三连/同花顺可用的最小与最大牌值(2 与王不参与顺/连)
_RUN_MIN, _RUN_MAX = 3, 14

# 当前级牌(默认 2), 与 JS 的 dangQianJiPai 对应
_DANG_QIAN_JI_PAI = PAI_ZHI["ER"]


def she_zhi_ji_pai(zhi: int) -> None:
    """设置当前级牌(全局, 对应 JS sheZhiJiPai)。"""
    global _DANG_QIAN_JI_PAI
    _DANG_QIAN_JI_PAI = int(zhi)


def huo_qu_ji_pai() -> int:
    """获取当前级牌。"""
    return _DANG_QIAN_JI_PAI


def _ji(jipai: int | None) -> int:
    return _DANG_QIAN_JI_PAI if jipai is None else int(jipai)


def huo_qu_shiji_paizhi(zhi: int, jipai: int | None = None) -> int:
    """实际牌值: 王最大(+100), 级牌次之(+50), A 再其次(+30), 其余原值。"""
    if zhi >= PAI_ZHI["XIAO_WANG"]:
        return zhi + 100
    jp = _ji(jipai)
    if zhi == jp:
        return zhi + 50
    if zhi == PAI_ZHI["A"]:
        return zhi + 30
    return zhi


def shi_ji_pai(zhi: int, jipai: int | None = None) -> bool:
    """是否级牌。"""
    return zhi == _ji(jipai)


def shi_zhu_pai(card: "Card", jipai: int | None = None) -> bool:
    """是否主牌(= 红桃级牌, 万能牌)。"""
    return card.zhi == _ji(jipai) and card.hua == HUA_SE["HONG_TAO"]


def shi_hong_se(hua: int) -> bool:
    """是否红色花色(♥/♦)。"""
    return hua in (HUA_SE["HONG_TAO"], HUA_SE["FANG_KUAI"])


def get_pai_mian(zhi: int) -> str:
    """牌面显示文本。"""
    if zhi == PAI_ZHI["XIAO_WANG"]:
        return "🃏"
    if zhi == PAI_ZHI["DA_WANG"]:
        return "👑"
    if PAI_ZHI["ER"] <= zhi <= PAI_ZHI["SHI"]:
        return str(zhi)
    return {PAI_ZHI["J"]: "J", PAI_ZHI["Q"]: "Q",
            PAI_ZHI["K"]: "K", PAI_ZHI["A"]: "A"}.get(zhi, "")


def get_hua_se_fu_hao(hua: int) -> str:
    """花色符号。"""
    return _HUA_FU_HAO.get(hua, "")


# --------------------------------------------------------------------------- #
# 牌对象
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Card:
    """一张牌。``zhi`` 2..14(A)/15 小王/16 大王; ``hua`` 0♠1♥2♣3♦4 王; ``id`` 唯一。

    内部识别时可能把 ``hua`` 置为 ``None`` 表示"万能牌占位"(花色待定)。
    """
    zhi: int
    hua: int | None = HUA_SE["HEI_TAO"]
    id: int = -1

    def __repr__(self) -> str:
        return card_to_str(self)


# --------------------------------------------------------------------------- #
# 牌型对象
# --------------------------------------------------------------------------- #

@dataclass
class Group:
    """牌型。``xing`` 见 PAI_XING; ``zhu_zhi`` 比较主值(已含级牌换算);
    ``chang_du`` 见模块 docstring; ``cards`` 参与牌; ``hua`` 同花顺花色(否则 -1);
    ``wild_used`` 用掉的主牌(万能)张数。"""
    xing: int = PAI_XING["WU_XIAO"]
    zhu_zhi: int = 0
    chang_du: int = 0
    cards: list = field(default_factory=list)
    hua: int = -1
    wild_used: int = 0

    @property
    def is_invalid(self) -> bool:
        return self.xing == PAI_XING["WU_XIAO"]

    @property
    def name(self) -> str:
        return PAI_XING_NAME.get(self.xing, "无效")

    def __repr__(self) -> str:
        body = " ".join(card_to_str(c) for c in self.cards)
        return f"<{self.name} {body}>"


INVALID = Group()


# --------------------------------------------------------------------------- #
# 牌面字符串 <-> 对象
# --------------------------------------------------------------------------- #

def parse_card(token: str) -> "Card":
    """把 "5h"/"5♥"/"10s"/"BJ"/"RJ" 解析为 Card(id=-1)。

    * 花色字母: s♠ h♥ c♣ d♦(大小写不敏感), 亦可直接用 ♠♥♣♦; 缺省 ♠。
    * 王: "BJ"(小王)/"RJ"(大王), 亦可 "小王"/"大王"。
    """
    t = token.strip()
    if t in ("BJ", "bj", "小王", "SW"):
        return Card(PAI_ZHI["XIAO_WANG"], HUA_SE["WANG"], -1)
    if t in ("RJ", "rj", "大王", "DW"):
        return Card(PAI_ZHI["DA_WANG"], HUA_SE["WANG"], -1)
    hua = HUA_SE["HEI_TAO"]
    if t and (t[-1] in _HUA_LETTER or t[-1] in _HUA_UNI):
        hua = _HUA_LETTER.get(t[-1]) if t[-1] in _HUA_LETTER else _HUA_UNI[t[-1]]
        t = t[:-1]
    t = t.upper()
    if t not in _TOKEN2ZHI:
        raise ValueError(f"未知牌面: {token!r}")
    return Card(_TOKEN2ZHI[t], hua, -1)


def cards_from_tokens(tokens: list) -> list:
    """批量解析 (id 依次赋值 0..n-1)。"""
    return [Card(c.zhi, c.hua, i) for i, c in enumerate(parse_card(t) for t in tokens)]


def card_to_token(card: "Card") -> str:
    """Card -> 紧凑令牌, 如 "5h"、"BJ"、"10s"。"""
    if card.zhi == PAI_ZHI["XIAO_WANG"]:
        return "BJ"
    if card.zhi == PAI_ZHI["DA_WANG"]:
        return "RJ"
    letter = {0: "s", 1: "h", 2: "c", 3: "d"}.get(card.hua if card.hua is not None else -1, "s")
    return f"{get_pai_mian(card.zhi)}{letter}"


def card_to_str(card: "Card") -> str:
    """Card -> 展示串, 如 "♥5"、"大王"。"""
    if card.zhi == PAI_ZHI["XIAO_WANG"]:
        return "小王"
    if card.zhi == PAI_ZHI["DA_WANG"]:
        return "大王"
    hua = get_hua_se_fu_hao(card.hua) if card.hua is not None else "?"
    return f"{hua}{get_pai_mian(card.zhi)}"


def cards_to_str(cards: list) -> str:
    return " ".join(card_to_str(c) for c in cards)


def group_to_str(group: "Group") -> str:
    """牌型可读描述, 如 "炸弹：♥5 ♠5 ♣5 ♦5"。"""
    if group is None or group.is_invalid:
        return "无效牌型"
    extra = " (主牌万能×%d)" % group.wild_used if group.wild_used else ""
    return f"{group.name}：{cards_to_str(group.cards)}{extra}"


# --------------------------------------------------------------------------- #
# 牌组构建 / 洗牌 / 发牌 / 排序 / 统计
# --------------------------------------------------------------------------- #

def chuang_jian_pai_zu() -> list:
    """创建两副完整牌(108 张): 2×(13 值×4 花色) + 4 王。"""
    pai_zu = []
    pid = 0
    for _ in range(2):
        for zhi in range(PAI_ZHI["ER"], PAI_ZHI["A"] + 1):
            for hua in range(HUA_SE["HEI_TAO"], HUA_SE["FANG_KUAI"] + 1):
                pai_zu.append(Card(zhi, hua, pid))
                pid += 1
    for _ in range(2):
        pai_zu.append(Card(PAI_ZHI["XIAO_WANG"], HUA_SE["WANG"], pid)); pid += 1
        pai_zu.append(Card(PAI_ZHI["DA_WANG"], HUA_SE["WANG"], pid)); pid += 1
    return pai_zu


def xi_pai(pai_zu: list, rng: random.Random | None = None) -> list:
    """洗牌(Fisher-Yates)。"""
    r = rng or random
    out = list(pai_zu)
    for i in range(len(out) - 1, 0, -1):
        j = r.randrange(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def fa_pai(rng: random.Random | None = None) -> dict:
    """发牌: 4 人每人 27 张。"""
    pai_zu = xi_pai(chuang_jian_pai_zu(), rng)
    return {
        "wan_jia_pai": pai_zu[0:27],
        "ai1_pai": pai_zu[27:54],
        "ai2_pai": pai_zu[54:81],
        "ai3_pai": pai_zu[81:108],
    }


def pai_xu(cards: list, jipai: int | None = None) -> list:
    """按实际牌值从大到小排序(同值按花色)。"""
    return sorted(cards, key=lambda c: (huo_qu_shiji_paizhi(c.zhi, jipai), c.hua), reverse=True)


def tong_ji_paizhi(cards: list) -> dict:
    """统计各牌值出现次数 {zhi: count}。"""
    tong_ji: dict = {}
    for c in cards:
        tong_ji[c.zhi] = tong_ji.get(c.zhi, 0) + 1
    return tong_ji


def fen_zu(cards: list) -> dict:
    """按出现次数分组: dan/dui/san/si/wu/liu(内按实际牌值降序)。"""
    result = {"dan": [], "dui": [], "san": [], "si": [], "wu": [], "liu": []}
    for zhi, count in tong_ji_paizhi(cards).items():
        if count == 1:
            result["dan"].append(zhi)
        elif count == 2:
            result["dui"].append(zhi)
        elif count == 3:
            result["san"].append(zhi)
        elif count == 4:
            result["si"].append(zhi)
        elif count == 5:
            result["wu"].append(zhi)
        else:
            result["liu"].append(zhi)
    for key in result:
        result[key].sort(key=lambda z: huo_qu_shiji_paizhi(z), reverse=True)
    return result


# --------------------------------------------------------------------------- #
# 牌型识别
# --------------------------------------------------------------------------- #

def _lian(zhiz: list) -> bool:
    """牌值列表是否连续(且都落在 2..A 之外的王不算, 仅 3..14 可入顺)。"""
    if not zhiz:
        return False
    for z in zhiz:
        if z < _RUN_MIN or z > _RUN_MAX:
            return False
    s = sorted(zhiz)
    return all(s[i] == s[i - 1] + 1 for i in range(1, len(s)))


def _longest_run_ranks(zhiz: list) -> list:
    """在已排序去重的牌值里找最长连续段, 返回该段牌值列表。"""
    best: list = []
    cur: list = []
    for z in sorted(set(zhiz)):
        if cur and z == cur[-1] + 1:
            cur.append(z)
        else:
            cur = [z]
        if len(cur) > len(best):
            best = list(cur)
    return best


def _uniform_hua(cards: list):
    """全部牌的花色; 若含 None(万能占位)则忽略之。冲突返回 None。"""
    huas = {c.hua for c in cards if c.hua is not None}
    if len(huas) == 1:
        return next(iter(huas))
    return None


def _identify_core(cards: list, jipai: int) -> "Group":
    """不含万能推演的牌型识别(与 JS jieXiPaiXing 对应)。"""
    n = len(cards)
    if n == 0:
        return Group()
    rc: dict = {}
    for c in cards:
        rc[c.zhi] = rc.get(c.zhi, 0) + 1
    zhiz = sorted(rc)
    counts = sorted(rc.values(), reverse=True)

    def zz() -> int:
        return max(huo_qu_shiji_paizhi(z, jipai) for z in zhiz)

    # 天王炸(4 王)
    if n == 4 and all(c.zhi >= PAI_ZHI["XIAO_WANG"] for c in cards):
        return Group(PAI_XING["TIAN_WANG_ZHA"], 100, 4, cards)

    if n == 1:
        return Group(PAI_XING["DAN_ZHANG"], zz(), 1, cards)
    if n == 2 and counts == [2]:
        return Group(PAI_XING["DUI_ZI"], zz(), 1, cards)
    if n == 3 and counts == [3]:
        return Group(PAI_XING["SAN_ZHANG"], zz(), 1, cards)
    if n == 5 and counts == [3, 2]:
        return Group(PAI_XING["SAN_DAI_ER"], zz(), 1, cards)
    # 炸弹(4-6 张相同)
    if 4 <= n <= 6 and counts == [n]:
        return Group(PAI_XING["ZHA_DAN"], zz(), n, cards)
    # 四带二(任意 4 张同点 + 2 张)
    if n == 6 and any(v == 4 for v in rc.values()):
        return Group(PAI_XING["SI_DAI_ER"], zz(), 1, cards)
    # 钢板(两个连续三张)
    if n == 6 and counts == [3, 3] and _lian(zhiz):
        return Group(PAI_XING["GANG_BAN"], zz(), 2, cards)
    # 同花顺
    if n >= 5:
        h = _uniform_hua(cards)
        if h is not None and _lian(zhiz):
            return Group(PAI_XING["TONG_HUA_SHUN"], zz(), n, cards, hua=h)
    # 顺子
    if n >= 5 and counts == [1] * n and _lian(zhiz):
        return Group(PAI_XING["SHUN_ZI"], zz(), n, cards)
    # 连对
    if n >= 6 and n % 2 == 0 and counts == [2] * (n // 2) and _lian(zhiz):
        return Group(PAI_XING["LIAN_DUI"], zz(), len(zhiz), cards)
    # 三连(>=3 个连续三张)
    if n >= 6 and n % 3 == 0 and counts == [3] * (n // 3) and _lian(zhiz):
        return Group(PAI_XING["SAN_LIAN"], zz(), len(zhiz), cards)
    # 飞机(三连 + 翅膀; 翅膀张数 = 连数 或 连数×2)
    if n >= 8:
        tri = sorted(k for k, v in rc.items() if v >= 3 and _RUN_MIN <= k <= _RUN_MAX)
        run = _longest_run_ranks(tri)
        m = len(run)
        if m >= 2:
            wings = n - 3 * m
            if wings == m or wings == 2 * m:
                return Group(PAI_XING["FEI_JI"],
                             max(huo_qu_shiji_paizhi(z, jipai) for z in run), m, cards)
    return Group()


# 解释优先级(同一次选牌可能多种解释时取"最强"者)
_TIER = {
    PAI_XING["WU_XIAO"]: 0, PAI_XING["DAN_ZHANG"]: 1, PAI_XING["DUI_ZI"]: 1,
    PAI_XING["SAN_ZHANG"]: 1, PAI_XING["SAN_DAI_ER"]: 1, PAI_XING["SI_DAI_ER"]: 1,
    PAI_XING["SHUN_ZI"]: 2, PAI_XING["LIAN_DUI"]: 2,
    PAI_XING["GANG_BAN"]: 3, PAI_XING["SAN_LIAN"]: 3, PAI_XING["FEI_JI"]: 3,
    PAI_XING["ZHA_DAN"]: 4, PAI_XING["TONG_HUA_SHUN"]: 5, PAI_XING["TIAN_WANG_ZHA"]: 6,
}


def _interp_key(g: "Group", wild_used: int) -> tuple:
    return (_TIER.get(g.xing, 0), g.chang_du, g.zhu_zhi, -wild_used)


def _wild_targets(fixed: list, jipai: int) -> list:
    """主牌可顶替的候选牌值集合(取固定牌附近点数, 保证顺/连可补缺口)。"""
    zs = set()
    for c in fixed:
        for d in range(-4, 5):
            z = c.zhi + d
            if PAI_ZHI["ER"] <= z <= PAI_ZHI["A"]:
                zs.add(z)
    if not fixed:
        zs.update(range(PAI_ZHI["ER"], PAI_ZHI["A"] + 1))
    zs.add(jipai)
    zs.add(PAI_ZHI["ER"])
    zs.add(PAI_ZHI["A"])
    return sorted(z for z in zs if PAI_ZHI["ER"] <= z <= PAI_ZHI["A"])


def identify(cards: list, jipai: int | None = None) -> "Group":
    """识别牌型(``cards`` 为 Card 列表)。返回 Group; 无法识别返回无效 Group。

    含主牌(红桃级牌)时自动推演万能顶替, 取"最强解释"(类型层级 > 长度 > 主值,
    同等时优先少用万能牌)。``Group.wild_used`` 为用掉的主牌张数。
    """
    cards = list(cards)
    if not cards:
        return Group()
    jp = _ji(jipai)
    wilds = [c for c in cards if c.zhi == jp and c.hua == HUA_SE["HONG_TAO"]]
    fixed = [c for c in cards if not (c.zhi == jp and c.hua == HUA_SE["HONG_TAO"])]

    best_g = _identify_core(cards, jp)
    best_key = _interp_key(best_g, 0)
    best_cards = best_g.cards

    if wilds:
        targets = _wild_targets(fixed, jp)
        id_map = {c.id: c for c in cards}
        for combo in itertools.product(targets, repeat=len(wilds)):
            virt = list(fixed)
            used = 0
            for w, z in zip(wilds, combo):
                virt.append(Card(z, None, w.id))
                if z != w.zhi:
                    used += 1
            g = _identify_core(virt, jp)
            if g.is_invalid:
                continue
            key = _interp_key(g, used)
            if key > best_key:
                best_key = key
                best_g = g
                best_cards = [id_map[c.id] for c in g.cards]
        best_g.cards = best_cards
        # wild_used 由最优解的 key 末位反推
        best_g.wild_used = -best_key[3]
    return best_g


# --------------------------------------------------------------------------- #
# 比较 / 校验
# --------------------------------------------------------------------------- #

def bi_jiao_pai_xing(g1: "Group", g2: "Group"):
    """比较牌型大小: 1=g1 大, -1=g2 大, 0=相等, None=不可比。"""
    if g1 is None or g2 is None or g1.is_invalid or g2.is_invalid:
        return None
    x1, x2 = g1.xing, g2.xing
    tian, tong, zha = PAI_XING["TIAN_WANG_ZHA"], PAI_XING["TONG_HUA_SHUN"], PAI_XING["ZHA_DAN"]

    if x1 == tian and x2 == tian:
        return 0                     # 修正 JS: 天王炸不互压
    if x1 == tian:
        return 1
    if x2 == tian:
        return -1

    # 同花顺 vs 炸弹: 张数多者胜(与 JS 一致; 6 张炸弹 > 5 张同花顺)
    if x1 == tong and x2 == zha:
        return 1 if g1.chang_du >= g2.chang_du else -1
    if x2 == tong and x1 == zha:
        return -1 if g2.chang_du >= g1.chang_du else 1

    # 炸弹压普通牌型
    if x1 == zha and x2 not in (zha, tong):
        return 1
    if x2 == zha and x1 not in (zha, tong):
        return -1
    # 同花顺压普通牌型
    if x1 == tong and x2 != tong:
        return 1
    if x2 == tong and x1 != tong:
        return -1

    # 同类型
    if x1 == x2:
        if x1 in (zha, tong):        # 炸弹/同花顺: 先比张数
            if g1.chang_du != g2.chang_du:
                return 1 if g1.chang_du > g2.chang_du else -1
            return (g1.zhu_zhi > g2.zhu_zhi) - (g1.zhu_zhi < g2.zhu_zhi)
        if g1.chang_du == g2.chang_du:
            return (g1.zhu_zhi > g2.zhu_zhi) - (g1.zhu_zhi < g2.zhu_zhi)
        return None                  # 顺/连类长度不同不可比
    return None


def can_beat(cand: "Group", last: "Group | None") -> bool:
    """``cand`` 能否压过 ``last``(``last`` 无效/None 表示自由出牌, 只要 cand 合法)。"""
    if cand is None or cand.is_invalid:
        return False
    if last is None or last.is_invalid:
        return True
    r = bi_jiao_pai_xing(cand, last)
    return r is not None and r > 0


def yan_zheng_chu_pai(chu_pai: list, shou_pai: list, shang_jia: "Group | None",
                      jipai: int | None = None):
    """出牌合法性校验。返回 ``(valid, reason, group)``。

    与 JS ``yanZhengChuPai`` 对应: 校验拥有牌、牌型有效、能压过上家。
    """
    if not chu_pai:
        return False, "请选择要出的牌", Group()
    shou_ids = {c.id for c in shou_pai}
    for c in chu_pai:
        if c.id not in shou_ids:
            return False, "你没有这些牌", Group()
    g = identify(chu_pai, jipai)
    if g.is_invalid:
        return False, "无效的牌型组合", g
    if shang_jia is None or shang_jia.is_invalid:
        return True, "", g
    r = bi_jiao_pai_xing(g, shang_jia)
    if r is None:
        return False, "牌型不匹配，无法压过", g
    if r > 0:
        return True, "", g
    return False, "牌太小，压不过", g


# --------------------------------------------------------------------------- #
# 候选生成(压牌/自由出牌)
# --------------------------------------------------------------------------- #

def _pick(by_zhi: dict, wilds: list, zhi: int, k: int, used: set):
    """从点数 ``zhi`` 取 ``k`` 张; 不足用手牌主牌顶替。用于 by_zhi 与原手牌。"""
    out = []
    for c in by_zhi.get(zhi, ()):
        if c.id not in used:
            used.add(c.id)
            out.append(c)
            if len(out) == k:
                return out
    for w in wilds:
        if w.id not in used:
            used.add(w.id)
            out.append(w)
            if len(out) == k:
                return out
    for c in out:
        used.discard(c.id)
    return None


def _pick_any(hand: list, used: set, k: int):
    out = []
    for c in hand:
        if c.id not in used:
            used.add(c.id)
            out.append(c)
            if len(out) == k:
                return out
    for c in out:
        used.discard(c.id)
    return None


def _pick_pair_any(by_zhi: dict, wilds: list, used: set):
    for z in list(by_zhi):
        got = _pick(by_zhi, wilds, z, 2, used)
        if got:
            return got
    return None


def _gen_runs(by_zhi: dict, wilds: list, per: int, min_len: int) -> list:
    """生成连续牌型: per=1 顺子, per=2 连对, per=3 三连(含钢板)。"""
    res = []
    for L in range(min_len, 13):
        for s in range(_RUN_MIN, _RUN_MAX - L + 2):
            used: set = set()
            cards: list = []
            ok = True
            for r in range(s, s + L):
                got = _pick(by_zhi, wilds, r, per, used)
                if not got:
                    ok = False
                    break
                cards += got
            if ok:
                res.append(cards)
    return res


def _gen_tong_hua_shun(hand: list, wilds: list) -> list:
    """生成同花顺(同花色连续 >=5 张, 主牌可补)。"""
    res = []
    for hua in range(4):
        for L in range(5, 13):
            for s in range(_RUN_MIN, _RUN_MAX - L + 2):
                used: set = set()
                cards: list = []
                ok = True
                for r in range(s, s + L):
                    c = next((x for x in hand
                              if x.hua == hua and x.zhi == r and x.id not in used), None)
                    if c is not None:
                        cards.append(c)
                        used.add(c.id)
                        continue
                    w = next((x for x in wilds if x.id not in used), None)
                    if w is not None:
                        cards.append(w)
                        used.add(w.id)
                    else:
                        ok = False
                        break
                if ok:
                    res.append(cards)
    return res


def _gen_fei_ji(hand: list, by_zhi: dict, wilds: list) -> list:
    """生成飞机(>=2 连三张 + 单翼或对翼)。"""
    res = []
    for m in range(2, 6):
        for s in range(_RUN_MIN, _RUN_MAX - m + 2):
            used: set = set()
            trips: list = []
            ok = True
            for r in range(s, s + m):
                got = _pick(by_zhi, wilds, r, 3, used)
                if not got:
                    ok = False
                    break
                trips += got
            if not ok:
                continue
            # 单翼(m 张)
            one = _pick_any(hand, set(used), m)
            if one:
                res.append(trips + one)
            # 对翼(m 对)
            u2 = set(used)
            pairs: list = []
            ok2 = True
            for _ in range(m):
                got = _pick_pair_any(by_zhi, wilds, u2)
                if not got:
                    ok2 = False
                    break
                pairs += got
            if ok2:
                res.append(trips + pairs)
    return res


def _gen_all(hand: list, jipai: int) -> list:
    """从手牌生成所有"候选牌组"(未去重, 已是实际 Card 组合)。"""
    by_zhi: dict = {}
    for c in hand:
        by_zhi.setdefault(c.zhi, []).append(c)
    wilds = [c for c in hand if c.zhi == jipai and c.hua == HUA_SE["HONG_TAO"]]
    out: list = []

    # 单张(每个点数一张) / 对 / 三 / 炸弹
    for z in list(by_zhi):
        out.append([by_zhi[z][0]])
        for k in (2, 3, 4, 5, 6):
            got = _pick(by_zhi, wilds, z, k, set())
            if got:
                out.append(got)

    # 三带二
    for t in list(by_zhi):
        tri = _pick(by_zhi, wilds, t, 3, set())
        if not tri:
            continue
        base = {c.id for c in tri}
        for p in list(by_zhi):
            if p == t:
                continue
            pr = _pick(by_zhi, wilds, p, 2, set(base))
            if pr:
                out.append(tri + pr)

    # 四带二
    for t in list(by_zhi):
        quad = _pick(by_zhi, wilds, t, 4, set())
        if not quad:
            continue
        two = _pick_any(hand, {c.id for c in quad}, 2)
        if two:
            out.append(quad + two)

    out += _gen_runs(by_zhi, wilds, 1, 5)     # 顺子
    out += _gen_runs(by_zhi, wilds, 2, 3)     # 连对
    out += _gen_runs(by_zhi, wilds, 3, 2)     # 三连/钢板
    out += _gen_tong_hua_shun(hand, wilds)    # 同花顺
    out += _gen_fei_ji(hand, by_zhi, wilds)   # 飞机

    # 天王炸
    xw = sum(1 for c in hand if c.zhi == PAI_ZHI["XIAO_WANG"])
    dw = sum(1 for c in hand if c.zhi == PAI_ZHI["DA_WANG"])
    if xw >= 2 and dw >= 2:
        tw = ([c for c in hand if c.zhi == PAI_ZHI["XIAO_WANG"]][:2] +
              [c for c in hand if c.zhi == PAI_ZHI["DA_WANG"]][:2])
        out.append(tw)
    return out


def find_all_plays(hand: list, last: "Group | None" = None, jipai: int | None = None) -> list:
    """找出 ``hand`` 中所有能压过 ``last`` 的合法出牌(``last`` 为空则列出所有牌型)。

    返回去重后的 Group 列表, 已按 (类型, 长度, 主值) 排序。每个返回项均满足
    ``can_beat`` 为真且 ``identify(g.cards)`` 与之一致。
    """
    hand = list(hand)
    if not hand:
        return []
    jp = _ji(jipai)
    res: list = []
    seen: set = set()
    for cs in _gen_all(hand, jp):
        if not cs:
            continue
        g = identify(cs, jp)
        if g.is_invalid:
            continue
        if not can_beat(g, last):
            continue
        key = (g.xing, g.zhu_zhi, g.chang_du,
               tuple(sorted(c.id for c in g.cards)))
        if key in seen:
            continue
        seen.add(key)
        res.append(g)
    res.sort(key=lambda g: (g.xing, g.chang_du, g.zhu_zhi))
    return res


# --------------------------------------------------------------------------- #
# 贡牌 / 还牌 / 升级
# --------------------------------------------------------------------------- #

def zhao_zui_da_pai(shou_pai: list, jipai: int | None = None):
    """找出最大的牌(贡牌)。"""
    if not shou_pai:
        return None
    return pai_xu(shou_pai, jipai)[0]


def zhao_zui_xiao_pai(shou_pai: list, exclude_id: int = -1, jipai: int | None = None):
    """找出最小的牌(还牌), 排除 ``exclude_id``(通常为刚收到的贡牌)。"""
    if not shou_pai:
        return None
    px = pai_xu(shou_pai, jipai)
    for i in range(len(px) - 1, -1, -1):
        if px[i].id != exclude_id:
            return px[i]
    return px[-1]


def ji_suan_sheng_ji(you_ci: int, dui_you_you_ci: int) -> int:
    """升级计算: ``you_ci`` 己方游次(1 头游..4 末游), ``dui_you_you_ci`` 队友游次。"""
    if you_ci >= 3 and dui_you_you_ci >= 3:
        return 3          # 双下
    if you_ci <= 2 and dui_you_you_ci <= 2:
        return 3          # 双上
    if you_ci == 4 or dui_you_you_ci == 4:
        return 2          # 单下
    return 1


def huo_qu_xia_yi_ji_pai(dang_qian: int) -> int:
    """下一级牌(逢 A 必打, 停在 A)。"""
    if dang_qian >= PAI_ZHI["A"]:
        return PAI_ZHI["A"]
    return dang_qian + 1


# --------------------------------------------------------------------------- #
# 队伍 / 位置(teamLogic.js)
# --------------------------------------------------------------------------- #

WEI_ZHI = {"NAN": 0, "XI": 1, "BEI": 2, "DONG": 3}
WEI_ZHI_NAME = ["南", "西", "北", "东"]


def huo_qu_dui_you(wei_zhi: int) -> int:
    """队友位置(对家)。"""
    return (wei_zhi + 2) % 4


def huo_qu_dui_shou(wei_zhi: int) -> list:
    """对手位置。"""
    return [(wei_zhi + 1) % 4, (wei_zhi + 3) % 4]


def shi_fou_dui_you(wei_zhi1: int, wei_zhi2: int) -> bool:
    return huo_qu_dui_you(wei_zhi1) == wei_zhi2


def shi_fou_wan_jia(wei_zhi: int) -> bool:
    return wei_zhi == WEI_ZHI["NAN"]


def huo_qu_dui_wu() -> dict:
    """{'dui_wu1': [南, 北], 'dui_wu2': [西, 东]}"""
    return {"dui_wu1": [WEI_ZHI["NAN"], WEI_ZHI["BEI"]],
            "dui_wu2": [WEI_ZHI["XI"], WEI_ZHI["DONG"]]}


def xia_yi_ge_wei_zhi(dang_qian: int) -> int:
    return (dang_qian + 1) % 4


def huo_qu_wei_zhi_ming_cheng(wei_zhi: int) -> str:
    return WEI_ZHI_NAME[wei_zhi] if 0 <= wei_zhi < 4 else "未知"


def ji_suan_jie_guo(you_ci_list: list, dang_qian_ji: int, zha_dan_shu: int = 0) -> dict:
    """结算: ``you_ci_list`` 为按名次排列的位置列表 [头游, 二游, 三游, 末游]。"""
    dui_wu = huo_qu_dui_wu()
    d1min, d1max = 4, 1
    d2min, d2max = 4, 1
    for i, wei_zhi in enumerate(you_ci_list):
        you_ci = i + 1
        if wei_zhi in dui_wu["dui_wu1"]:
            d1min, d1max = min(d1min, you_ci), max(d1max, you_ci)
        else:
            d2min, d2max = min(d2min, you_ci), max(d2max, you_ci)

    d1_sheng = d1min < d2min
    sheng_fang = "dui_wu1" if d1_sheng else "dui_wu2"
    sheng_min = d1min if d1_sheng else d2min
    sheng_max = d1max if d1_sheng else d2max

    sheng_ji_shu = 1
    if sheng_max in (3, 4):
        bai_min = d2min if d1_sheng else d1min
        bai_max = d2max if d1_sheng else d1max
        if bai_min == 3 and bai_max == 4:
            sheng_ji_shu = 3        # 双下
        elif bai_min == 4:
            sheng_ji_shu = 2        # 单下
    if sheng_min == 1 and sheng_max == 2:
        sheng_ji_shu = 3            # 双上

    return {
        "sheng_fang": sheng_fang,
        "sheng_ji_shu": sheng_ji_shu,
        "xin_ji_pai": min(dang_qian_ji + sheng_ji_shu, 14),
        "zha_dan_shu": zha_dan_shu,
        "tou_you": you_ci_list[0],
        "mo_you": you_ci_list[3],
        "dui_wu1_huo_sheng": d1_sheng,
        "you_ci_list": list(you_ci_list),
    }


def huo_qu_gong_huan_xin_xi(mo_you_wei_zhi: int, tou_you_wei_zhi: int) -> dict:
    """贡还信息: 末游向头游贡牌; 若同队则不贡。"""
    if shi_fou_dui_you(mo_you_wei_zhi, tou_you_wei_zhi):
        return {"xu_yao_gong_pai": False}
    return {"xu_yao_gong_pai": True,
            "gong_pai_zhe": mo_you_wei_zhi,
            "shou_pai_zhe": tou_you_wei_zhi}
