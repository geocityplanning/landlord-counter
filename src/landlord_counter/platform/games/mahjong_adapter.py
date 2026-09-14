"""麻将(電脳麻将)适配器 —— 基于**无障碍树**实现(无需 VLM)。

关键发现: Firefox 把网页 DOM 暴露到 a11y 树 →
- **手牌是 Button 节点**(文字=牌名如 `チーワン`), y∈[700,820] → 可直接读取手牌
- 牌桌信息(東一局/点数/ドラ)也在树里
- 点击手牌 = 出手(重开页面后点击有效; 实测 START 与手牌点击都有响应)

状态: 真机可读手牌; 出手/回合判定仍在打磨(见 docs/M6_接入清单_实操版.md).
"""
from __future__ import annotations

import re
import time

from ..types import Action, ExecResult, GameAdapter, Observation

HAND_Y0, HAND_Y1 = 700, 820      # 手牌按钮的 y 区间
HAND_MAX = 14                    # 摸牌后 14 张 = 该我出手
# 副露(吃/碰/杠)后手牌变少, 但规律不变: 该我出手时张数 ≡ 2 (mod 3), 等待中 ≡ 1 (mod 3)
#   无副露 13→14, 一副露 10→11, 两副露 7→8 ...
ACTION_TEXTS = {"チー", "ポン", "カン", "リーチ", "ツモ", "ロン", "キャンセル", "パス"}
# 手牌牌名(日本語読み): イーワン/リャンピン/サンソー... + 字牌(トン/ナン/シャー/ペー/ハツ/チュン)
# 注意: 不同承载暴露的控件类不同 —— Focus=Button, Bromite(Chromium)=**Image**;
#       所以按"文字+位置"识别, 不要依赖控件类(踩过: 只认 Button → 手牌恒为空 → 0 动作)。
TILE_RE = re.compile(
    r"^(赤)?(イー|リャン|サン|スー|ウー|ロー|チー|パー|キュー)(ワン|ピン|ソー)$"
    r"|^(トン|ナン|シャー|ペー|ハツ|チュン)$"
)


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
        """手牌节点: 位置在手牌带内 + 牌名文本(不依赖控件类)。"""
        out = []
        for n in self.a11y.dump(force=True):
            t = (n.text or "").strip()
            if t and TILE_RE.match(t) and HAND_Y0 <= n.center[1] <= HAND_Y1:
                out.append(n)
        return out

    def _action_nodes(self):
        """吃/碰/杠/立直/自摸/和了/取消 等操作按钮(按文字匹配, 不限控件类/位置)。"""
        return [n for n in self.a11y.dump(force=True)
                if (n.text or "").strip() in ACTION_TEXTS]

    def _wall(self):
        """剩余牌数(牌数: N) —— 全局水位, 随对局单调下降, 比手牌节点稳。"""
        try:
            txt = [n.text.strip() for n in self.a11y.dump()]
        except Exception:  # noqa: BLE001
            return None
        for i, t in enumerate(txt):
            if t == "牌数:" and i + 1 < len(txt):
                try:
                    return int(txt[i + 1])
                except ValueError:
                    return None
        return None

    def progress_signal(self, frame):
        w = self._wall()
        if w is not None:
            return w
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
        # 有操作提示(チー/ポン/カン/リーチ/キャンセル...) ⇒ 一定在等我应答
        #   (实测: 提示阶段手牌节点会从无障碍树里消失, 只看手牌数会永久卡住)
        if acts:
            return Observation(frame=frame, my_turn=True, hand=names,
                               extra={"phase": "prompt", "actions": acts})
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
        target = nodes[min(int(action.combo or 0), len(nodes) - 1)]
        before_names = [n.text for n in nodes]
        wall0 = self._wall()
        # 主路径 = **键盘通道**: 本容器里 touch 对页面完全无效(实测点击后牌面/牌数零变化),
        # 而网页游戏实现了键盘选择(setSelector): 方向键移动选择器 + Enter 确认。
        # 方向键按到底(次数 > 张数)使选择器**夹在最后一张** ⇒ 确定性"ツモ切り"(弃刚摸的牌)。
        for _ in range(len(nodes) + 6):
            self.device.shell("input", "keyevent", "22")   # KEYCODE_DPAD_RIGHT
            time.sleep(0.18)
        self.device.shell("input", "keyevent", "66")       # KEYCODE_ENTER
        time.sleep(1.6)
        # 回执: 牌数下降(全局水位) 或 手牌牌面变化
        for _ in range(3):
            time.sleep(1.0)
            if wall0 is not None:
                w = self._wall()
                if w is not None and w < wall0:
                    self._fails = 0
                    return ExecResult(True, 0, f"键盘出手(牌数 {wall0}→{w})")
            names = [n.text for n in self._hand_nodes()]
            if names and names != before_names:
                self._fails = 0
                return ExecResult(True, 0, f"键盘出手 牌面变化({len(before_names)}→{len(names)})")
        # 兜底1: 再补一次 Enter(动画/焦点未落定)
        self.device.shell("input", "keyevent", "66")
        time.sleep(1.2)
        names = [n.text for n in self._hand_nodes()]
        if names and names != before_names:
            self._fails = 0
            return ExecResult(True, 0, "补 Enter 出手")
        # 兜底2: 点按(某些承载/容器触控可用)
        self.device.tap(*target.center, wait=1.0)
        time.sleep(1.0)
        names = [n.text for n in self._hand_nodes()]
        if names and names != before_names:
            self._fails = 0
            return ExecResult(True, 0, "点击兜底出手")
        # 未变化: 多半不是我的回合 → 记失败并退避(避免狂点)
        self._fails += 1
        if self._fails >= 2:
            time.sleep(min(6.0, 1.5 * self._fails))
        return ExecResult(False, 1, f"点击未出手(手牌未变{fails if False else ''})")

    def settle(self, frame):
        return None
