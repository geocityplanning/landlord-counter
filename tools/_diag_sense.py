#!/usr/bin/env python3
"""直接调适配器的 sense(), 看它为什么判"不是我回合"(0 动作)。

用法: PYTHONPATH=src python3 tools/_diag_sense.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P            # noqa: E402
from landlord_counter.platform import registry              # noqa: E402
from landlord_counter.platform.device import AdbDevice      # noqa: E402

dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
f = dev.snap()
ad = registry.create("guandan")
print("my_turn(像素):", P.my_turn(f))
print("_band_looks_like_hand:", ad._band_looks_like_hand(f))
print("hand_is_real:", P.hand_is_real(f))
print("card_slots:", P.card_slots(f))
print("tm_read_hand:", P.tm_read_hand(f)[0])
print("_ex:", getattr(ad, "_ex", None))
ex = getattr(ad, "_ex", None)
if ex is not None:
    print("  ex.cdp:", getattr(ex, "cdp", None))
    if getattr(ex, "cdp", None) is not None:
        try:
            print("  our_turn_probe:", ex.cdp.our_turn_probe(ex.L.btn_play))
        except Exception as e:  # noqa: BLE001
            print("  our_turn_probe 异常:", type(e).__name__, e)
obs = ad.sense(f)
print(f"sense → my_turn={obs.my_turn} hand={obs.hand} extra={obs.extra}")
