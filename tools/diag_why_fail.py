#!/usr/bin/env python3
"""归因诊断(用户设计第⑥步): 选牌→出牌→读游戏 toast, 分清是①还是②。

  ① 决策不合规(游戏规则不认我们挑的牌) → toast 会说"不能出/管不上/牌型不符"之类
  ② 操作错(按钮没点中/选中集不对)      → toast 通常为空, 而手牌张数也没变

用法: GUANDAN_OURS=1 GUANDAN_DECIDE=rl PYTHONPATH=src python3 tools/diag_why_fail.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import rules as R            # noqa: E402
from landlord_counter.platform import registry            # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    ad = registry.create("guandan")
    try:
        from landlord_counter.config import load_config
        from landlord_counter.vision.card_recognizer import CardRecognizer

        vision = CardRecognizer(load_config().vision)
    except Exception as e:  # noqa: BLE001
        print(f"(识别器不可用 {type(e).__name__} → vision=None)")
        vision = None
    ad.attach(dev, vision=vision)

    t = c.truth() or {}
    print(f"真值: 阶段={t.get('phase')} 轮到={t.get('current')} "
          f"我的手牌={len((t.get('hands') or {}).get('0') or [])}张 selected={t.get('selected')}")
    f = dev.snap()
    obs = ad.sense(f)
    print(f"感知: my_turn={obs.my_turn} hand={len(obs.hand or [])}张 table={obs.table}")
    if not obs.my_turn or not obs.hand:
        print("→ 现在不是我方可决策的时刻, 稍后再跑")
        return 0
    act = ad.decide(obs)
    combo = getattr(act, "combo", None)
    print(f"决策: kind={act.kind} why={act.meta.get('why')} combo={combo}")
    if combo is not None:
        print(f"  组合: {[str(x) for x in combo.cards]} 牌型={getattr(combo, 'name', '?')}")
    # 合法性自检(用我们自己的规则库): 与桌面牌比, 我们这套能不能压
    tbl = obs.table or []
    if tbl:
        last = R.identify(tbl, 1)         # 级牌先用 1 试(只做形态判断)
        print(f"  桌上牌型: {getattr(last, 'name', '?')} | 我方牌型: {getattr(combo, 'name', '?')}")
    t0 = c.truth() or {}
    hand_before = len((t0.get("hands") or {}).get("0") or [])
    res = ad.execute(act, obs)
    print(f"执行: ok={res.ok} retries={res.retries} msg={res.detail}")
    time.sleep(1.0)
    t1 = c.truth() or {}
    hand_after = len((t1.get("hands") or {}).get("0") or [])
    print(f"★ 手牌: {hand_before} → {hand_after} 张  ({'✓ 真打出去了' if hand_after < hand_before else '✗ 没打出去'})")
    try:
        print(f"★ 游戏 toast: {ad._ex.cdp.toast()!r}")
    except Exception as e:  # noqa: BLE001
        print(f"(toast 读取失败 {type(e).__name__})")
    print(f"★ selected: {t1.get('selected')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
