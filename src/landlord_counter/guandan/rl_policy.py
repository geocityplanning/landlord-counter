"""掼蛋 RL 决策: 用开源预训练权重(MonadMorph/guandan-RL)在**我方合法候选**里做选择。

设计(与 DanKS 同思路的"学习式选择器"):
  1. 我们用自家规则引擎枚举合法候选(rules.find_all_valid_plays)
  2. 把每个候选映射到模型的 120 维动作空间的 (type, rank) 段 → 得到合法掩码
  3. 模型(Transformer, 453k 参数)对 20 个状态 token 打分 → 掩码后取 argmax
  4. 选中的候选 → 交给执行层(提示/点选)

关键: 权重是**旧版代码**训练的(history/last_hand=16 维), 现仓库已是 MLP 版对不上 →
本模块按 checkpoint 实测维度复刻结构(strict=True 加载通过), 并用作者 deck.py/policy.py
的编码规范还原 20 个状态 token。

权重: reference/guandan-rl/Bests/policy_value_net_{300,700,1000}.pt (1.8MB, CPU 约 12ms)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn

# 作者的牌值顺序(orderofRanks): 3..A, 2, 小王, 大王  → 我们的 zhi: 3..14(A), 2, 15(小王), 16(大王)
THEIR_ORDER = ["3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2",
               "Black Joker", "Red Joker"]
# 我们的 zhi → 他们的 rank 下标
ZHI_TO_THEIR = {3: 0, 4: 1, 5: 2, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7, 11: 8, 12: 9,
                13: 10, 14: 11, 2: 12, 15: 13, 16: 14}
# 我们的牌型(rules.PAI_XING 的整数值) → 他们的 type
#   1单张 2对子 3三张 4三带二 5顺子 6连对 7三连 9钢板 10炸弹 11同花顺 12天王炸 13四带二
XING_TO_TYPE = {1: 1, 2: 2, 3: 3, 4: 7, 6: 4, 5: 5, 9: 6, 11: 13}
# 他们的 type 段长度与起始下标(masking() 的顺序): {type: (offset, length)}
TYPE_SEG = {1: (0, 15), 2: (15, 15), 3: (30, 13), 4: (43, 10), 5: (53, 8),
            6: (61, 11), 11: (72, 13), 12: (85, 13), 13: (98, 8), 14: (106, 13)}
PASS_INDEX = 119
NUM_ACTIONS = 120


class GTNet(nn.Module):
    """按预训练 checkpoint 维度复刻的 Transformer 打分网络(20 tokens)。"""

    def __init__(self, d_model: int = 128, n_heads: int = 4, n_layers: int = 2,
                 num_actions: int = NUM_ACTIONS) -> None:
        super().__init__()
        dims = [16] + [16] * 16 + [5] + [16] + [4]      # hand / 16×history / cards_left / last_hand / player
        self.proj = nn.ModuleList([nn.Linear(d, d_model) for d in dims])
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads,
                                           dim_feedforward=d_model * 4,
                                           batch_first=True, activation="gelu")
        self.transformer = nn.TransformerEncoder(layer, num_layers=n_layers)
        self.norm = nn.LayerNorm(d_model)
        self.cls_token = nn.Parameter(torch.randn(1, 1, d_model))
        self.policy_head = nn.Linear(d_model, num_actions)
        self.value_head = nn.Linear(d_model, 1)

    def forward(self, tokens: list, history_length: int = 0):
        mask = torch.tensor([False] * 2 + (16 - history_length) * [True]
                            + (history_length + 3) * [False]).unsqueeze(0)
        xs = torch.cat([p(torch.as_tensor(t, dtype=torch.float32).unsqueeze(0))
                        for t, p in zip(tokens, self.proj)], dim=0).unsqueeze(0)
        xs = torch.cat([self.cls_token.expand(xs.size(0), -1, -1), xs], dim=1)
        y = self.transformer(xs, src_key_padding_mask=mask)
        h = self.norm(y[:, 0, :])
        return self.policy_head(h), self.value_head(h)


# ---------------------------------------------------------------- 状态编码
def _hand_token(hand) -> list[float]:
    """手牌 token(16): 15 个牌值计数 /8 + [同花可成组数]。"""
    cnt = [0] * 15
    suit_of_rank: dict[int, set] = {}
    for c in hand:
        i = ZHI_TO_THEIR.get(getattr(c, "zhi", None), None)
        if i is None:
            continue
        cnt[i] += 1
        hua = getattr(c, "hua", None)
        if hua is not None and hua < 4:
            suit_of_rank.setdefault(i, set()).add(hua)
    royal = sum(1 for i, s in suit_of_rank.items() if len(s) >= 4)
    return [x / 8.0 for x in cnt] + [float(royal)]


def xing_to_type(xing: int, chang_du: int) -> int | None:
    """我们的 (xing, chang_du) → 他们的 type(长度不符则 None)。"""
    if xing == 10:                      # 炸弹: 4/5/6 张
        return {4: 11, 5: 12, 6: 14}.get(chang_du)
    if xing == 5:                       # 顺子: 他们只支持 5 张
        return 5 if chang_du == 5 else None
    if xing == 6:                       # 连对: 他们只支持 3 对
        return 4 if chang_du == 3 else None
    return XING_TO_TYPE.get(xing)


def _play_token(player: int | None, group: Any) -> list[float]:
    """一次出牌 token(16): 4 玩家 one-hot + 11 牌型 one-hot(含炸弹位) + 1 rank/14。"""
    p = [0] * 4
    if player is not None and 0 <= player < 4:
        p[player] = 1
    t = [0] * 11
    r = 0.0
    if group is not None:
        xing = getattr(group, "xing", None)
        cd = getattr(group, "chang_du", 1)
        tno = xing_to_type(xing, cd) if isinstance(xing, int) else None
        if tno is not None:
            idx = tno - 1 if tno < 10 else tno - 5
            if 0 <= idx < 10:
                t[idx] = 1
            else:
                t[9] = 1
            if tno >= 10:
                t[10] = 1                     # 炸弹指示位
            zhi = getattr(group, "zhu_zhi", None)
            if zhi in ZHI_TO_THEIR:
                r = ZHI_TO_THEIR[zhi] / 14.0
    return p + t + [r]


def encode_tokens(hand, history: list, left_counts: list[int],
                  last_play, seat: int, history_length: int = 0) -> list:
    """组装 20 个 token: [手牌, 16×历史, 余牌, 上家牌, 座位]。

    history: [(player, Group|None), ...] 最近在前/后均可, 取最后 16 条
    left_counts: [我方余牌, 下家, 对家, 上家, 合计] (缺省按 108 估算)
    last_play: (player, Group|None) 或 None
    """
    hist = (history or [])[-16:]
    tokens = [_hand_token(hand)]
    pad = 16 - len(hist)
    for _ in range(pad):
        tokens.append([0.0] * 16)
    for pl, g in hist:
        tokens.append(_play_token(pl, g))
    tokens.append([x / 108.0 for x in left_counts[:5]] + [0.0] * max(0, 5 - len(left_counts)))
    lp = _play_token(*(last_play if last_play else (None, None)))
    tokens.append(lp)
    seat_onehot = [0] * 4
    seat_onehot[seat % 4] = 1
    tokens.append(seat_onehot)
    return tokens


# ---------------------------------------------------------------- 动作映射
def candidate_to_index(xing: int, chang_du: int, zhu_zhi: int) -> int | None:
    """把我们的候选((xing, chang_du, zhu_zhi))映射到模型动作下标; 映射不了返回 None。"""
    tno = xing_to_type(xing, chang_du)
    if tno is None or tno not in TYPE_SEG:
        return None
    off, length = TYPE_SEG[tno]
    ri = ZHI_TO_THEIR.get(zhu_zhi)
    if ri is None or ri >= length:
        return None
    return off + ri


def _as_group(cand: Any) -> Any:
    """候选归一成 Group: 支持 Group 本身 / 带 .group 的对象 / 牌数组。"""
    g = getattr(cand, "group", None)
    if g is not None and hasattr(g, "xing"):
        return g
    if hasattr(cand, "xing"):
        return cand
    try:
        from . import rules as R

        items = list(cand) if isinstance(cand, (list, tuple)) else [cand]
        return R.identify(items)
    except Exception:  # noqa: BLE001
        return cand


@dataclass
class RLPolicy:
    """RL 决策器: 在我们的合法候选里选一个(或不出)。"""

    weights: str = ""
    device: str = "cpu"

    def __post_init__(self) -> None:
        # 从本文件向上找仓库根(含 reference/guandan-rl 的那层)
        root = os.path.dirname(os.path.abspath(__file__))
        for _ in range(8):
            if os.path.isdir(os.path.join(root, "reference", "guandan-rl")):
                break
            root = os.path.dirname(root)
        default = os.path.join(root, "reference", "guandan-rl", "Bests", "policy_value_net_1000.pt")
        path = self.weights or os.getenv("GUANDAN_RL_WEIGHTS", default)
        path = os.path.abspath(path)
        self.net = GTNet()
        sd = torch.load(path, map_location=self.device)
        self.net.load_state_dict(sd, strict=True)
        self.net.eval()
        self.path = path
        self.calls = 0
        self.last_value = None

    def choose(self, candidates: list, hand, history: list, left_counts: list,
               last_play, seat: int) -> tuple[Any | None, dict]:
        """在候选里选; 返回 (选中的候选 或 None=不出, 调试信息)。"""
        idxs, keep = [], []
        for c in candidates:
            g = _as_group(c)
            i = candidate_to_index(getattr(g, "xing", None),
                                   getattr(g, "chang_du", 1), getattr(g, "zhu_zhi", 0))
            if i is not None:
                idxs.append(i)
                keep.append(c)
        mask = torch.zeros(1, NUM_ACTIONS, dtype=torch.bool)
        for i in idxs:
            mask[0, i] = True
        mask[0, PASS_INDEX] = True                      # 不出总是合法(可选)
        tokens = encode_tokens(hand, history, left_counts, last_play, seat,
                               history_length=min(16, len(history or [])))
        with torch.no_grad():
            logits, value = self.net(tokens, min(16, len(history or [])))
            logits = logits.masked_fill(~mask, -1e9)
            pick = int(torch.argmax(logits, dim=-1).item())
        self.calls += 1
        self.last_value = float(value)
        info = {"pick": pick, "pass": pick == PASS_INDEX, "n_cand": len(keep),
                "value": float(value), "mapped": len(idxs)}
        if pick == PASS_INDEX:
            return None, info
        for i, c in zip(idxs, keep):
            if i == pick:
                return c, info
        return None, info
