"""掼蛋托管: 平台入口 + 少量共用常量/小工具。

★ 2026-09-21 大清理(用户: "既然规则这个不行, 直接不修了, 删了吧, 直接用RL"):
  本文件原来还带着一条 **旧的自研视觉主循环**(读手牌→规则决策→点牌, 约 470 行)。
  它早就被 ``platform/`` 通用层取代, 实测**外部零调用** ⇒ 按"停用=删掉"整条删除 ✗,
  连带 ``ai.choose_play`` 那条**规则决策臂**一起删(见 ai.py / guandan_adapter.py)。

  保留下来的, 只有**别人还在用的东西**:
    * ``BTN_HINT/BTN_PLAY/BTN_PASS`` / ``JIPAI``  ← guandan_adapter 导入 ✓
    * ``tap`` / ``snap`` / ``gold_button``       ← tools/guandan_prep.py 导入 ✓
    * ``map_indices``                            ← guandan_adapter 用(牌→手牌下标)✓
    * ``main()``                                 ← tools/demo_guandan.sh / night_guandan.sh 在用 ✓

  决策现在**只有一条路**: RL(``platform/games/guandan_adapter.py::_decide_rl``)✓。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2
import numpy as np

ADB = ["adb", "-s", "127.0.0.1:5555"]

# 底部三个按钮(720x1280 实测): 提示 / 出牌 / 不出
BTN_HINT = (199, 1119)
BTN_PLAY = (359, 1119)
BTN_PASS = (519, 1119)

JIPAI = int(os.getenv("GUANDAN_JIPAI", "2"))  # 本局级牌(默认打2); 真值可用时以真值为准 ✓


def tap(x, y, wait=1.0):
    subprocess.run(ADB + ["shell", "input", "tap", str(x), str(y)], capture_output=True)
    time.sleep(wait)


def snap():
    r = subprocess.run(ADB + ["exec-out", "screencap", "-p"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    arr = np.frombuffer(r.stdout, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def gold_button(img):
    """找大金钮(开始游戏/再接一局): 金色块 w>250 h>50, y∈[600,1100]。返回中心或 None。"""
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    gold = ((r > 140) & (r < 215) & (g > 110) & (g < 185) & (b < 90)).astype(np.uint8) * 255
    n, lab, stats, cent = cv2.connectedComponentsWithStats(gold, 8)
    best = None
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if w > 250 and h > 50 and 600 <= y <= 1100:
            if best is None or a > best[4]:
                best = (x, y, w, h, a, int(cent[i][0]), int(cent[i][1]))
    return (best[5], best[6]) if best else None


def map_indices(hand, cards) -> list[int] | None:
    """把决策选中的 Card 列表映射回手牌(左→右)下标; 失败 None。"""
    used: set[int] = set()
    out: list[int] = []
    for c in cards:
        hit = None
        for i, h in enumerate(hand):
            if i in used:
                continue
            if h.zhi == c.zhi and (h.hua == c.hua or c.hua == 4 or h.hua == 4):
                hit = i
                break
        if hit is None:
            for i, h in enumerate(hand):
                if i not in used and h.zhi == c.zhi:
                    hit = i
                    break
        if hit is None:
            return None
        used.add(hit)
        out.append(hit)
    return sorted(out)


def main() -> int:
    """薄壳入口: 只有 platform 一条路(Runtime + GuandanAdapter ⇒ RL 决策 ✓)。"""
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    from ..config import load_config
    from ..platform.device import AdbDevice
    from ..platform.games.guandan_adapter import GuandanAdapter
    from ..platform.runtime import Runtime
    from ..vision.card_recognizer import CardRecognizer

    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    rec = CardRecognizer(load_config().vision)
    ad = GuandanAdapter()
    rt = Runtime(ad, dev, vision=rec, tag=os.getenv("STATS_TAG", "-"))
    print(f"▶ 掼蛋托管(platform 薄壳) 时长={dur}s ours={ad.ours}", flush=True)
    out = rt.run(seconds=dur)
    print(f"▶ 结束: {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
