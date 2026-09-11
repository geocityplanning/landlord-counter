"""通用手势执行层: 点选验证 / 扫点 / 提示选牌 / 回执轮询 / 两轮重试。

与游戏无关——游戏只需提供 GestureLayout(牌位公式/按钮坐标/判据函数)。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass
class GestureLayout:
    """一款游戏的布局与判据(由适配器提供)。

    按钮坐标可以是固定点, 也可以用 ``btn_resolver(frame)`` 动态解析(如按颜色找按钮)。
    """

    card_tap_x: Callable[[int, int], int]      # (索引, 手牌张数) -> 设备x
    hand_y: int                                # 手牌带点击 y
    lift_px: Callable[[np.ndarray], int]       # 抬起像素量(用于选牌验证)
    my_turn: Callable[[np.ndarray], bool]      # 是否我方回合(含按钮可用)
    white_count: Callable[[np.ndarray], int]   # 手牌白卡像素(用于回执)
    btn_hint: tuple[int, int] | None = None
    btn_play: tuple[int, int] | None = None
    btn_pass: tuple[int, int] | None = None
    btn_resolver: Callable[[np.ndarray], dict] | None = None   # → {'hint','play','pass'} 坐标
    lift_diff: Callable[[np.ndarray, np.ndarray], float] | None = None  # 帧差抬起量(可选, 更稳)
    lift_eps: float = 300.0     # "新抬起一张"的最小增量(像素口径≈300, 张数口径≈0.5)
    lift_one: float = 1460.0    # 单张抬起量(像素口径≈1460, 张数口径=1)
    lift_min: float = 500.0     # 判定"有选中"的最小抬起量


class Executor:
    """通用出牌执行器。所有动作自带验证与重试, 绝不"静默失败"。"""


    def __init__(self, device, layout: GestureLayout, log: Callable[[str], None] = print) -> None:
        self.dev = device
        self.L = layout
        self.log = log

    # ---------- 基础 ----------
    def _snap(self):
        return self.dev.snap()

    def _lift(self, img) -> int:
        return self.L.lift_px(img) if img is not None else 0

    def btn(self, name: str, frame=None):
        """取按钮坐标: 优先 btn_resolver(动态), 否则固定点。返回 None 表示当前不可用。"""
        if self.L.btn_resolver is not None:
            img = frame if frame is not None else self._snap()
            if img is None:
                return None
            return self.L.btn_resolver(img).get(name)
        return getattr(self.L, f"btn_{name}", None)

    def tap_card(self, idx: int, n: int) -> bool:
        """点选第 idx 张并验证抬起; 失败则左右扫点(小牌量牌位漂移)。

        验证方式: 有 lift_diff(帧差) 用它(更稳); 否则用绝对抬起量增量。
        """
        base = self.L.card_tap_x(idx, n)
        for dx in (0, 8, -8, 16, -16):
            if self.L.lift_diff is not None:
                before_img = self._snap()
                self.dev.tap(base + dx, self.L.hand_y, wait=0.35)
                after_img = self._snap()
                if after_img is None:
                    continue
                if self.L.lift_diff(before_img, after_img) >= self.L.lift_eps:
                    return True
            else:
                before = self._lift(self._snap())
                self.dev.tap(base + dx, self.L.hand_y, wait=0.30)
                after = self._lift(self._snap())
                if after > before + self.L.lift_eps:
                    return True
        return False

    def select(self, idxs: list[int], n: int) -> bool:
        """逐张点选; 全中才算成功。"""
        for i in idxs:
            if not self.tap_card(i, n):
                self.log(f"  [gesture] ✗ 点选不中 idx={i} (n={n})")
                return False
        return True

    def clear(self, idxs: list[int], n: int) -> None:
        for i in idxs:
            self.dev.tap(self.L.card_tap_x(i, n), self.L.hand_y, wait=0.15)

    def selected_count(self, img) -> int:
        lift = self._lift(img)
        return round(lift / self.L.lift_one) if lift > self.L.lift_min else 0

    def pass_turn(self, frame=None) -> bool:
        p = self.btn("pass", frame)
        if not p:
            self.log("  [gesture] ✗ 找不到'不出'按钮")
            return False
        self.dev.tap(*p, wait=1.6)
        return True

    # ---------- 出牌 ----------
    def wait_receipt(self, before: int, polls: int = 8, poll_s: float = 0.4) -> bool:
        """回执: 回合交出 或 手牌白卡明显下降。"""
        for _ in range(polls):
            time.sleep(poll_s)
            img = self._snap()
            if img is None:
                continue
            if not self.L.my_turn(img) or self.L.white_count(img) < before - 1500:
                return True
        return False

    def play_by_hint(self, want: int | None = None, follow: bool = False) -> str:
        """提示选牌执行: 提示 → 张数校验 → 出牌 → 回执(带补点一次)。

        返回 'ok' | 'none'(无可出) | 'mismatch'(张数不符, 已清选) | 'fail'
        """
        before = self.L.white_count(self._snap())
        ph = self.btn("hint")
        if not ph:
            return "fail"
        self.dev.tap(*ph, wait=1.6)
        iv = self._snap()
        est = self.selected_count(iv)
        if est == 0:
            return "none"
        if want and not follow and abs(est - want) > max(1, want // 2):
            self.pass_turn()                              # 清掉提示选中的牌
            return "mismatch"
        pp = self.btn("play")
        if not pp:
            return "fail"
        self.dev.tap(*pp, wait=1.6)
        if self.wait_receipt(before):
            return "ok"
        self.log("  [gesture] ↻ 出牌未生效 → 补点一次")
        self.dev.tap(*pp, wait=1.6)
        if self.wait_receipt(before, polls=6):
            return "ok"
        return "fail"

    def direct_play(self, idxs: list[int], n: int, rounds: int = 2) -> bool:
        """直选执行: 点选 → 校验张数 → 出牌 → 回执; 失败清选后再来一轮。"""
        before = self.L.white_count(self._snap())
        for r in range(rounds):
            if r:
                self.log("  [gesture] ↻ 直选重试(重新取帧)")
                time.sleep(1.0)
            if not self.select(idxs, n):
                self.clear(idxs, n)
                continue
            time.sleep(0.5)
            est = self.selected_count(self._snap())
            if est == 0 or abs(est - len(idxs)) > max(1, len(idxs) // 2):
                self.log(f"  [gesture] ✗ 选牌校验失败(选中≈{est} vs 目标{len(idxs)})")
                self.clear(idxs, n)
                continue
            pp = self.btn("play")
            if not pp:
                self.clear(idxs, n)
                continue
            self.dev.tap(*pp, wait=1.6)
            if self.wait_receipt(before):
                return True
            self.log("  [gesture] ↻ 出牌未生效 → 补点一次")
            self.dev.tap(*pp, wait=1.6)
            if self.wait_receipt(before, polls=6):
                return True
            self.clear(idxs, n)
        return False
