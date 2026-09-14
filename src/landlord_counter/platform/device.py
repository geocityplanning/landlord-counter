"""设备层: adb 截屏/点击/按键(与游戏无关)。"""
from __future__ import annotations

import os
import subprocess
import time

import cv2
import numpy as np


class AdbDevice:
    """一台安卓设备(云手机/模拟器)。"""

    def __init__(self, serial: str = "127.0.0.1:5555", url: str | None = None,
                 browser_pkg: str | None = None) -> None:
        self.serial = serial
        self.url = url
        self.browser_pkg = browser_pkg or os.getenv("BROWSER_PKG", "org.bromite.bromite")

    # ---- 基础 ----
    def shell(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["adb", "-s", self.serial, "shell", *args],
                              capture_output=True, text=True)

    def snap(self) -> np.ndarray | None:
        raw = subprocess.run(["adb", "-s", self.serial, "exec-out", "screencap", "-p"],
                             capture_output=True).stdout
        if not raw:
            return None
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        return img

    def tap(self, x: int, y: int, wait: float = 0.3) -> None:
        self.shell("input", "tap", str(int(x)), str(int(y)))
        if wait:
            time.sleep(wait)

    # ---- 恢复(看门狗用) ----
    def force_stop(self, pkg: str) -> None:
        self.shell("am", "force-stop", pkg)

    def open_url(self, url: str, component: str | None = None) -> None:
        component = component or os.getenv("BROWSER_COMPONENT") or os.getenv("BROWSER_ACT")
        args = ["am", "start", "-a", "android.intent.action.VIEW", "-d", url]
        if component:
            args += ["-n", component]
        self.shell(*args)

    def recover(self, package: str | None = None, url: str | None = None) -> None:
        """通用恢复: 有网页入口→重开浏览器; 否则重启 App。"""
        url = url or self.url
        if url:
            self.force_stop(self.browser_pkg)
            time.sleep(2)
            self.open_url(url, os.getenv("BROWSER_COMPONENT") or None)
        elif package:
            self.shell("am", "force-stop", package)
            time.sleep(1)
            self.shell("monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(12)
