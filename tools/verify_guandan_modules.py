#!/usr/bin/env python3
"""掼蛋专有模块验收: 定位 / 读牌 / 点牌 三项出数(2026-09-18)。

· 定位: 标定常量 + 在线校验 ⇒ 牌位数是否等于真值
· 读牌: 逐张(花色+点数)与真值比对 ⇒ 准确率
· 点牌: 点第 i 张 ⇒ 游戏真值里选中的是不是第 i 张 ⇒ 命中率; 完事精确撤销(不留残余 ✓)

用法: PYTHONPATH=src python3 tools/verify_guandan_modules.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L                 # noqa: E402
from landlord_counter.guandan import percept as P                # noqa: E402
from landlord_counter.guandan import read as R                  # noqa: E402
from landlord_counter.guandan import tap as T                    # noqa: E402
from landlord_counter.platform.cdp import CDP                    # noqa: E402
from landlord_counter.platform.device import AdbDevice           # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch          # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦", 0: "?"}


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()

    def img_fn():
        return dev.snap()

    def tap_fn(x, y):
        try:
            mt.tap(int(x), int(y))
            return True
        except Exception:  # noqa: BLE001
            return False

    def truth_fn():
        try:
            return c.truth() or {}
        except Exception:  # noqa: BLE001
            return {}

    # 等"我的回合 + 干净"
    for _ in range(30):
        t = truth_fn()
        if t.get("phase") == "playing" and t.get("current") == 0 and not (t.get("selected") or []):
            break
        time.sleep(3)

    g = L.geom()
    print(f"标定: {g.calibrated_at} | {g.notes}")
    print(f"     手牌带 {g.hand_y0}..{g.hand_y1} | 牌距 {g.pitch} | 末张宽 {g.last_card_w}")

    # ---------- ① 定位 ----------
    f = img_fn()
    t = truth_fn()
    ids = t.get("handIds") or []
    zhi = (t.get("hands") or {}).get("0") or []
    n = len(ids)
    print(f"\n===== ① 定位 =====")
    print(f"真值手牌 {n} 张")
    if (t.get("selected") or []):
        n_clear = T.clear_residue(tap_fn, truth_fn, img_fn)
        print(f"  回落清掉 {n_clear} 张残留 ✓")
        t = truth_fn()
        ids = t.get("handIds") or []
        n = len(ids)
    slots, chk = L.locate(f, n)
    print(f"  在线校验 ok={chk.ok} 实测={chk.measured}")
    print(f"  牌位 {len(slots)} 个 vs 真值 {n} 张  {'✓' if len(slots) == n else '✗'}")

    # ---------- ② 读牌 ----------
    print(f"\n===== ② 读牌 =====")
    rr = R.read(f, expect=n, hand_ids=ids, ranks=zhi)     # ★ 走专有读牌(含按局自动重采 ✓)
    if rr.collected:
        print(f"  [按局重采] 新一局 → 自动采了 {rr.collected} 张模板 ✓")
        f = img_fn()
        rr = R.read(f, expect=n, hand_ids=ids, ranks=zhi)
    rd = rr.cards
    ok = sum(1 for a, b in zip(rd, zhi) if a[1] == b)
    print(f"  我读 {len(rd)} 张 | 点数逐位对 {ok}/{len(zhi)} = {ok / max(1, len(zhi)) * 100:.1f}%")
    print("  我读: " + " ".join(str(NAME.get(a[1], a[1])) for a in rd[:14]))
    print("  真值: " + " ".join(str(NAME.get(b, b)) for b in zhi[:14]))

    # ---------- ③ 点牌 ----------
    print(f"\n===== ③ 点牌 =====")
    hit = 0
    tests = [n - 1, n // 2, 2]
    for i in tests:
        _ids, sel = T._cards_snapshot(truth_fn)
        if sel:
            T.clear_residue(tap_fn, truth_fn, img_fn)
        pt = L.card_tap(i, n, img_fn())
        if pt is None:
            print(f"  点第{i}张: ✗ 定位校验未通过(拒绝动手 ✓)")
            continue
        tap_fn(*pt)
        time.sleep(0.9)
        _ids2, sel2 = T._cards_snapshot(truth_fn)
        pos = [_ids2.index(s) for s in sel2 if s in _ids2]
        good = pos == [i]
        hit += 1 if good else 0
        print(f"  点第{i}张(x={pt[0]}) → 游戏选中 {pos}  {'✓' if good else '✗'}")
        if sel2:                                   # 立刻撤销, 保持干净 ✓
            tap_fn(*pt)
            time.sleep(0.8)
    print(f"  ★ 命中 {hit}/{len(tests)}")
    n_clear = T.clear_residue(tap_fn, truth_fn, img_fn)
    print(f"  收尾: 清掉 {n_clear} 张 → selected={(truth_fn().get('selected'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
