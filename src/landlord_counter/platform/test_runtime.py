"""通用运行时离线单测: 假设备 + 假适配器 → 验证主循环/进桌/统计/看门狗。

运行: PYTHONPATH=src python3 -m landlord_counter.platform.test_runtime
"""
from __future__ import annotations

import os
import tempfile

import numpy as np

from .runtime import Runtime
from .types import Action, ExecResult, GameAdapter, Observation, SettleInfo


class FakeDevice:
    def __init__(self, frames):
        self.frames = frames
        self.i = 0
        self.taps = []
        self.recoveries = 0

    def snap(self):
        f = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return f

    def tap(self, x, y, wait=0.0):
        self.taps.append((x, y))

    def recover(self, package=None, url=None):
        self.recoveries += 1
        self.i = 0  # 恢复后重新开始序列


class FakeAdapter(GameAdapter):
    name = "fake"
    start_url = "x"

    def __init__(self):
        self.start_calls = 0
        self.plays = 0

    def start_button(self, frame):
        return (100, 100) if frame[0, 0, 0] == 1 else None

    def progress_signal(self, frame):
        return int(frame[0, 0, 1])

    def sense(self, frame):
        return Observation(frame=frame, my_turn=True, hand=[1, 2, 3])

    def decide(self, obs):
        return Action("play", combo=None)

    def execute(self, action, obs):
        self.plays += 1
        import time as _t
        _t.sleep(0.05)          # 模拟点击耗时, 避免空转刷屏
        return ExecResult(True, 0, "fake")

    def settle(self, frame):
        return SettleInfo(raw="头游=南", win=True) if frame[0, 0, 0] == 1 else None


def frame(a=0, b=0):
    f = np.zeros((4, 4, 3), np.uint8)
    f[0, 0] = (a, b, 0)
    return f


def main() -> int:
    failed = 0

    # 1) 进桌 + 结算统计
    dev = FakeDevice([frame(1, 1), frame(0, 5), frame(0, 6)])
    ad = FakeAdapter()
    with tempfile.NamedTemporaryFile("r", suffix=".csv", delete=False) as tf:
        csv_path = tf.name
    rt = Runtime(ad, dev, stats_path=csv_path, tag="test", watchdog_s=999)
    rt.run(seconds=0.6)
    lines = [ln for ln in open(csv_path) if ln.strip()]
    print("taps:", dev.taps, "| csv:", lines)
    if not (dev.taps and lines and "win" in lines[0]):
        print("✗ 进桌/统计 未通过")
        failed += 1
    else:
        print("✓ 进桌 + 结算统计 通过")
    os.unlink(csv_path)

    # 2) 看门狗: 进展信号不变 → 应触发恢复
    dev2 = FakeDevice([frame(0, 7)] * 5)
    ad2 = FakeAdapter()
    ad2.decide = lambda obs: Action("none")
    rt2 = Runtime(ad2, dev2, watchdog_s=0.3, heartbeat_s=99, idle_sleep=0.05)
    # 让 decide 返回 pass(有动作) 但进度信号不变 → 仍触发恢复
    rt2.run(seconds=2.0)
    print("recoveries:", dev2.recoveries)
    if dev2.recoveries >= 1:
        print("✓ 看门狗自愈 通过")
    else:
        print("✗ 看门狗 未触发")
        failed += 1

    # 3) 执行计数
    dev3 = FakeDevice([frame(0, 1), frame(0, 2), frame(0, 3)])
    ad3 = FakeAdapter()
    rt3 = Runtime(ad3, dev3, watchdog_s=999, idle_sleep=0.05)
    out = rt3.run(seconds=0.4)
    print("actions:", out)
    if out["actions"] >= 1:
        print("✓ 动作执行 通过")
    else:
        print("✗ 动作执行 未通过")
        failed += 1

    print(f"\n通过 {3 - failed} 项, 失败 {failed} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
