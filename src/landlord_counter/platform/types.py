"""通用层类型: 观测 / 动作 / 执行结果 / 结算 + GameAdapter 抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np

Point = tuple[int, int]


@dataclass
class Observation:
    """一帧的语义观测(由适配器填充)。"""

    frame: np.ndarray
    my_turn: bool = False
    hand: Any = None                 # 游戏自定义(掼蛋: list[Card], 斗地主: list[int])
    table: Any = None                # 桌面待压牌 / 出牌区
    buttons: dict[str, Point] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """决策结果。kind: play(出牌, combo 为组合) / pass(不出) / start(点开始) / none(不动作)"""

    kind: str
    combo: Any = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecResult:
    """执行结果; ok=False 时由 Runtime 决定重试/回落。"""

    ok: bool
    retries: int = 0
    detail: str = ""


@dataclass
class SettleInfo:
    """结算信息(用于统计)。win=None 表示未能判定。"""

    raw: str = ""
    win: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class GameAdapter(ABC):
    """一款游戏的托管适配器。Runtime 只依赖本接口。"""

    name: str = "unnamed"
    package: str | None = None       # 安卓包名(网页版游戏为 None)
    start_url: str | None = None     # 网页版游戏入口(供 device.recover 使用)

    # ---- 生命周期 ----
    def attach(self, device, vision=None) -> None:
        """注入设备与识别器(Runtime 启动时调用)。"""
        self.device = device
        self.vision = vision

    # ---- 感知/决策/执行 ----
    @abstractmethod
    def start_button(self, frame) -> Point | None:
        """开始游戏/再接一局的大按钮中心; 没有则 None。"""

    @abstractmethod
    def sense(self, frame) -> Observation:
        """解析当前帧 → 观测。"""

    @abstractmethod
    def decide(self, obs: Observation) -> Action:
        """根据观测决策。"""

    @abstractmethod
    def execute(self, action: Action, obs: Observation) -> ExecResult:
        """执行动作(含回执校验与重试)。"""

    def settle(self, frame) -> SettleInfo | None:
        """结算解读; 不在结算页返回 None。"""
        return None

    # ---- 可选: 供 Runtime 判断"是否有进展"的信号 ----
    def progress_signal(self, frame) -> Any:
        """返回一个可比对的值(如手牌像素量), 用于看门狗判定。默认 None=不可用。"""
        return None
