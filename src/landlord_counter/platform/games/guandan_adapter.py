"""掼蛋(开源 Web 版)适配器: 把既有 percept/ai 接进平台通用接口。

过渡期说明: 复用 ../guandan 下已标定的几何常量与工具, 后续逐步下沉到 platform。
"""
from __future__ import annotations

import os
import time

from ..types import Action, ExecResult, GameAdapter, Observation

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

    # ---------- 感知 ----------
    def start_button(self, frame):
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
        n_vis = P.hand_columns(frame)
        hand = P.read_hand_ordered(self.vision, frame, expected=n_vis)
        if not hand:
            return Observation(frame=frame, my_turn=True, hand=None, extra={"read_fail": True})
        table = P.read_table_last(self.vision, frame)
        cards = table or []
        if hand and n_vis and abs(n_vis - len(hand)) > 1:
            hand2 = P.read_hand_ordered(self.vision, frame, expected=n_vis)
            if hand2:
                hand = hand2
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
        choice = AI.choose_play(obs.hand, last, st)
        if choice is None or getattr(choice, "is_invalid", False):
            return Action("pass", meta={"why": "引擎判不出"})
        return Action("play", combo=choice, meta={"why": "自研决策"})

    # ---------- 执行 ----------
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        dev = self.device
        frame = obs.frame
        if action.kind == "pass":
            self.device.tap(*BTN_PASS, wait=1.4)
            return ExecResult(True, 0, "不出")
        # 出牌: 提示选牌 → 张数校验 → 出牌 → 回执; 失败重试一轮
        w_before = P.white_count(frame)
        for attempt in range(2):
            dev.tap(*BTN_HINT, wait=1.6)
            iv = dev.snap()
            if iv is None:
                continue
            lift = P.lifted_px(iv)
            est = round(lift / 1460) if lift > 500 else 0
            if est == 0:
                if obs.table:                     # 跟牌: 提示都没有 → 真不出
                    dev.tap(*BTN_PASS, wait=1.6)
                    return ExecResult(True, attempt, "提示无可出→不出")
                if obs.hand:                      # 领出却提示为空 → 盲出最小单张(保流程)
                    dev.tap(P.card_tap_x(0, len(obs.hand)), 875, wait=0.4)
                    dev.tap(*BTN_PLAY, wait=1.6)
                    return ExecResult(True, attempt, "提示空→盲出最小单张")
                return ExecResult(False, attempt, "提示空且无手牌")
            if action.combo is not None:
                want = len(action.combo.cards)
                if abs(est - want) > max(1, want // 2):
                    for _ in range(2):
                        dev.tap(*BTN_PASS, wait=1.2)   # 清掉提示选中的牌
                    continue
            dev.tap(*BTN_PLAY, wait=1.6)
            for _ in range(8):
                time.sleep(0.4)
                i2 = dev.snap()
                if i2 is None:
                    continue
                if not P.my_turn(i2) or P.white_count(i2) < w_before - 1500:
                    return ExecResult(True, attempt, "出牌成功")
            dev.tap(*BTN_PLAY, wait=1.6)
            for _ in range(6):
                time.sleep(0.4)
                i2 = dev.snap()
                if i2 is None:
                    continue
                if not P.my_turn(i2) or P.white_count(i2) < w_before - 1500:
                    return ExecResult(True, attempt, "补点后成功")
        return ExecResult(False, 2, "两轮均未生效")
