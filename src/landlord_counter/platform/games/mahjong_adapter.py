"""麻将(電脳麻将)适配器 —— 基于**无障碍树**实现(无需 VLM)。

关键发现: Firefox 把网页 DOM 暴露到 a11y 树 →
- **手牌是 Button 节点**(文字=牌名如 `チーワン`), y∈[700,820] → 可直接读取手牌
- 牌桌信息(東一局/点数/ドラ)也在树里
- 点击手牌 = 出手(重开页面后点击有效; 实测 START 与手牌点击都有响应)

状态: 真机可读手牌; 出手/回合判定仍在打磨(见 docs/M6_接入清单_实操版.md).
"""
from __future__ import annotations

import time

from ..types import Action, ExecResult, GameAdapter, Observation

HAND_Y0, HAND_Y1 = 700, 820      # 手牌按钮的 y 区间
HAND_MAX = 14                    # 摸牌后 14 张 = 该我出手


class MahjongAdapter(GameAdapter):
    name = "mahjong"
    package = None
    start_url = "http://172.18.0.1:8124/index.html"

    def __init__(self) -> None:
        self.a11y = None

    # ---------- 装配 ----------
    def attach(self, device, vision=None) -> None:
        super().attach(device, vision)
        from ..a11y import A11y

        self.a11y = A11y(getattr(device, "serial", "127.0.0.1:5555"))

    # ---------- 感知 ----------
    def start_button(self, frame):
        """标题页 START(按文字, 精确坐标)。"""
        try:
            n = self.a11y.button("START")
            return n.center if n else None
        except Exception:  # noqa: BLE001
            return None

    def _hand_nodes(self):
        return [n for n in self.a11y.dump(force=True)
                if n.cls.endswith("Button") and HAND_Y0 <= n.center[1] <= HAND_Y1 and n.text.strip()]

    def progress_signal(self, frame):
        try:
            return len(self._hand_nodes())
        except Exception:  # noqa: BLE001
            return None

    def sense(self, frame) -> Observation:
        try:
            hand = self._hand_nodes()
        except Exception:  # noqa: BLE001
            hand = []
        names = [n.text for n in hand]
        my_turn = len(names) >= HAND_MAX            # 摸牌后 14 张 ⇒ 轮到我出手
        return Observation(frame=frame, my_turn=my_turn, hand=names,
                           extra={"phase": "discard" if my_turn else "wait"})

    # ---------- 决策 ----------
    def decide(self, obs: Observation) -> Action:
        """占位策略: 打出最后一张(即刚摸到的牌 = ツモ切り)。后续接规则/模型。"""
        hand = obs.hand or []
        if not hand:
            return Action("none")
        return Action("play", combo=len(hand) - 1, meta={"why": "ツモ切り(占位策略)"})

    # ---------- 执行 ----------
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        nodes = self._hand_nodes()
        if not nodes:
            return ExecResult(False, 0, "读不到手牌")
        idx = min(int(action.combo or 0), len(nodes) - 1)
        target = nodes[idx]
        before = len(nodes)
        self.device.tap(*target.center, wait=1.2)
        time.sleep(1.0)
        after_nodes = self._hand_nodes()
        after = len(after_nodes)
        if after < before:      # 手牌减少 = 真的出手了
            return ExecResult(True, 0, f"打出 {target.text}({before}→{after})")
        if after == before and before == HAND_MAX:
            return ExecResult(False, 1, f"点击未出手({before}→{after}, 手牌未减)")
        return ExecResult(False, 1, f"状态未知({before}→{after})")

    def settle(self, frame):
        return None
