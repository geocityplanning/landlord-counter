#!/usr/bin/env python3
"""视觉读牌准确率(对照游戏真值): "眼"准不准。

方法(关键在**同步**):
    ① 取真值 t1 → ② 抓帧 → ③ 再取真值 t2
    如果 t1.hands[0] != t2.hands[0] → 说明这中间有出牌/进牌 → 样本作废(避免错位误判 ✗)
    否则: 用视觉读这帧的手牌 → 与 t1.hands[0](点数多重集)比对
另外顺带量: 四家面板张数(视觉) vs 真值张数 ✓

用法: PYTHONPATH=src python3 tools/read_acc.py [样本数=15] [每样本最大重试=3]
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.config import load_config                       # noqa: E402
from landlord_counter.guandan import percept as P                      # noqa: E402
from landlord_counter.platform.cdp import CDP                          # noqa: E402
from landlord_counter.platform.device import AdbDevice                 # noqa: E402
from landlord_counter.vision.card_recognizer import CardRecognizer     # noqa: E402


def main() -> int:
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    tries = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    c = CDP()
    if not c.find_truth():
        print("✗ 没有真值钩子(需插桩版页面)")
        return 2
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    vis = CardRecognizer(load_config().vision)

    n = exact = cnt_ok = panel_ok = panel_n = 0
    cards_hit = cards_tot = 0          # 逐张口径: 读对的张数 / 应读的张数
    print(f"{'#':<4}{'真值':<26}{'视觉':<26}{'张数':<8}结果")
    print("-" * 88)
    for i in range(want):
        got = None
        for _try in range(tries):
            t1 = c.truth()
            if not t1 or t1.get("phase") != "playing":
                time.sleep(2)
                continue
            f = dev.snap()
            t2 = c.truth()
            if not t2 or (t1.get("hands", {}).get("0") != t2.get("hands", {}).get("0")):
                time.sleep(1.0)          # 中间有出牌 → 丢弃这轮
                continue
            got = (t1, f)
            break
        if not got:
            print(f"{i + 1:<4}(跳过: 画面在变动或不在牌局)")
            continue
        t1, f = got
        truth = sorted(int(x) for x in (t1.get("hands", {}).get("0") or []))
        if not truth:
            continue
        hand = P.read_hand_ordered(vis, f, expected=len(truth)) or []
        mine = sorted(getattr(x, "zhi", 0) for x in hand)
        n += 1
        same_n = (len(mine) == len(truth))
        cnt_ok += 1 if same_n else 0
        eq = (Counter(mine) == Counter(truth))
        cm, ct = Counter(mine), Counter(truth)
        cards_hit += sum(min(cm[k], ct[k]) for k in ct)      # 每个点数取两者的较小计数 = 命中
        cards_tot += max(len(truth), len(mine))
        exact += 1 if eq else 0
        ft = " ".join(map(str, truth))
        fm = " ".join(map(str, mine)) if mine else "(空)"
        res = "✓ 完全一致" if eq else ("✗ 牌面不同" if same_n else f"✗ 张数不同({len(mine)}≠{len(truth)})")
        print(f"{i + 1:<4}{ft:<26}{fm:<26}{('✓' if same_n else '✗'):<8}{res}")

        # 面板张数 vs 真值(顺带量)
        try:
            pan = P.read_seat_panels(vis, f)["panels"]
            th = t1.get("hands", {})
            for seat, idx in (("西", 1), ("北", 2), ("东", 3)):
                if seat in pan and pan[seat].get("left") is not None:
                    panel_n += 1
                    if int(pan[seat]["left"]) == len(th.get(str(idx), [])):
                        panel_ok += 1
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.2)

    print("-" * 88)
    if n:
        print(f"★ 视觉读牌 张数一致率: {cnt_ok}/{n} = {cnt_ok / n * 100:.0f}%")
        print(f"★ 视觉读牌 逐张完全一致率: {exact}/{n} = {exact / n * 100:.0f}%   ← '眼'的准确率")
    if cards_tot:
        print(f"★ 视觉读牌 **逐张准确率**: {cards_hit}/{cards_tot} = {cards_hit / cards_tot * 100:.1f}%   ← 这才是 99% 的口径")
    if panel_n:
        print(f"★ 座位面板张数一致率: {panel_ok}/{panel_n} = {panel_ok / panel_n * 100:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
