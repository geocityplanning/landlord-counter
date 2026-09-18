#!/usr/bin/env python3
"""**人工托管模式**的画面工具(2026-09-18 用户要求)。

用户原话: "你现在出牌点击不太准, 要不你给我手动控制出牌, 然后你截图"
⇒ 分工: 用户看牌/决定打哪张(报"第几号"或"出X") → 我按号码点(走已验证的路径) → 我截图回话

本工具输出一张图:
  上 = 整屏(带出牌按钮标记)
  中 = 手牌带放大 2.5 倍 + **每张编号**(用户直接报编号 ✓)
  下 = 游戏真值(我的手牌点数, 供核对"我看到的和你看到的是不是一样")

用法: python3 tools/manual_view.py [--out /tmp/manual.png]
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L          # noqa: E402
from landlord_counter.platform.cdp import CDP             # noqa: E402
from landlord_counter.platform.device import AdbDevice    # noqa: E402

SCALE = 2.5
BAND = (790, 950)          # 手牌及上方一点(复核用 ✓)


def name_of(v: int) -> str:
    return {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}.get(v, str(v))


def main() -> int:
    out = "/tmp/manual.png"
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]

    from manual_tap import wait_stable           # 同一份实现 ✓(别再写第二套 ✗)

    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    wait_stable(dev)
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    hand = [int(v) for v in ((t.get("hands") or {}).get("0") or [])]
    n = len(hand)
    img = dev.snap()
    g = L.geom()
    slots, chk = L.locate(img, n)
    pb = L.play_button(img)

    full = img.copy()
    for i, x in enumerate(slots):
        x0 = int(x)
        cv2.line(full, (x0, BAND[0]), (x0, BAND[1]), (0, 255, 0), 1)
        cv2.putText(full, str(i + 1), (x0, BAND[0] - 6), cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (0, 255, 255), 1)
    if pb:
        cv2.circle(full, (int(pb[0]), int(pb[1])), 22, (255, 0, 255), 2)
        cv2.putText(full, "PLAY", (int(pb[0]) - 22, int(pb[1]) - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

    band = cv2.resize(img[BAND[0] - 25:BAND[1]], None, fx=SCALE, fy=SCALE,
                      interpolation=cv2.INTER_NEAREST)
    for i, x in enumerate(slots):
        xb = int(int(x) * SCALE)
        cv2.line(band, (xb, 0), (xb, band.shape[0]), (0, 255, 0), 1)
        cv2.putText(band, str(i + 1), (xb + 3, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 255, 255), 2)

    hdr = f"turn={'ME' if t.get('current') == 0 else t.get('current')}  cards={n}  " \
          f"slots={len(slots)}{'' if chk.ok else ' (!!zheng-du) '}"
    # 各家剩几张 + 上一手(末局的决策全靠它 ✓; 用户 2026-09-18: 把这一局打完, 各种情况都碰一遍)
    hands_all = t.get("hands") or {}
    seat_txt = "  ".join(
        f"{'我' if k == '0' else '席' + k}:{len(hands_all.get(k) or [])}"
        for k in ("0", "1", "2", "3"))
    plays = t.get("plays") or []
    last = plays[-1] if isinstance(plays, list) and plays else None
    last_txt = ""
    if last:
        zz = [name_of(int(v)) for v in (last.get("zhi") or [])]
        last_txt = f"  上一手: 席{last.get('seat')} 出 {' '.join(zz)}"
    hdr = hdr + "   |   " + seat_txt + last_txt
    head = np.full((34, max(full.shape[1], band.shape[1]), 3), 20, np.uint8)
    cv2.putText(head, hdr, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    W = max(full.shape[1], band.shape[1])
    sep = np.full((6, W, 3), 40, np.uint8)
    bank = np.full((30, W, 3), 20, np.uint8)
    cv2.putText(bank, "game truth (我的牌): " + " ".join(name_of(v) for v in hand),
                (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    parts = [head, full, sep, band, sep, bank]
    out_img = np.vstack([p if p.shape[1] == W else np.pad(
        p, ((0, 0), (0, W - p.shape[1]), (0, 0))) for p in parts])
    cv2.imwrite(out, out_img)
    print(f"✓ {out} | 轮到={t.get('current')} 手牌 {n} 张 | 牌位 {len(slots)} | 按钮 {pb}")
    print("  我的牌: " + " ".join(name_of(v) for v in hand))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
