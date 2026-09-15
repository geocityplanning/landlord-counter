"""掼蛋(开源 Web 版)适配器: 把既有 percept/ai 接进平台通用接口。

过渡期说明: 复用 ../guandan 下已标定的几何常量与工具, 后续逐步下沉到 platform。
"""
from __future__ import annotations

import os
import re
import time

from ..types import Action, ExecResult, GameAdapter, Observation, SettleInfo

# 复用已标定常量(见 docs/M4_掼蛋几何参考.md)
from ...guandan import ai as AI
from ...guandan import percept as P
from ...guandan import rules as R
from ...guandan.agent import BTN_HINT, BTN_PASS, BTN_PLAY, JIPAI, WHITE_MIN, gold_button


class GuandanAdapter(GameAdapter):
    name = "guandan"
    package = None
    start_url = "http://172.18.0.1:8123/index.html"

    def __init__(self, ours: bool | None = None) -> None:
        self.ours = (os.getenv("GUANDAN_OURS", "0") == "1") if ours is None else ours
        self._last_seat = {"who": None, "blocks": {}}
        self._ex = None
        # RL 决策臂(2026-09-15): 开源预训练权重在我方合法候选里选牌 → 必须走点选直出
        self.rl = os.getenv("GUANDAN_DECIDE", "").strip().lower() == "rl"
        self._rl = None
        self._rl_hist: list = []
        self._rl_played = [0.0, 0.0, 0.0, 0.0]

    def attach(self, device, vision=None) -> None:
        super().attach(device, vision)
        self._build_executor()

    def _build_executor(self) -> None:
        from ..a11y import A11y
        from ..gestures import Executor, GestureLayout

        self.a11y = A11y(getattr(self.device, "serial", "127.0.0.1:5555"))

        def _btn(name: str, fallback):
            """无障碍树按文字取按钮中心(精确), 取不到用固定坐标。"""
            pat = {"hint": "提示", "play": "出牌", "pass": "不出"}[name]
            try:
                n = self.a11y.button(pat)
                if n:
                    return n.center
            except Exception:  # noqa: BLE001
                pass
            return fallback

        layout = GestureLayout(
            card_tap_x=P.card_tap_x,
            card_positions=P.card_positions,
            hand_y=875,
            btn_hint=BTN_HINT,
            btn_play=BTN_PLAY,
            btn_pass=BTN_PASS,
            lift_px=P.lifted_px,
            my_turn=P.my_turn,
            white_count=P.white_count,
        )
        self._ex = Executor(self.device, layout, log=print)

    # ---------- 感知 ----------
    def start_button(self, frame):
        # 优先无障碍文字按钮(再来一局/开始游戏), 失败回落金块检测
        try:
            for pat in ("再来一局", "开始游戏", "继续游戏"):
                n = self.a11y.button(pat)
                if n:
                    return n.center
        except Exception:  # noqa: BLE001
            pass
        return gold_button(frame)

    def progress_signal(self, frame):
        return P.white_count(frame)

    def _track_seat(self, frame) -> None:
        cur = P.blocks_by_seat(frame)
        changed = None
        for nm, box in cur.items():
            pb = self._last_seat["blocks"].get(nm)
            if pb is None or abs(box[0] - pb[0]) + abs(box[1] - pb[1]) > 10:
                changed = nm
        if changed:
            self._last_seat["who"] = changed
        elif not cur and self._last_seat["blocks"]:
            self._last_seat["who"] = None
        self._last_seat["blocks"] = cur

    def sense(self, frame) -> Observation:
        self._track_seat(frame)
        if not P.my_turn(frame):          # 手牌白卡 + 按钮可用(防残局误判)
            return Observation(frame=frame, my_turn=False)
        # 期望张数: 优先"块宽实测真值"(不依赖 VLM/像素分段, 实测比 hand_columns 准)
        n_vis = P.hand_card_count_est(frame) or P.hand_columns(frame)
        hand = P.read_hand_ordered(self.vision, frame, expected=n_vis)
        if not hand:
            return Observation(frame=frame, my_turn=True, hand=None, extra={"read_fail": True})
        table = P.read_table_last(self.vision, frame)
        cards = table or []
        if hand and n_vis and abs(n_vis - len(hand)) > 1:
            hand2 = P.read_hand_ordered(self.vision, frame, expected=n_vis)
            if hand2:
                hand = hand2
            if abs(n_vis - len(hand)) > 1:      # 重读后仍对不上 → 不敢用, 走提示驱动
                return Observation(frame=frame, my_turn=True, hand=None, extra={"read_fail": True})
        return Observation(frame=frame, my_turn=True, hand=hand, table=cards,
                           extra={"n_vis": n_vis})

    # ---------- 决策 ----------
    def decide(self, obs: Observation) -> Action:
        if obs.extra.get("read_fail") or not obs.hand:
            return Action("play", combo=None, meta={"hint": True, "why": "读牌失败→提示驱动"})
        cards = obs.table or []
        if cards:
            gl = R.identify(cards, JIPAI)
            if getattr(gl, "is_invalid", False):
                return Action("play", combo=None, meta={"hint": True, "why": "待压牌非法→提示驱动"})
        if not self.ours:
            return Action("play", combo=None, meta={"hint": True, "why": "MVP提示驱动"})
        st = AI.GameState()
        st.jipai = JIPAI
        st.shi_dui_you = self._last_seat.get("who") == "top"
        last = R.identify(cards, JIPAI) if cards else None
        if self.rl:
            return self._decide_rl(obs, last, cards)
        choice = AI.choose_play(obs.hand, last, st)
        if choice is None or getattr(choice, "is_invalid", False):
            return Action("pass", meta={"why": "引擎判不出"})
        return Action("play", combo=choice, meta={"why": "自研决策"})

    def _decide_rl(self, obs: Observation, last, cards: list) -> Action:
        """RL 臂: 预训练权重在"我方全部合法出牌"里选 → 标记 direct(执行层点选直出)。"""
        who = self._last_seat.get("who")
        wi = {"right": 1, "top": 2, "left": 3}.get(who or "", 1)
        if len(obs.hand) >= 25:                      # 手牌回到满手 = 新一局 → 清历史
            self._rl_hist.clear()
            self._rl_played = [0.0, 0.0, 0.0, 0.0]
        if last is not None and (not self._rl_hist or self._rl_hist[-1][1] is not last):
            self._rl_hist.append((wi, last))
            self._rl_played[wi] = min(27.0, self._rl_played[wi] + len(cards))
        if self._rl is None:
            from ...guandan.rl_policy import RLPolicy

            self._rl = RLPolicy()
            print(f"▶ RL 决策器已加载: {os.path.basename(self._rl.path)}", flush=True)
        cands = AI.zhao_ke_chu_de_pai(obs.hand, last, JIPAI)
        mine = float(len(obs.hand))
        others = [max(0.0, 27 - self._rl_played[i]) for i in (1, 2, 3)]
        choice, info = self._rl.choose(cands, obs.hand, self._rl_hist[-16:],
                                       [mine] + others + [mine + sum(others)], (wi, last), 0)
        print(f"  [rl] 手牌{len(obs.hand)} 候选{info['n_cand']}(可映射{info['mapped']}) → "
              f"{R.group_to_str(choice) if choice is not None else '不出'} | value={info['value']:.3f}",
              flush=True)
        if choice is None:
            return Action("pass", meta={"why": "RL判不出/不出"})
        self._rl_hist.append((0, choice))
        self._rl_played[0] = min(27.0, self._rl_played[0] + len(choice.cards))
        return Action("play", combo=choice, meta={"why": "RL决策", "direct": True})

    # ---------- 执行 ----------
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        if self._ex is None:
            self._build_executor()
        ex = self._ex
        assert ex is not None
        if action.kind == "pass":
            ex.pass_turn()
            return ExecResult(True, 0, "不出")
        # RL 臂: 打的是我们自己选的牌 → 必须点选直出(提示只会出游戏自己选的牌)
        if action.meta.get("direct") and action.combo is not None and obs.hand:
            idxs = _map_indices(obs.hand, action.combo.cards)
            if idxs:
                if ex.direct_play(idxs, len(obs.hand)):
                    return ExecResult(True, 0, "直选出牌(RL)")
                return ExecResult(False, 1, "直选失败(RL)")
        want = len(action.combo.cards) if action.combo is not None else None
        follow = bool(obs.table)
        r = ex.play_by_hint(want=want, follow=follow)
        if r == "ok":
            return ExecResult(True, 0, "出牌成功")
        if r == "none":
            if follow:
                ex.pass_turn()
                return ExecResult(True, 0, "提示无可出→不出")
            if obs.hand:      # 领出却提示为空 → 盲出最小单张(保流程)
                ex.dev.tap(ex.L.card_tap_x(0, len(obs.hand)), ex.L.hand_y, wait=0.4)
                ex.dev.tap(*ex.L.btn_play, wait=1.6)
                return ExecResult(True, 0, "提示空→盲出最小单张")
            return ExecResult(False, 0, "提示空且无手牌")
        # mismatch / fail → 直选我们的决策(有组合时), 否则回落失败
        if action.combo is not None and obs.hand:
            idxs = _map_indices(obs.hand, action.combo.cards)
            if idxs and ex.direct_play(idxs, len(obs.hand)):
                return ExecResult(True, 1, "直选成功")
        return ExecResult(False, 1, f"提示执行={r} 且直选未成")


def _map_indices(hand, cards):
    """把组合中的牌映射回手牌索引(用于直选)。"""
    from ...guandan.agent import map_indices

    try:
        return map_indices(hand, cards)
    except Exception:  # noqa: BLE001
        return None

    # ---------- 结算 ----------
    def settle(self, frame) -> SettleInfo | None:
        """结算解读: 优先无障碍文字(免 VLM), 否则回落 VLM 读弹窗。"""
        try:
            blob = self.a11y.text_blob(force=True)
        except Exception:  # noqa: BLE001
            blob = ""
        if "头游" in blob:
            head = ""
            m = re.search(r"头游[:：]\s*(\S+)", blob)
            if m:
                head = m.group(1)
            win = True if head in ("南", "北", "我方") else (False if head in ("西", "东") else None)
            up = ""
            m2 = re.search(r"升级[:：]?\s*([+\-]?\d+\s*级)", blob)
            if m2:
                up = m2.group(1)
            raw = f"头游={head};升级={up}"
            return SettleInfo(raw=raw, win=win)
        if self.vision is None:
            return None
        txt, win = P.read_settle(self.vision, frame)
        if "头游" not in txt and "升级" not in txt:
            return None
        return SettleInfo(raw=txt.strip()[:60], win=win)
