"""无障碍树通道: 通过 adb uiautomator dump 读取页面/应用的可访问节点。

价值(网页游戏/App 通用):
- 按钮**精确坐标**(按文字/类型查) → 不再依赖像素色块猜位置
- 页面**文字**(如结算: 头游/升级) → 统计不用 VLM, 又快又准

限制: 手牌/牌面这类纯图形元素通常**不在**树里(仍需视觉/VLM)。
"""
from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass

_TTL = 2.0  # 同一份 dump 复用时长(秒), 避免每轮都 dump(1-2s)


@dataclass
class Node:
    text: str
    cls: str
    box: tuple[int, int, int, int]      # x0,y0,x1,y1
    clickable: bool = False

    @property
    def center(self) -> tuple[int, int]:
        x0, y0, x1, y1 = self.box
        return ((x0 + x1) // 2, (y0 + y1) // 2)


class A11y:
    """一台设备的无障碍树读取器(带 TTL 缓存)。"""

    def __init__(self, serial: str = "127.0.0.1:5555", ttl: float = _TTL) -> None:
        self.serial = serial
        self.ttl = ttl
        self._nodes: list[Node] = []
        self._ts = 0.0

    # ---------- 读取 ----------
    def dump(self, force: bool = False) -> list[Node]:
        if not force and (time.time() - self._ts) < self.ttl and self._nodes:
            return self._nodes
        subprocess.run(["adb", "-s", self.serial, "shell", "uiautomator", "dump", "/sdcard/a11y.xml"],
                       capture_output=True)
        raw = subprocess.run(["adb", "-s", self.serial, "shell", "cat", "/sdcard/a11y.xml"],
                             capture_output=True).stdout.decode("utf-8", "ignore")
        nodes: list[Node] = []
        for m in re.finditer(r"<node[^>]*>", raw):
            tag = m.group(0)
            t = re.search(r'text="([^"]*)"', tag)
            c = re.search(r'class="([^"]*)"', tag)
            b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
            clk = 'clickable="true"' in tag
            if not b:
                continue
            x0, y0, x1, y1 = (int(v) for v in b.groups())
            nodes.append(Node(text=(t.group(1) if t else ""), cls=(c.group(1) if c else ""),
                              box=(x0, y0, x1, y1), clickable=clk))
        self._nodes, self._ts = nodes, time.time()
        return nodes

    # ---------- 查询 ----------
    def find(self, pattern: str, cls: str | None = None, force: bool = False) -> list[Node]:
        """按文字(正则) 找节点; cls 可限定 android.widget.Button 等。"""
        rx = re.compile(pattern)
        return [n for n in self.dump(force) if rx.search(n.text) and (cls is None or cls in n.cls)]

    def text_blob(self, force: bool = False) -> str:
        """整棵树的文字拼接(适合做"页面状态"判定)。"""
        return "\n".join(n.text for n in self.dump(force) if n.text.strip())

    def button(self, pattern: str, force: bool = False) -> Node | None:
        hits = self.find(pattern, "Button", force=force)
        return hits[0] if hits else None

    def tap_text(self, pattern: str, device) -> bool:
        """按文字找按钮并点击(优先 Button, 否则任意节点)。"""
        n = self.button(pattern, force=True) or (self.find(pattern, force=True) or [None])[0]
        if not n:
            return False
        device.tap(*n.center, wait=0.5)
        return True
