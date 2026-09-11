"""斗地主(wishday)适配器: 复用 tools/auto_play 的感知/几何 + 通用手势层执行。

决策: 规则引擎(logic/bot)。DouZero 决策待接(bridge 已有, 见 TODO)。
"""
from __future__ import annotations

import os

import numpy as np

from ..types import Action, ExecResult, GameAdapter, Observation, SettleInfo


def _ddz_white(img) -> int:
    """斗地主手牌带白卡像素(手牌行附近, y[500,700])。"""
    band = img[500:700, :]
    b, g, r = band[:, :, 0].astype(int), band[:, :, 1].astype(int), band[:, :, 2].astype(int)
    return int(((b > 200) & (g > 200) & (r > 200)).sum())


class DoudizhuAdapter(GameAdapter):
    name = "doudizhu"
    package = "com.doudizhu.game"
    start_url = None

    def __init__(self, use_douzero: bool | None = None) -> None:
        self.use_douzero = (os.getenv("DOUZERO", "0") == "1") if use_douzero is None else use_douzero
        self.ap = None
        self._ex = None
        self._dz = None

    # ---------- 装配 ----------
    def attach(self, device, vision=None) -> None:
        super().attach(device, vision)
        from ...tools import auto_play as AP
        from ..gestures import Executor, GestureLayout

        self.AP = AP
        self.ap = AP.AutoPlay(vision)
        layout = GestureLayout(
            card_tap_x=self._tap_x,
            hand_y=AP.HAND_Y,
            lift_px=AP.lifted_count,
            my_turn=lambda img: AP.my_turn(self.ap, img),
            white_count=_ddz_white,
            btn_resolver=self._buttons,
            lift_diff=AP.lifted_delta,   # 帧差度量(已验证更稳)
            lift_eps=60.0,
            lift_one=1.0,
            lift_min=0.5,
        )
        self._ex = Executor(device, layout, log=print)

    def _tap_x(self, i: int, n: int) -> int:
        AP = self.AP
        sp = min(max((AP.HAND_AVAIL - AP.CARD_W) / max(n - 1, 1), AP.CARD_W * 0.35), AP.CARD_W * 0.90)
        start_x = (1280.0 - (sp * (n - 1) + AP.CARD_W)) / 2
        return int(start_x + i * sp + sp * 0.4)

    def _buttons(self, img) -> dict:
        """动态按钮: grey=不出, green=出牌, blue=提示/叫分。统一取 (x,y)。"""
        AP = self.AP
        row = self.ap.button_row(img)
        blue = AP.mask_blobs(img, AP.BLUE, 25, 120, 300, 150, 60)

        def xy(b):
            return (b[0], b[1]) if b else None

        return {
            "pass": xy(row.get("grey")),
            "play": xy(row.get("green")),
            "hint": xy(blue[-1]) if blue else None,
        }

    # ---------- 感知 ----------
    def start_button(self, frame):
        return self.ap.result_screen(frame)      # 结算屏的"再来一局"绿大钮

    def progress_signal(self, frame):
        return _ddz_white(frame)

    def sense(self, frame) -> Observation:
        AP = self.AP
        # 叫分轮: 无出牌绿钮 + 有"3分"红钮(铁证)
        reds = self.ap._color_blocks(frame, [(0xD3, 0x2F, 0x2F)], 35, min_w=220, min_h=100)
        row0 = self.ap.button_row(frame)
        if not row0.get("green") and reds:
            hand_b = AP.read_hand_sane(self.vision, frame)
            return Observation(frame=frame, my_turn=True, hand=hand_b, extra={"phase": "bid"})
        # 出牌轮: 稳定双帧(绿钮两帧一致)才认
        ok_stable = False
        try:
            ok_stable = AP.my_turn_stable(self.ap)[0]
        except Exception:  # noqa: BLE001
            ok_stable = AP.my_turn(self.ap, frame)
        if not ok_stable:
            return Observation(frame=frame, my_turn=False)
        hand = AP.read_hand_sane(self.vision, frame)
        table = []
        zone = self.ap.last_played_zone(frame)
        if zone:
            table = self.ap.read_zone_cards(frame, zone) or []
        return Observation(frame=frame, my_turn=True, hand=hand, table=table,
                           buttons={k: v for k, v in self._buttons(frame).items() if v},
                           extra={"phase": "play"})

    # ---------- 决策 ----------
    def decide(self, obs: Observation) -> Action:
        from ...logic import bot

        hand = obs.hand or []
        if not hand:
            return Action("none", meta={"why": "未读到手牌"})
        if obs.extra.get("phase") == "bid":
            score = bot.decide_bid(hand)
            return Action("bid", meta={"score": score})
        table = obs.table or []
        if table:
            from ...logic import ddz_engine as E

            last = E.identify(table)
            choice = bot.pick_follow(hand, last)
        else:
            choice = bot.pick_lead(hand)
        if choice is None:
            return Action("pass", meta={"why": "规则判不出"})
        return Action("play", combo=choice, meta={"why": "规则决策"})

    # ---------- 执行 ----------
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        if self._ex is None:
            self.attach(self.device, self.vision)
        ex = self._ex
        assert ex is not None
        if action.kind == "bid":
            return self._do_bid(action, obs)
        if action.kind == "pass":
            ok = ex.pass_turn(obs.frame)
            return ExecResult(ok, 0, "不出")
        hand = obs.hand or []
        idxs = self._map(action, hand)
        if not idxs:
            r = ex.play_by_hint(follow=bool(obs.table))
            return ExecResult(r == "ok", 0, f"提示执行={r}")
        if ex.direct_play(idxs, len(hand)):
            return ExecResult(True, 0, "直选成功")
        r = ex.play_by_hint(follow=bool(obs.table))
        return ExecResult(r == "ok", 1, f"直选失败→提示={r}")

    def _do_bid(self, action: Action, obs: Observation) -> ExecResult:
        """叫分: score>0 → 红钮(最右); 否则灰钮(不叫)。"""
        img = obs.frame
        target = None
        if action.meta.get("score", 0) > 0:
            reds = self.ap._color_blocks(img, [(0xD3, 0x2F, 0x2F)], 35, min_w=220, min_h=100)
            if reds:
                target = (reds[-1][0], reds[-1][1])
        if target is None:
            g = self.ap.button_row(img).get("grey")
            target = (g[0], g[1]) if g else None
        if target is None:
            return ExecResult(False, 0, "无叫分按钮")
        self.device.tap(*target, wait=3.0)
        return ExecResult(True, 0, f"叫分{action.meta.get('score', 0)}({'不叫' if action.meta.get('score', 0) == 0 else '叫'})")

    def _map(self, action: Action, hand: list[int]):
        """组合 → 手牌索引(逐张从低取)。"""
        combo = action.combo
        if combo is None or not getattr(combo, "ranks", None):
            return None
        used: dict[int, int] = {}
        pos: list[int] = []
        for rk in combo.ranks:
            k = used.get(rk, 0)
            found = -1
            seen = 0
            for i, h in enumerate(hand):
                if h != rk:
                    continue
                if seen == k:
                    found = i
                    break
                seen += 1
            if found < 0:
                return None
            used[rk] = k + 1
            pos.append(found)
        pos.sort()
        return pos

    # ---------- 结算 ----------
    def settle(self, frame) -> SettleInfo | None:
        if not self.ap.result_screen(frame):
            return None
        txt = ""
        try:
            from ...tools.auto_play import PROMPT_RESULT

            txt = self.vision.recognize_with_vlm(frame, PROMPT_RESULT) or ""
        except Exception:  # noqa: BLE001
            pass
        win = True if "赢" in txt else (False if "输" in txt else None)
        return SettleInfo(raw=txt.strip()[:40], win=win)
