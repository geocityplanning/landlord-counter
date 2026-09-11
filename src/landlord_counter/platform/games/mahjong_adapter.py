"""麻将(電脳麻将)适配器 —— **进行中, 未通过真机验收**。

已完成: 选型(kobalab/Majiang, MIT)、构建(dist)、本地托管(8124)、页面打开(START@(360,430))、
        牌桌几何初标定(台面绿/手牌带 y≈740-800/起点 x≈109/间距≈33)。
未完成: 回合判定、"点击手牌出手"交互确认、决策(规则/模型)、结算统计。

接入步骤见 docs/M6_接入清单_实操版.md（第 3-5 步）。
"""
from __future__ import annotations

import time

import cv2
import numpy as np

from ..types import Action, ExecResult, GameAdapter, Observation

HAND_BAND = (735, 805)      # 手牌带 y 区间(初标定)
HAND_ROW_Y = 770            # 点击 y
HAND_START_X = 109.0        # 手牌起点 x(初标定)
TILE_PITCH = 33.0           # 相邻牌露出间距(初标定, 13 张时)
TILE_EXPOSED = 20.0         # 露出宽度
WHITE_MIN = 2500            # 手牌带白像素阈值(初标定)


def _white(img) -> np.ndarray:
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    return (b > 200) & (g > 200) & (r > 200)


def hand_white(img) -> int:
    y0, y1 = HAND_BAND
    return int(_white(img)[y0:y1].sum())


class MahjongAdapter(GameAdapter):
    name = "mahjong"
    package = None
    start_url = "http://172.18.0.1:8124/index.html"

    def start_button(self, frame):
        """TODO: 标题页 START 按钮检测(实测 @(360,430) 可开始, 但目前写死)。"""
        return None

    def progress_signal(self, frame):
        return hand_white(frame)

    def sense(self, frame) -> Observation:
        """TODO: 真正的"轮到我"判据(需相位/按钮视觉)。当前仅按手牌白像素粗判。"""
        wc = hand_white(frame)
        return Observation(frame=frame, my_turn=wc >= WHITE_MIN, hand=None, extra={"white": wc})

    def decide(self, obs: Observation) -> Action:
        """TODO: 决策(打出哪张)。当前为占位: 打第一张。"""
        return Action("play", combo=0, meta={"why": "占位: 打第一张(未实现决策)"})

    def execute(self, action: Action, obs: Observation) -> ExecResult:
        """TODO: 需要先确认"点击手牌即出手"的交互; 当前为坐标探测实现。"""
        i = int(action.combo or 0)
        x = int(HAND_START_X + i * TILE_PITCH + TILE_EXPOSED / 2)
        self.device.tap(x, HAND_ROW_Y, wait=1.2)
        return ExecResult(True, 0, f"试探点击手牌#{i} @({x},{HAND_ROW_Y})")

    def settle(self, frame):
        return None
