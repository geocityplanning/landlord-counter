#!/usr/bin/env python3
"""只画**读错的牌位**的裁切条 + 它匹配到的模板 —— 一眼看出"为什么认错" ✓

对每个读错的位: 左边=现场裁的条, 右边=被选中的模板(并列出前 3 名键与距离) ✓
输出: data/shots/wrong_slots.png
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import locate as L            # noqa: E402
from landlord_counter.guandan import percept as P           # noqa: E402
from landlord_counter.guandan import read as R              # noqa: E402
from landlord_counter.platform.cdp import CDP               # noqa: E402
from landlord_counter.platform.device import AdbDevice      # noqa: E402

NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}
OUT = "data/shots/wrong_slots.png"


def main() -> int:
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    t = c.truth() or {}
    zhi = (t.get("hands") or {}).get("0") or []
    n = len(zhi)
    f = dev.snap()
    g = L.geom()
    slots, _chk = L.locate(f, n)
    rr = R.read(f, expect=n, hand_ids=t.get("handIds"), ranks=zhi)
    f = dev.snap()                       # 采集后重取一帧(与读数同刻更好)
    rr = R.read(f, expect=n, hand_ids=t.get("handIds"), ranks=zhi)
    bank = P.load_templates_sr()
    y0, card_h = g.hand_y0, g.hand_y1 - g.hand_y0 - 16

    rows = []
    for i, x in enumerate(slots):
        x0 = int(x)
        my = rr.cards[i][1] if i < len(rr.cards) else 0
        tr = zhi[i] if i < len(zhi) else 0
        if my == tr:
            continue
        # 现场裁切条(带上方 40px, 便于看干扰 ✓)
        ctx = f[max(0, y0 - 40):g.hand_y1, x0:x0 + 24]
        # 前 3 名模板
        items = [(k, t2) for k, arrs in bank.items() for t2 in arrs]
        items.sort(key=lambda kt: 0 if "_auto_" in kt[0] else 1)
        ds = []
        for k, t2 in items:
            dy, d = P.slide_best(f, x0, y0, t2, win_up=0)
            if dy is not None:
                ds.append((d, k, t2))
        ds.sort(key=lambda z: z[0])
        row = []
        SC = 3
        big = cv2.resize(ctx, (24 * SC, ctx.shape[0] * SC), interpolation=cv2.INTER_NEAREST)
        cv2.putText(big, f"#{i}", (2, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(big, f"read {NAME.get(my, my)}", (2, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
        cv2.putText(big, f"truth {NAME.get(tr, tr)}", (2, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        row.append(big)
        for d, k, t2 in ds[:2]:                       # 前 2 名模板
            tb = t2[:, :24]
            bt = cv2.resize(tb, (24 * SC, tb.shape[0] * SC), interpolation=cv2.INTER_NEAREST)
            lab = f"{k} {d:.3f}"
            cv2.putText(bt, lab, (1, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 0), 1)
            row.append(bt)
        hh = max(r.shape[0] for r in row)          # ★ 高度补齐(裁切条高度不一 ✗)
        row = [np.pad(r, ((0, hh - r.shape[0]), (0, 0), (0, 0)), constant_values=25) for r in row]
        gap = np.full((hh, 6, 3), 40, np.uint8)
        merged = []
        for r in row:
            merged.append(r)
            merged.append(gap)
        merged.pop()
        rows.append(np.hstack(merged))
    if not rows:
        print("✓ 没有读错的牌位")
        return 0
    W = max(r.shape[1] for r in rows)
    H = sum(r.shape[0] for r in rows) + 10 * len(rows) + 26
    out = np.full((H, W, 3), 25, np.uint8)
    cv2.putText(out, "each row: [crop(with top ctx)] [best tpl] [2nd tpl]  | read/truth on crop",
                (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    yy = 24
    for r in rows:
        out[yy:yy + r.shape[0], :r.shape[1]] = r
        yy += r.shape[0] + 10
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cv2.imwrite(OUT, out)
    bad = sum(1 for i in range(len(rr.cards)) if i < len(zhi) and rr.cards[i][1] != zhi[i])
    print(f"✓ {OUT} | 读错 {bad}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
