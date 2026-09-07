"""截屏层：通过 ADB 从安卓设备/模拟器获取屏幕截图。"""
from __future__ import annotations

import subprocess
from typing import Optional

import numpy as np

from ..config import ScreenConfig


class ADBError(RuntimeError):
    pass


class ScreenCapturer:
    """ADB 截屏器"""

    def __init__(self, config: ScreenConfig):
        self.cfg = config

    def _adb(self, *args: str) -> bytes:
        cmd = ["adb"]
        if self.cfg.adb_serial:
            cmd += ["-s", self.cfg.adb_serial]
        cmd += list(args)
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=15)
        except subprocess.TimeoutExpired:
            raise ADBError("adb 命令超时")
        if proc.returncode != 0:
            raise ADBError(
                f"adb {' '.join(args)} 失败: {proc.stderr.decode(errors='ignore')}"
            )
        return proc.stdout

    def list_devices(self) -> list[str]:
        out = self._adb("devices").decode(errors="ignore")
        devices = []
        for line in out.splitlines()[1:]:
            if line.strip() and "\tdevice" in line:
                devices.append(line.split("\t")[0])
        return devices

    def capture(self) -> np.ndarray:
        """截屏并返回 BGR numpy 数组"""
        png_bytes = self._adb("exec-out", "screencap", "-p")
        if not png_bytes:
            raise ADBError("截屏返回空数据")
        import cv2

        img = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ADBError("截屏数据解码失败")
        if self.cfg.screen_scale != 1.0:
            img = cv2.resize(
                img, None, fx=self.cfg.screen_scale, fy=self.cfg.screen_scale
            )
        return img

    def capture_roi(self, roi_normalized: tuple) -> np.ndarray:
        """按归一化坐标 (x1,y1,x2,y2) 裁剪区域"""
        img = self.capture()
        h, w = img.shape[:2]
        x1, y1, x2, y2 = roi_normalized
        return img[int(y1 * h) : int(y2 * h), int(x1 * w) : int(x2 * w)]
