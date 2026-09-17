#!/usr/bin/env python3
"""打印一条决策的完整链路: AI想打什么 → 映射到手牌索引 → 映射到屏幕坐标 → 合法性自检。

用来回答"决策要出的到底是哪张/为什么点出来是那几张" ✓

用法: GUANDAN_OURS=1 GUANDAN_DECIDE=rl PYTHONPATH=src python3 tools/diag_decide_map.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import rules as R            # noqa: E402
from landlord_counter.platform import registry            # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402
from landlord_counter.platform.games.guandan_adapter import _map_indices   # noqa: E402


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    ad = registry.create("guandan")
    try:
        from landlord_counter.config import load_config
        from landlord_counter.vision.card_recognizer import CardRecognizer

        ad.attach(dev, vision=CardRecognizer(load_config().vision))
    except Exception:  # noqa: BLE001
        ad.attach(dev, vision=None)
    from landlord_counter.guandan.agent import JIPAI as jipai

    t = c.truth() or {}
    print(f"真值: 轮到={t.get('current')} 我的手牌={len((t.get('hands') or {}).get('0') or [])}张 "
          f"selected={t.get('selected')}")
    f = dev.snap()
    obs = ad.sense(f)
    if not obs.my_turn or not obs.hand:
        print(f"→ 现在不是可决策时刻(my_turn={obs.my_turn} hand={len(obs.hand or [])})")
        return 0
    hand = obs.hand
    n = len(hand)
    print("① 我读到的整手(左→右):", [str(x) for x in hand])
    print("   桌上牌:", [str(x) for x in (obs.table or [])], "| 级牌 JIPAI =", jipai)
    act = ad.decide(obs)
    combo = getattr(act, "combo", None)
    print(f"② 决策: kind={act.kind} why={act.meta.get('why')}")
    if combo is None:
        print("   (没给组合)")
        return 0
    print("   想打的牌(combo.cards):", [str(x) for x in combo.cards])
    if not combo.is_invalid:
        print(f"   牌型: {combo.name}")
    else:
        print("   ⚠ 牌型: **非法** ✗")
    idxs = _map_indices(hand, combo.cards)
    print("③ 映射到手牌索引:", idxs)
    if idxs:
        print("   这些索引上的牌:", [str(hand[i]) for i in idxs if 0 <= i < n])
        try:
            xs = [ad._ex._pos(i, n) for i in idxs]
            print("   对应屏幕 x 坐标:", xs)
        except Exception as e:  # noqa: BLE001
            print(f"   (取坐标失败 {type(e).__name__})")
    # 自检
    try:
        g = R.identify(list(combo.cards), jipai)
        print(f"④ 自检: 牌型={getattr(g, 'name', '?')} 非法={getattr(g, 'is_invalid', '?')}", end="")
        if obs.table:
            last = R.identify(list(obs.table), jipai)
            print(f" | 能否压过桌上({getattr(last, 'name', '?')}) = {R.can_beat(g, last)}")
        else:
            print(" | (我方领出)")
    except Exception as e:  # noqa: BLE001
        print(f"   (自检异常 {type(e).__name__}: {e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
