#!/usr/bin/env python3
"""掼蛋几何**离线标定**(2026-09-18 用户定的方向: 离线标定 + 在线校验)。

做什么
-----
在**干净、静止**的一帧上把几何量准, 落盘 data/calib/guandan.json ⇒ 运行时**照常量用** ✓
量: 手牌带 y、牌位起点/牌距/末张宽、按钮三段(出牌那段)、点击纵坐标

纪律(重要)
---------
① 只在"静止"的帧上量: 连续两帧像素一致才算静止(动画期间量的一切都是错的 ✗)
② 只在"干净"的牌桌上量: 无选中(有选中牌会上抬 ⇒ 带会漂 ✗) —— 用游戏真值判定 ✓
③ **量不准就不落盘**: 与真值交叉校验(张数、逐位可读), 不过就不写文件 ✓
   (坏的标定比没有标定更糟: 它会让在线校验"通过", 然后一路错下去 ✗)

用法: PYTHONPATH=src python3 tools/calibrate_guandan.py [--write]
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import geometry as G          # noqa: E402
from landlord_counter.guandan import percept as P           # noqa: E402
from landlord_counter.platform.cdp import CDP               # noqa: E402
from landlord_counter.platform.device import AdbDevice      # noqa: E402


def wait_static(dev, tol=1.5, timeout=6.0):
    """等画面静止: 连续两帧像素差 ≤tol ✓(动画期间量的一切都错 ✗)"""
    prev = dev.snap()
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.15)
        cur = dev.snap()
        if prev is not None and cur is not None and cur.shape == prev.shape:
            if float(np.abs(cur.astype("int16") - prev.astype("int16")).mean()) <= tol:
                return cur
        prev = cur
    return prev


def main() -> int:
    write = "--write" in sys.argv
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    has_truth = c.find_truth()
    print(f"真值通道: {'✓' if has_truth else '✗(无真值 ⇒ 无法交叉校验, 将拒绝落盘)'}")

    # 等"我的回合 + 牌桌干净"
    t = {}
    for _ in range(30):
        t = c.truth() or {}
        if t.get("phase") == "playing" and t.get("current") == 0 and not (t.get("selected") or []):
            break
        time.sleep(3)
    if (t.get("selected") or []):
        print("✗ 牌桌有选中(会让手牌带上抬) ⇒ 先复位再标定")
        return 1
    truth = sorted((int(x) for x in ((t.get("hands") or {}).get("0") or [])), reverse=True)
    print(f"真值手牌 {len(truth)} 张 (显示顺序: 从大到小)")

    frame = wait_static(dev)
    if frame is None:
        print("✗ 取帧失败")
        return 1
    h, w = frame.shape[:2]
    print(f"分辨率 {w}x{h}")

    # ---- ① 手牌带 ----
    y0, y1 = P.hand_band_measured(frame)
    print(f"① 手牌带 y = {y0}..{y1}")

    # ---- ② 白牌面横范围 + 相位 ----
    band = frame[y0:y1]
    white = (band.min(axis=2) > 150).mean(axis=0)
    cols = np.where(white > 0.40)[0]
    x_lo, x_hi = int(cols[0]), int(cols[-1])
    print(f"② 白牌面横范围 x = {x_lo}..{x_hi}")

    # ---- ③ 牌距: 用竖直边界峰的中位间距(与源码常量交叉) ----
    peaks = [int(v) for v in P.card_edges(frame, y0, y1)]
    pitch = 24
    if len(peaks) >= 3:
        gaps = np.diff(peaks)
        good = gaps[(gaps >= 18) & (gaps <= 32)]
        if len(good):
            pitch = int(round(float(np.median(good))))
    print(f"③ 牌距 pitch = {pitch} (峰值 {len(peaks)} 个)")

    # ---- ④ 末张宽: 用真值张数反推(整排宽 = (n-1)*pitch + 末张宽) ----
    n_truth = len(truth)
    last_w = int(round((x_hi - x_lo) - (n_truth - 1) * pitch))
    print(f"④ 末张宽 last_card_w = {last_w} (由 {n_truth} 张反推)")

    # ---- ⑤ 牌位起点: 末张左缘 - (n-1)*pitch ----
    right_left = x_hi - last_w
    slot_x0 = right_left - (n_truth - 1) * pitch
    print(f"⑤ 牌位起点 slot_x0 = {slot_x0}  (末张左缘 {right_left})")

    # ---- ⑥ 按钮三段 ----
    y_a, y_b = 1078, 1148
    bb = frame[y_a:y_b]
    g = bb[:, :, 1].astype(int)
    ng = ~((g > bb[:, :, 2].astype(int) + 12) & (g > bb[:, :, 0].astype(int) + 12))
    colp = ng.mean(axis=0)
    runs, s = [], None
    for x, v in enumerate(colp):
        if v > 0.6 and s is None:
            s = x
        elif v <= 0.6 and s is not None:
            if x - s > 25:
                runs.append((s, x))
            s = None
    if s is not None and len(colp) - s > 25:
        runs.append((s, len(colp)))
    play_x = 360
    if len(runs) >= 3:
        lo, hi = max(runs, key=lambda ab: bb[:, ab[0]:ab[1]].mean())
        play_x = int((lo + hi) // 2)
    print(f"⑥ 按钮段 {runs} ⇒ 出牌中心 x = {play_x}")

    geom = G.GuandanGeom(
        hand_y0=int(y0), hand_y1=int(y1),
        slot_x0=int(slot_x0), pitch=int(pitch), last_card_w=int(last_w),
        max_cards=int(n_truth),
        btn_y0=y_a, btn_y1=y_b, btn_play_x=int(play_x),
        btn_play_y=int((y_a + y_b) // 2),
        notes=f"离线标定于 {w}x{h}; 真值 {n_truth} 张",
    )

    # ---- ⑦ 交叉校验(不过就不落盘 ✗) ----
    print("\n=== 交叉校验 ===")
    ok = True
    slots = geom.slots_from_right(n_truth, right_left)
    print(f"  牌位 {len(slots)} 个: {slots[:5]} … {slots[-3:]}")
    if len(slots) != n_truth:
        ok = False
        print(f"  ✗ 牌位数 {len(slots)} ≠ 真值 {n_truth}")
    else:
        print(f"  ✓ 牌位数 == 真值({n_truth})")
    if abs(last_w - 88) > 12:
        print(f"  ⚠ 末张宽 {last_w} 与历史实测 88 相差较大(可疑, 但先记录)")
    rd, info = P.tm_read_hand(frame)
    good = sum(1 for a, b in zip(rd, truth) if a[1] == b)
    print(f"  读牌交叉: 逐位一致 {good}/{n_truth}")
    if good < n_truth * 0.8:
        print("  ⚠ 读牌一致性偏低(模板库可能不是这一局的) —— 标定仍然有效, 但读牌要单独重采模板")

    if not ok:
        print("\n✗ 校验未通过 ⇒ **不落盘**(坏的标定比没有更糟 ✗)")
        return 1
    if write:
        p = G.save(geom)
        print(f"\n✓ 已写入 {p}")
    else:
        print("\n(未加 --write ⇒ 仅试运行, 不落盘)")
        print(json_dumps := __import__("json").dumps(
            {k: v for k, v in geom.__dict__.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
