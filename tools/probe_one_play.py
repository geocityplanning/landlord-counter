#!/usr/bin/env python3
"""最干净的单次实验: 等我的回合 → 选**一张** → 按出牌(实测按钮) → 读游戏判决(toast) + 真值。

目的(2026-09-17): 把"选一张再出牌"这条最小路径单独跑一次, 看游戏到底说什么 ——
  toast='无效的牌型组合'  ⇒ 决策/牌型问题
  toast='请选择要出的牌'  ⇒ 没选中(选中集为空)
  toast 静默且手牌不减    ⇒ 要么不是我们回合, 要么按的位置不对

用法: PYTHONPATH=src python3 tools/probe_one_play.py [要选的位号, 默认26]
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch    # noqa: E402


def play_btn(img):
    """出牌按钮: 底部三段里**最亮**的那段(实测 2026-09-17)"""
    y_a, y_b = 1078, 1148
    band = img[y_a:y_b]
    if band.size == 0:
        return None
    g = band[:, :, 1].astype(int)
    ng = ~((g > band[:, :, 2].astype(int) + 12) & (g > band[:, :, 0].astype(int) + 12))
    col = ng.mean(axis=0)
    runs, s = [], None
    for x, v in enumerate(col):
        if v > 0.6 and s is None:
            s = x
        elif v <= 0.6 and s is not None:
            if x - s > 25:
                runs.append((s, x))
            s = None
    if s is not None and len(col) - s > 25:
        runs.append((s, len(col)))
    if len(runs) < 3:
        return None
    lo, hi = max(runs, key=lambda ab: band[:, ab[0]:ab[1]].mean())
    return ((lo + hi) // 2, (y_a + y_b) // 2)


def main() -> int:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 26
    c = CDP()
    c.find_truth()
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()

    # 等我的回合(最多 120s)
    for _ in range(40):
        t = c.truth() or {}
        if t.get("phase") == "playing" and t.get("current") == 0 and not (t.get("selected") or []):
            break
        time.sleep(3)
    t0 = c.truth() or {}
    n0 = len((t0.get("hands") or {}).get("0") or [])
    print(f"开局: 轮到={t0.get('current')} 手牌={n0}张 selected={t0.get('selected')} toast=[{c.toast()}]")

    img = dev.snap()
    y0, y1 = P.hand_band_measured(img)
    cards, _i = P.tm_read_hand_with_lift(img)
    if idx >= len(cards):
        print(f"✗ 位号 {idx} 超出(共 {len(cards)} 位)")
        return 0
    x = cards[idx][2]
    y = (y0 + y1) // 2
    print(f"选第{idx}张: x={x} y={y} (读作点数 {cards[idx][1]})")
    mt.tap(x, y)
    time.sleep(0.9)
    t1 = c.truth() or {}
    print(f"选后: selected={t1.get('selected')}  ({len(t1.get('selected') or [])} 张)")

    pb = play_btn(dev.snap())
    print(f"出牌按钮 = {pb}")
    if pb:
        mt.tap(pb[0], pb[1])
        time.sleep(2.2)
        t2 = c.truth() or {}
        n2 = len((t2.get("hands") or {}).get("0") or [])
        print(f"按后: 手牌={n2}张 selected={t2.get('selected')} toast=[{c.toast()}]")
        print("结论:", "✓✓ 打出去了!" if n2 < n0 else f"✗ 没打出去 (游戏判决见上 toast)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
