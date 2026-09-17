#!/usr/bin/env python3
"""决策 → 索引 → **这张索引在我读到的序列里是哪张牌** —— 直接抓"点错"的根 ✓

用户 2026-09-17 观察: 决策不是大牌, 却点出了 KK ⇒ 高度怀疑**索引与牌序对不上**
  (若决策层的"手牌顺序"与视觉读出的顺序不一致 ⇒ 索引被镜像/错位 ⇒ 点到的永远是别的牌)

用法: PYTHONPATH=src python3 tools/check_index_map.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402
from landlord_counter.platform.registry import create      # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
SUIT = {1: "♠", 2: "♣", 3: "♥", 4: "♦", 0: "?"}


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    ad = create("guandan")
    ad.attach(dev)
    t = c.truth() or {}
    print(f"真值: 轮到={t.get('current')} 手牌={len((t.get('hands') or {}).get('0') or [])}张 "
          f"selected={t.get('selected')}")

    f = dev.snap()
    y0, y1 = P.hand_band_measured(f)
    cards, _i = P.tm_read_hand(f)
    print(f"\n我读到的序列(左→右 {len(cards)} 张):")
    print("  " + " ".join(f"{i}:{SUIT.get(s, '')}{NAME.get(r, r)}" for i, (s, r, _x, _l) in enumerate(cards)))
    truth_zhi = (t.get("hands") or {}).get("0") or []
    print("  真值(同序): " + " ".join(f"{i}:{NAME.get(z, z)}" for i, z in enumerate(truth_zhi)))

    # 让适配器自己算一遍决策, 拿到它要出的牌 + 索引
    st = ad.sense(f)
    print(f"\n感知: my_turn={getattr(st, 'my_turn', None)} hand={len(getattr(st, 'hand', []) or [])}张")
    act = ad.decide(st)
    combo = getattr(act, "combo", None)
    print(f"决策: {act}")
    if combo is not None:
        want = [(getattr(x, 'suit', 0), getattr(x, 'rank', 0)) for x in (combo.cards if hasattr(combo, 'cards') else [])]
        _txt = [SUIT.get(s, "?") + str(NAME.get(r, r)) for s, r in want]
        print(f"  要出的牌: {_txt}")
        # 在**我读到的序列**里找这些牌 → 应该给出与决策相同的索引
        idxs = []
        for s_, r_ in want:
            for i, (s2, r2, _x, _l) in enumerate(cards):
                if r2 == r_ and (s_ in (0, s2) or s2 == 0):
                    idxs.append(i)
                    break
        print(f"  按我的序列, 这些牌在: {idxs}")
        for i in idxs:
            if i < len(cards):
                print(f"    索引{i} → x={cards[i][2]} → 我读作 {SUIT.get(cards[i][0], '')}{NAME.get(cards[i][1], cards[i][1])}")
        for i in idxs:                      # 也报一下真值那一张是什么(核对身份)
            if i < len(truth_zhi):
                print(f"    索引{i} 的真值点数 = {NAME.get(truth_zhi[i], truth_zhi[i])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
