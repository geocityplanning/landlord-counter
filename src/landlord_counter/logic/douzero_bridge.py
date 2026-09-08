"""DouZero 决策桥接层 (M3): 把 ddz_engine/手牌状态翻译给 DouZero 权重, 决策回译。

设计:
  - 动作空间: 用 ddz_engine.find_all_valid_plays 的合法候选 → env 卡号列表(3-14=3..A,17=2,20=小,30=大)
  - obs: 复用 douzero.env.env.get_obs; 对手牌不可见 → other_hand_cards 用"54-我手-已出"并集近似
  - 决策: model.forward(z,x)['values'] argmax over legal(含 pass 占位); 失败/未启用 → 回退规则版
用法:
  from landlord_counter.logic.douzero_bridge import DouZeroBot
  bot = DouZeroBot('/tmp/dz_w')
  choice_tokens = bot.decide(role='landlord_down', hand=[...17 tokens...],
                             counts={'landlord':20,'landlord_down':n,'landlord_up':17},
                             played={'landlord':[...],...}, last_move=[...], can_pass=True)
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import numpy as np

from landlord_counter.logic import ddz_engine as E

TOK2ENV = {}
for _r in range(3, 11):
    TOK2ENV[str(_r)] = _r
TOK2ENV.update({"J": 11, "Q": 12, "K": 13, "A": 14, "2": 17, "小": 20, "大": 30,
                "BJ": 20, "RJ": 30})
ENV2TOK = {v: k for k, v in TOK2ENV.items() if k not in ("BJ", "RJ")}


class DouZeroBot:
    """懒加载 3 个位置模型; 决策=引擎候选 + obs前向 argmax。"""

    def __init__(self, weights_dir: str, enabled: bool = True):
        self.dir = weights_dir
        self.enabled = enabled and all(
            os.path.exists(os.path.join(weights_dir, f"{p}.ckpt"))
            for p in ("landlord", "landlord_down", "landlord_up")
        )
        self._models: dict = {}

    def available(self) -> bool:
        return self.enabled

    def _model(self, role: str):
        if role not in self._models:
            from douzero.evaluation.deep_agent import _load_model

            self._models[role] = _load_model(role, os.path.join(self.dir, f"{role}.ckpt"))
        return self._models[role]

    # ---------- 候选: 引擎合法牌 → env 卡号 ----------
    def _group_to_env(self, g: E.Group) -> list[int]:
        return sorted(TOK2ENV[E.rank_to_token(r)] for r in g.ranks)

    def _candidates(self, hand_ranks: list[int], last_group: E.Group | None) -> list[list[int]]:
        groups = E.find_all_valid_plays(hand_ranks, last_group if last_group and not last_group.is_invalid else None)
        seen = set()
        out = []
        for g in groups:
            cards = self._group_to_env(g)
            k = tuple(cards)
            if k not in seen:
                seen.add(k)
                out.append(cards)
        return out

    # ---------- obs ----------
    def _obs(self, role: str, hand_env: list[int], counts, played_by_role: dict,
             last_move_env: list[int], seq_env: list[list[int]], can_pass: bool,
             legal_env: list[list[int]]) -> dict:
        # 对手并集近似: 54张 - 我方 - 已出(按rank计数) → 无身份并集
        from collections import Counter as C

        used = C(hand_env) + C(c for lst in seq_env for c in lst)
        if last_move_env:
            used += C(last_move_env)
        rest = []
        for c in sorted(set(TOK2ENV.values())):
            maxn = 1 if c in (20, 30) else 4
            n = maxn - used.get(c, 0)
            rest += [c] * max(n, 0)

        fs = SimpleNamespace()
        fs.player_position = {"landlord": "landlord", "down": "landlord_down", "up": "landlord_up"}[role]
        fs.player_hand_cards = hand_env
        fs.num_cards_left_dict = counts  # keys landlord/landlord_up/landlord_down
        fs.three_landlord_cards = []
        fs.other_hand_cards = rest
        fs.card_play_action_seq = [list(x) for x in seq_env[-15:]]
        fs.last_move = list(last_move_env) if last_move_env else []
        fs.last_two_moves = [[], []]
        fs.last_move_dict = {"landlord": [], "landlord_up": [], "landlord_down": []}
        fs.played_cards = {"landlord": [], "landlord_up": [], "landlord_down": []}
        fs.bomb_num = 0
        fs.legal_actions = legal_env
        from douzero.env.env import get_obs

        return get_obs(fs)

    # ---------- 决策 ----------
    def decide(self, role: str, hand_tokens: list[str],
               counts: dict, played_tokens_by_role: dict,
               last_tokens: list[str] | None, can_pass: bool,
               seq_tokens: list[list[str]] | None = None) -> list[str] | None:
        """返回要出的牌 tokens; None = 不出(pass)。内部失败回退引擎最小规则。"""
        if not self.enabled:
            return None
        import torch

        role_short = {"landlord_down": "down", "landlord_up": "up"}.get(role, role)
        # 手数钳制: 地主≤20 农民≤17 (farmer obs one-hot 定长)
        counts = {
            "landlord": min(max(int(counts.get("landlord", 17)), 1), 20),
            "landlord_up": min(max(int(counts.get("landlord_up", 17)), 0), 17),
            "landlord_down": min(max(int(counts.get("landlord_down", 17)), 0), 17),
        }
        hand_ranks = sorted(E.token_to_rank(t) for t in hand_tokens)
        last_group = E.identify_str(last_tokens) if last_tokens else E.Group()
        cands = self._candidates(hand_ranks, last_group)
        if not cands:
            return None  # 压不过 → 不出(由调用方点不出)
        if can_pass:
            cands = [[]] + cands  # pass 作为候选之一
        hand_env = [TOK2ENV[t] for t in hand_tokens]
        last_env = [TOK2ENV[t] for t in (last_tokens or [])]
        seq_env = [[TOK2ENV[t] for t in lst] for lst in (seq_tokens or [])]
        obs = self._obs(role_short, hand_env, counts,
                        played_tokens_by_role or {}, last_env, seq_env, can_pass, cands)
        zb = torch.from_numpy(obs["z_batch"]).float()
        xb = torch.from_numpy(obs["x_batch"]).float()
        model_name = "landlord" if role_short == "landlord" else f"landlord_{role_short}"
        model = self._model(model_name)
        with torch.no_grad():
            vals = model.forward(zb, xb, return_value=True)["values"].detach().cpu().numpy().reshape(-1)
        best = int(np.argmax(vals))
        act = cands[best] if best < len(cands) else cands[best % len(cands)]
        if not act:
            return None
        return sorted(ENV2TOK[c] for c in act)


def seat_role(landlord_seat: str, seat: str) -> str:
    """cycle 顺序 [human, B, A]; landlord_seat ∈ human/B/A → 返回 seat 的 DouZero 角色。
    landlord 下家(=landlord_down) = cycle 中 landlord 的后一位。"""
    cyc = ["human", "B", "A"]
    li = cyc.index(landlord_seat)
    si = cyc.index(seat)
    if si == li:
        return "landlord"
    return "down" if (li + 1) % 3 == si else "up"
