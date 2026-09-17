#!/usr/bin/env python3
"""读 / 点 / 验证 —— 三项一次跑完的干净验证(用户 2026-09-17 指定重点)。

① 读: 适配器 sense(含换局自动采模板) → 我读的逐位 vs 游戏真值 ⇒ 准确率
② 点: 点第 i 个牌位 → 游戏真值里被选中的是不是第 i 张 ⇒ 命中率; 再点一次撤销(保持干净)
③ 验证: 伺服选牌 → 按出牌 → 手牌是否真的减少(= 结果验收)

每一项都只信**游戏真值**(实验室里它才是裁判 ✓), 打印成一张表 ✓
用法: PYTHONPATH=src python3 tools/verify_read_tap_play.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P               # noqa: E402
from landlord_counter.platform.cdp import CDP                   # noqa: E402
from landlord_counter.platform.device import AdbDevice          # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch         # noqa: E402
from landlord_counter.platform.registry import create           # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦", 0: "?"}


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()
    ad = create("guandan")
    ad.attach(dev)
    try:
        ad._ex.cdp = c                       # 真值通道(实验室裁判) ✓
    except Exception:  # noqa: BLE001
        pass

    # 等我的回合
    for _ in range(30):
        t = c.truth() or {}
        if t.get("phase") == "playing" and t.get("current") == 0:
            break
        time.sleep(3)

    print("\n========== ① 读 ==========")
    frame = dev.snap()
    st = ad.sense(frame)                     # 走生产路径(含自动采模板 ✓)
    obs_hand = list(getattr(st, "hand", None) or [])
    t = c.truth() or {}
    zhi = (t.get("hands") or {}).get("0") or []
    mytxt = [SUIT.get(getattr(h, "hua", 0) or 0, "?") + str(NAME.get(getattr(h, "zhi", 0), getattr(h, "zhi", 0)))
             for h in obs_hand]
    ttxt = [str(NAME.get(z, z)) for z in zhi]
    ok = sum(1 for a, b in zip(obs_hand, zhi) if getattr(a, "zhi", None) == b)
    print(f"真值 {len(zhi)} 张 | 我读 {len(obs_hand)} 张 | **点数逐位对 {ok}/{len(zhi)}**"
          f" = {ok / max(1, len(zhi)) * 100:.1f}%")
    print("  我读: " + " ".join(mytxt[:14]) + (" …" if len(mytxt) > 14 else ""))
    print("  真值: " + " ".join(ttxt[:14]) + (" …" if len(ttxt) > 14 else ""))

    print("\n========== ② 点 ==========")
    cards, _i = P.tm_read_hand(frame)
    y0, y1 = P.hand_band_measured(frame)
    y = (y0 + y1) // 2
    tests = [len(cards) - 1, len(cards) // 2, 0]
    hit = 0
    for i in tests:
        if not (0 <= i < len(cards)):
            continue
        ids = (c.truth() or {}).get("handIds") or []
        if (c.truth() or {}).get("selected"):
            print("  (牌桌有残留 → 先跳过, 由③的撤销负责清)")
            break
        x = cards[i][2]
        mt.tap(x, y)
        time.sleep(0.9)
        sel = (c.truth() or {}).get("selIds") or []
        pos = [ids.index(s) for s in sel if s in ids]
        good = pos == [i]
        hit += 1 if good else 0
        print(f"  点第{i}位(x={x}) → 游戏选中 {pos}  {'✓' if good else '✗'}")
        if sel:                               # 点回去(保持干净 ✓)
            mt.tap(x, y)
            time.sleep(0.8)
    print(f"  **命中 {hit}/{len(tests)}**")

    print("\n========== ③ 验证(出牌) ==========")
    t0 = c.truth() or {}
    n0 = len((t0.get("hands") or {}).get("0") or [])
    print(f"  出牌前: 手牌 {n0} 张 | selected={(t0.get('selected'))}")
    os.environ["GUANDAN_OURS"] = "1"
    ad.ours = True
    st = ad.sense(dev.snap())
    act = ad.decide(st)
    print(f"  决策: {act}")
    try:
        res = ad.execute(act, st)
        print(f"  执行: ok={res.ok} retries={getattr(res, 'retries', '?')} msg={res.detail}")
    except Exception as e:  # noqa: BLE001
        print(f"  执行异常: {type(e).__name__}: {e}")
    time.sleep(1.5)
    t1 = c.truth() or {}
    n1 = len((t1.get("hands") or {}).get("0") or [])
    print(f"  出牌后: 手牌 {n1} 张 | selected={(t1.get('selected'))} | toast=[{c.toast()}]")
    print(f"  **结果: {'✓✓ 手牌减少 ⇒ 真打出去了' if n1 < n0 else '✗ 手牌没减'}**  ({n0}→{n1})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
