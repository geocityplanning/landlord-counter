#!/usr/bin/env python3
"""**人工托管的"手"**: 按用户报的编号点牌 → 用游戏真值校验选中 → 出图。

用户 2026-09-18: "要不你给我手动控制出牌, 然后你截图"
用法:
  python3 tools/manual_tap.py 26 27          # 点第 26、27 号(1 起)
  python3 tools/manual_tap.py --play 26 27   # 点完确认无误再按"出牌"
  python3 tools/manual_tap.py --clear        # 清掉桌上已有的选中(精确回落)

要点(都是踩出来的):
  · 点击 x = 牌位 + 6px(点在牌的**左缘**上会被游戏判给左边那张 ✗)
  · **每点一张前重新实量牌位**(点完牌面会变, 上一轮的 x 会过期)
  · 校验只认**游戏真值** selected, 不认"看起来抬起了"
"""
from __future__ import annotations

import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L          # noqa: E402
from landlord_counter.platform.cdp import CDP             # noqa: E402
from landlord_counter.platform.device import AdbDevice    # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch   # noqa: E402

OUT = "/tmp/manual.png"
BAND = (790, 950)
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def nm(v: int) -> str:
    return NAME.get(v, str(v))


def shot(dev, c, mt, note: str = "") -> tuple:
    """截一张"给用户看"的图: 整屏 + 手牌放大 + 编号 + 选中标记 ✓"""
    t = c.truth() or {}
    hand = [int(v) for v in ((t.get("hands") or {}).get("0") or [])]
    ids = list(t.get("handIds") or [])
    sel = set(int(v) for v in (t.get("selected") or []))
    img = dev.snap()
    g = L.geom()
    slots, _ = L.locate(img, len(hand))
    pos_sel = {i for i, i_ in enumerate(ids) if i_ in sel}      # 选中的是第几位(0 起)
    pb = L.play_button(img)

    full = img.copy()
    for i, x in enumerate(slots):
        x0 = int(x)
        col = (0, 0, 255) if i in pos_sel else (0, 255, 0)
        cv2.line(full, (x0, BAND[0]), (x0, BAND[1]), col, 2 if i in pos_sel else 1)
        cv2.putText(full, str(i + 1), (x0, BAND[0] - 6), cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (0, 255, 255), 1)
    if pb:
        cv2.circle(full, (int(pb[0]), int(pb[1])), 22, (255, 0, 255), 2)
    band = cv2.resize(img[BAND[0] - 25:BAND[1]], None, fx=2.5, fy=2.5,
                      interpolation=cv2.INTER_NEAREST)
    for i, x in enumerate(slots):
        xb = int(int(x) * 2.5)
        col = (0, 0, 255) if i in pos_sel else (0, 255, 0)
        cv2.line(band, (xb, 0), (xb, band.shape[0]), col, 2 if i in pos_sel else 1)
        cv2.putText(band, str(i + 1), (xb + 3, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 255), 2)
    sel_txt = " ".join(f"#{i + 1}({nm(hand[i])})" for i in sorted(pos_sel)) or "无"
    hdr = (f"turn={'ME' if t.get('current') == 0 else t.get('current')}  cards={len(hand)}  "
           f"selected={len(sel)}  [{sel_txt}]")
    if note:
        hdr = note + " | " + hdr
    head = np.full((34, max(full.shape[1], band.shape[1]), 3), 20, np.uint8)
    cv2.putText(head, hdr, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                (0, 255, 255) if sel else (255, 255, 255), 1)
    bank = np.full((30, max(full.shape[1], band.shape[1]), 3), 20, np.uint8)
    cv2.putText(bank, "truth: " + " ".join(nm(v) for v in hand), (6, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    W = max(full.shape[1], band.shape[1])
    sep = np.full((6, W, 3), 40, np.uint8)
    def pad(p):
        return p if p.shape[1] == W else np.pad(p, ((0, 0), (0, W - p.shape[1]), (0, 0)))
    cv2.imwrite(OUT, np.vstack([pad(p) for p in (head, full, sep, band, sep, bank)]))
    return hand, ids, sel, pos_sel


def tap_one(dev, c, mt, idx0: int) -> bool:
    """点第 idx0(0 起) 张 —— 点前重新实量牌位 ✓"""
    t = c.truth() or {}
    hand = [int(v) for v in ((t.get("hands") or {}).get("0") or [])]
    img = dev.snap()
    slots, _ = L.locate(img, len(hand))
    if idx0 >= len(slots):
        print(f"✗ 第 {idx0 + 1} 号越界(当前 {len(slots)} 位)")
        return False
    x = int(slots[idx0])
    mt.tap(x + 6, L.geom().hand_y())          # ★ +6px: 点在左缘上会被判给左邻 ✗
    return True


def main() -> int:
    args = [a for a in sys.argv[1:]]
    do_play = "--play" in args
    do_clear = "--clear" in args
    nums = [int(a) for a in args if a.isdigit()]

    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()

    if do_clear:
        t = c.truth() or {}
        ids = list(t.get("handIds") or [])
        sel = list(t.get("selected") or [])
        for sid in sel:
            if sid in ids:
                tap_one(dev, c, mt, ids.index(sid))
                time.sleep(0.45)
        time.sleep(0.8)
        hand, _i, s2, _p = shot(dev, c, mt, "清理后")
        print(f"✓ 清理: {len(sel)} → selected={len(s2)}")
        return 0

    for n in nums:
        ok = tap_one(dev, c, mt, n - 1)
        print(f"  点第 {n} 号 {'✓' if ok else '✗'}")
        time.sleep(0.55)

    time.sleep(0.9)
    hand, ids, sel, pos_sel = shot(dev, c, mt, f"点了 {' '.join(str(n) for n in nums)}")
    want = [nm(hand[n - 1]) for n in nums if 0 < n <= len(hand)]
    got = [nm(hand[i]) for i in sorted(pos_sel)]
    print(f"✓ 你想出: {' '.join(want)} | 游戏实际选中: {' '.join(got) or '无'} "
          f"| {'✓ 一致' if want == got else '✗ 不一致'}")

    if do_play and want == got and got:
        pb = L.play_button(dev.snap())
        mt.tap(int(pb[0]), int(pb[1]))
        time.sleep(1.6)
        hand2, _i, _s, _p = shot(dev, c, mt, "出牌后")
        print(f"✓ 已按出牌 | 手牌 {len(hand)} → {len(hand2)}"
              f" | {'✓ 打出去了' if len(hand2) < len(hand) else '✗ 没打出去'}")
    print(f"图: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
