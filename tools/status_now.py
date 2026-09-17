#!/usr/bin/env python3
"""一眼看清当前状态(设备/真值/读牌/服务/作业/git)。

用法: PYTHONPATH=src python3 tools/status_now.py
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {0: "", 1: "♠", 2: "♣", 3: "♥", 4: "♦"}


def sh(cmd: str) -> str:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"(失败 {type(e).__name__})"


print("=== 设备 ===")
print("adb:", sh("adb devices | tail -n +2 | head -3").replace("\n", " | "))
print("前台:", sh('adb -s 127.0.0.1:5555 shell dumpsys window 2>/dev/null | grep mCurrentFocus | head -1'))

print("\n=== 服务端口 ===")
for port, what in ((8123, "掼蛋游戏页"), (8130, "看板 board_api"), (8140, "直播 live_view"), (8001, "mall"), (4000, "osctl")):
    code = sh(f"curl -s --max-time 3 -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/ 2>/dev/null")
    print(f"  {port} {what}: {code or '无响应'}")

print("\n=== 游戏真值 + 读牌 ===")
try:
    from landlord_counter.guandan import percept as P
    from landlord_counter.platform.cdp import CDP
    from landlord_counter.platform.device import AdbDevice

    c = CDP()
    if not c.find_truth():
        print("  真值钩子: 无 ✗")
    else:
        t = c.truth() or {}
        hands = t.get("hands") or {}
        print(f"  阶段 {t.get('phase')} | 轮到 {t.get('current')} | 选中 {t.get('selected')}")
        print("  四家张数:", {k: len(v) for k, v in hands.items()})
        dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
        f = dev.snap()
        y0, y1 = P.hand_band_measured(f)
        rd, info = P.tm_read_hand(f)
        truth = sorted((hands.get("0") or []), reverse=True)
        got = [r for _, r, _, _l in rd]
        hit = sum(1 for a, b in zip(got, truth) if a == b)
        print(f"  手牌带 {(y0, y1)} | 抬起x {P.lifted_xs(f)}")
        shown = [f"{SUIT.get(s, '')}{NAME.get(r, str(r))}" for s, r, _, _l in rd]
        print(f"  读取({len(got)}张): {shown}")
        print(f"  真值({len(truth)}张): {[NAME.get(r, str(r)) for r in truth]}")
        print(f"  位对位命中: {hit}/{len(truth)} = {hit / max(1, len(truth)) * 100:.1f}%  (模板库 {info['tpl']} 类)")
except Exception as e:  # noqa: BLE001
    print(f"  (出错 {type(e).__name__}: {e})")

print("\n=== git ===")
print(sh("cd /project1/landlord-counter && git log --oneline -3 && git status --porcelain | head -3"))
