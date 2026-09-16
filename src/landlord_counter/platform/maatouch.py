"""MaaTouch 输入层: 拟人化触摸注入(压力/接触/时长/抖动/微移)。

为什么不用 `adb shell input tap`(2026-09-16 实测):
  · 该注入生成的 MotionEvent 极简(无压力/无接触面积/瞬时), 实测在掼蛋页上
    **点"出牌"按钮完全无反应**(而点手牌能用) —— 同页面不同元素表现不同,
    说明游戏侧对事件属性/时序有要求;
  · 而且 `input` 是公开的自动化指纹(反作弊易识别)。
MaaTouch(openstax/minitouch 协议的安卓原生实现, Apache-2.0)通过 InputManager 注入
**带压力与接触属性的真实 MotionEvent**, 走 stdin/stdout 的文本协议:
    d <id> <x> <y> <pressure>   按下
    m <id> <x> <y> <pressure>   移动
    u <id>                      抬起
    c                           提交(必须)
    k <key> d|u|o               按键(下/抬/单次)
    t <text>                    输入文本

本模块在此之上加"拟人化": 坐标抖动 + 随机按下时长 + 按压中的微移 + 随机压力。
"""
from __future__ import annotations

import os
import random
import subprocess
import time

BIN = "/data/local/tmp/maatouch"
MAIN = "com.shxyke.MaaTouch.App"


class MaaTouch:
    """持有一个常驻的 MaaTouch 进程(adb shell + stdin 管道)。"""

    def __init__(self, serial: str = "127.0.0.1:5555", human: bool = True) -> None:
        self.serial = serial
        self.human = human
        self.proc: subprocess.Popen | None = None
        self.max_x, self.max_y, self.max_p = 720, 1280, 255
        self.start()

    # ---------- 生命周期 ----------
    def start(self) -> bool:
        cmd = ["adb", "-s", self.serial, "shell",
               f"CLASSPATH={BIN} app_process /data/local/tmp {MAIN}"]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
        t0 = time.time()
        while time.time() - t0 < 10:
            line = self.proc.stdout.readline() if self.proc.stdout else ""
            if not line:
                break
            line = line.strip()
            if line.startswith("^"):                       # ^ <max> <w> <h> <p>
                p = line.split()
                if len(p) >= 5:
                    self.max_x, self.max_y, self.max_p = int(p[2]), int(p[3]), int(p[4])
            elif line.startswith("$"):
                return True
        return False

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def close(self) -> None:
        try:
            if self.proc and self.proc.stdin:
                self.proc.stdin.close()
            if self.proc:
                self.proc.terminate()
        except Exception:  # noqa: BLE001
            pass

    # ---------- 底层 ----------
    def _w(self, line: str) -> None:
        if not self.alive():
            self.start()
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _commit(self) -> None:
        self._w("c")

    # ---------- 拟人化参数 ----------
    def _jitter(self, x: int, y: int, px: int = 3) -> tuple[int, int]:
        if not self.human:
            return x, y
        return (max(0, min(self.max_x - 1, x + random.randint(-px, px))),
                max(0, min(self.max_y - 1, y + random.randint(-px, px))))

    def _pressure(self) -> int:
        return random.randint(90, 190) if self.human else 128

    # ---------- 对外动作 ----------
    def tap(self, x: int, y: int, duration_ms: int | None = None) -> None:
        """拟人化单击: 抖动坐标 + 随机按下时长 + 按压中微移(真人手指会漂)。"""
        x, y = self._jitter(int(x), int(y))
        dur = duration_ms if duration_ms is not None else random.randint(45, 130)
        pr = self._pressure()
        self._w(f"d 0 {x} {y} {pr}")
        self._commit()
        if self.human and dur > 60:
            # 按压中的微移(1~2px), 更接近真实手指
            mx, my = self._jitter(x, y, 2)
            time.sleep(dur / 2000.0)
            self._w(f"m 0 {mx} {my} {self._pressure()}")
            self._commit()
        time.sleep(dur / 1000.0)
        self._w("u 0")
        self._commit()

    def swipe(self, x0: int, y0: int, x1: int, y1: int, ms: int = 300, steps: int = 8) -> None:
        """拟人化滑动: 贝塞尔-ish 分段 + 时间抖动。"""
        x0, y0 = self._jitter(int(x0), int(y0))
        x1, y1 = self._jitter(int(x1), int(y1))
        self._w(f"d 0 {x0} {y0} {self._pressure()}")
        self._commit()
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(x0 + (x1 - x0) * t + (random.randint(-2, 2) if self.human else 0))
            cy = int(y0 + (y1 - y0) * t + (random.randint(-2, 2) if self.human else 0))
            self._w(f"m 0 {cx} {cy} {self._pressure()}")
            self._commit()
            time.sleep(max(0.005, ms / 1000.0 / steps + (random.uniform(-0.01, 0.01) if self.human else 0)))
        self._w("u 0")
        self._commit()

    def key(self, code: int) -> None:
        """单次按键(4=返回, 3=Home, 187=最近任务)。"""
        self._w(f"k {code} o")
        self._commit()


if __name__ == "__main__":       # 自测: 打印协议头 + 在屏幕中央轻点一下
    mt = MaaTouch()
    print("MaaTouch 就绪:", mt.alive(), f"屏幕 {mt.max_x}x{mt.max_y} 压力上限 {mt.max_p}")
    mt.tap(mt.max_x // 2, mt.max_y // 2)
    time.sleep(0.5)
    print("已发送一次拟人化点击; 进程存活:", mt.alive())
    mt.close()
