#!/usr/bin/env python3
"""直选执行链的**逐步真值探针**(仅实验室): 一格一格看直选卡在哪。

背景: P0-2 实测发现"我们自己点出去的牌"= 0 次 ✗ —— 全落回游戏提示兜底,
外面看着牌出得去, 实际不是我们点的。用真值通道把链路拆开看:
    ① 我们点牌 → 游戏 __truth().selected 变了吗?(选中了吗)
    ② 点"出牌" → __truth().plays 里出现我们的牌了吗?(登记了吗)
    ③ 没登记 → 看 toast 说什么 / 对比 selected 与我们的意图(是不是点偏/自动带同点数)

用法: PYTHONPATH=src python3 tools/direct_probe.py [试几张]
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.config import load_config                       # noqa: E402
from landlord_counter.guandan import percept as P                      # noqa: E402
from landlord_counter.platform import registry                         # noqa: E402
from landlord_counter.platform.cdp import CDP                          # noqa: E402
from landlord_counter.platform.device import AdbDevice                 # noqa: E402
from landlord_counter.vision.card_recognizer import CardRecognizer     # noqa: E402


def main() -> int:
    n_try = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    vis = CardRecognizer(load_config().vision)
    ad = registry.create("guandan")
    ad.attach(dev, vis)
    c = CDP()
    if not c.find_truth():
        print("✗ 没有真值钩子(需插桩版页面 + 带时间戳 URL 进桌)")
        return 2
    t0 = c.truth()
    print("【开局真值】phase:", t0.get("phase"), "| 当前出牌者:", t0.get("current"))
    hand_z = list(t0.get("hands", {}).get("0") or [])
    print("  我方手牌(真值)", len(hand_z), "张:", " ".join(map(str, sorted(hand_z))))
    if t0.get("current") != 0:
        print(f"✗ 现在不是我回合(当前 {t0.get('current')}) → 等一会再来")
        return 3

    frame = dev.snap()
    n_vis = P.hand_card_count_est(frame)
    hand = P.read_hand_strips_measured(vis, frame, n_vis) or P.read_hand_ordered(vis, frame, expected=n_vis)
    print("  我方手牌(视觉)", (len(hand) if hand else 0), "张:", "".join(str(x) for x in hand) if hand else "空")
    if not hand:
        print("✗ 读牌失败, 先不计")
        return 4

    ad._build_executor()
    ex = ad._ex
    # 挑一个"点数出现 2 次以上"的牌当目标(便于验证'自动带同点数')
    from collections import Counter
    cnt = Counter(getattr(x, "zhi", 0) for x in hand)
    zhi_sorted = sorted(cnt, key=lambda z: (cnt[z], z), reverse=True)
    tgt = zhi_sorted[0]
    idxs = [i for i, x in enumerate(hand) if getattr(x, "zhi", 0) == tgt][:1]
    print(f"\n① 决定打: 点数 {tgt} 的第 1 张 (手牌里同点数共 {cnt[tgt]} 张) → idx={idxs}")

    # 记录点牌前: 游戏认为选中了什么
    before = c.truth().get("selected") or []
    print("   点牌前 selected:", before)
    ok = ex.direct_play(idxs, len(hand), ranks=[getattr(hand[i], 'zhi', 0) for i in idxs])
    time.sleep(1.5)
    mid = c.truth()
    print(f"   点牌后 selected: {mid.get('selected')}  (点牌调用返回 {ok})")
    plays_before = len(mid.get("plays") or [])
    print("   ② 点'出牌'…")
    time.sleep(2.0)
    after = c.truth()
    plays_after = len(after.get("plays") or [])
    print(f"   出牌后 plays: {plays_before} → {plays_after}")
    if plays_after > plays_before:
        last = (after.get("plays") or [])[-1]
        print(f"   ✓ 游戏登记了我方出牌: seat={last.get('seat')} 点数={last.get('zhi')}")
    else:
        try:
            print("   ✗ 没有登记; toast:", repr(c.toast()))
        except Exception as e:  # noqa: BLE001
            print("   ✗ 没有登记; toast 读取失败", e)
    print("   手牌(真值)剩:", len(after.get("hands", {}).get("0") or []), "张")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
