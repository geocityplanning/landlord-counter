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
# 副露(吃/碰/杠)后手牌变少, 但规律不变: 该我出手时张数 ≡ 2 (mod 3), 等待中 ≡ 1 (mod 3)
#   无副露 13→14, 一副露 10→11, 两副露 7→8 ...
ACTION_TEXTS = {"チー", "ポン", "カン", "リーチ", "ツモ", "ロン", "キャンセル", "パス"}


class MahjongAdapter(GameAdapter):
    name = "mahjong"
    package = None
    start_url = "http://172.18.0.1:8124/index.html"

    def __init__(self) -> None:
        self.a11y = None
        self._fails = 0        # 连续"点击未出手"次数(用于退避)

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
        """手牌节点: y 在带内、且**不是**操作按钮(实测 ポン/キャンセル 会出现在同一 y 带内,
        混进来会让"手牌数"虚增并误判轮次)。"""
        out = []
        for n in self.a11y.dump(force=True):
            t = (n.text or "").strip()
            if not n.cls.endswith("Button") or not t:
                continue
            if t in ACTION_TEXTS:
                continue
            if HAND_Y0 <= n.center[1] <= HAND_Y1:
                out.append(n)
        return out

    def _action_nodes(self):
        """吃/碰/杠/立直/自摸/和了/取消 等操作按钮(不在手牌带内的按钮节点)。"""
        out = []
        for n in self.a11y.dump(force=True):
            t = (n.text or "").strip()
            if not n.cls.endswith("Button") or t not in ACTION_TEXTS:
                continue
            if HAND_Y0 <= n.center[1] <= HAND_Y1:
                continue
            out.append(n)
        return out

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
        try:
            acts = [n.text.strip() for n in self._action_nodes()]
        except Exception:  # noqa: BLE001
            acts = []
        # 该我出手: 张数 ≡ 2 (mod 3)（副露后手牌会少, 旧判据 ">=14" 会永久卡住）
        my_turn = len(names) >= 2 and len(names) % 3 == 2
        return Observation(frame=frame, my_turn=my_turn, hand=names,
                           extra={"phase": "discard" if my_turn else "wait", "actions": acts})

    # ---------- 决策 ----------
    def decide(self, obs: Observation) -> Action:
        """策略: ① 有和了/自摸 → 直接按; ② 有其它提示(吃碰立直) → 取消(演示阶段不打乱); ③ 否则打最后一张(ツモ切り)。"""
        acts = (obs.extra or {}).get("actions") or []
        if any(a in ("ツモ", "ロン") for a in acts):
            return Action("act", meta={"text": "ツモ", "why": "和了"})
        if acts:
            return Action("act", meta={"text": "キャンセル", "why": f"跳过提示 {acts}"})
        hand = obs.hand or []
        if not hand:
            return Action("none")
        idx = len(hand) - 1 - (self._fails % max(1, len(hand)))
        return Action("play", combo=idx, meta={"why": f"ツモ切り/轮换(占位策略, fails={self._fails})"})

    # ---------- 执行 ----------
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        # —— 操作按钮(取消/和了): 直接点该按钮, 回执=按钮消失/手牌变化 ——
        if action.kind == "act":
            want = (action.meta or {}).get("text")
            acts = self._action_nodes()
            tgt = next((n for n in acts if n.text.strip() == want), None) or (acts[0] if acts else None)
            if not tgt:
                return ExecResult(False, 0, "按钮已消失")
            before = [n.text for n in self._action_nodes()]
            self.device.tap(*tgt.center, wait=1.2)
            for _ in range(3):
                time.sleep(0.8)
                after = [n.text for n in self._action_nodes()]
                if after != before:
                    return ExecResult(True, 0, f"点击 {tgt.text}")
            return ExecResult(False, 1, f"按钮点击无效 {tgt.text}")

        nodes = self._hand_nodes()
        if not nodes:
            return ExecResult(False, 0, "读不到手牌")
        idx = min(int(action.combo or 0), len(nodes) - 1)
        target = nodes[idx]
        before_names = [n.text for n in nodes]
        # 主路径 = **点击该牌**(物理通道, 与真实玩家一致)。
        # 注意: ENTER 只做兜底 —— 实测 ENTER 会激活页面上获得焦点的导航链接,
        #       把页面带回标题页(跑 2 步就掉出对局)。
        self.device.tap(*target.center, wait=1.0)
        # 回执: 轮询手牌**列表**是否变化(打出/摸牌都会变), 最多 ~3 次
        for _ in range(3):
            time.sleep(1.0)
            after = self._hand_nodes()
            names = [n.text for n in after]
            if len(names) != len(before_names) or names != before_names:
                self._fails = 0
                return ExecResult(True, 0, f"打出 {target.text}({len(before_names)}→{len(names)})")
        # 兜底: ENTER(自摸切り时 UI 聚焦最后一张; 用后若页面跳回标题页由 Runtime 的进桌逻辑兜)
        self.device.shell("input", "keyevent", "66")
        time.sleep(0.9)
        n_after_key = [n.text for n in self._hand_nodes()]
        if not n_after_key or n_after_key != before_names:
            self._fails = 0
            return ExecResult(True, 0, f"ENTER 兜底出手({len(before_names)}→{len(n_after_key)})")
        # 未变化: 多半不是我的回合 → 记失败并退避(避免狂点)
        self._fails += 1
        if self._fails >= 2:
            time.sleep(min(6.0, 1.5 * self._fails))
        return ExecResult(False, 1, f"点击未出手(手牌未变{fails if False else ''})")

    def settle(self, frame):
        return None
