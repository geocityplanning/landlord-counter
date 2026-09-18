#!/usr/bin/env python3
"""掼蛋**按张数标定位置**(2026-09-18 用户定方向)。

用户原话: "27,26,25 剩余数量不同, 牌的位置不同, 我们现在不需要考虑很多问题, 每种情况量准位置"

做法: 对每个张数 n, **实测**这一排每张牌的左缘(用竖直边界峰, 不是推导公式 ✓),
      与真值张数交叉校验(峰数==n 且间距规整) ⇒ 合格才写进 slots_by_n[n] ✓
      不合格 ⇒ **不写**(坏的标定比没有更糟 ✗)

用法:
  PYTHONPATH=src python3 tools/calibrate_by_n.py            # 只量当前这一档
  PYTHONPATH=src python3 tools/calibrate_by_n.py --sweep    # 量完打掉一张, 继续量下一档(边打边扫)
  PYTHONPATH=src python3 tools/calibrate_by_n.py --show     # 打印已标定的表
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import geometry as G          # noqa: E402
from landlord_counter.guandan import locate as L            # noqa: E402
from landlord_counter.guandan import percept as P           # noqa: E402
from landlord_counter.platform.cdp import CDP               # noqa: E402
from landlord_counter.platform.device import AdbDevice      # noqa: E402
from landlord_counter.platform.maatouch import MaaTouch     # noqa: E402


def wait_static(dev, tol=1.5, timeout=6.0):
    prev = dev.snap()
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.15)
        cur = dev.snap()
        if prev is not None and cur is not None and prev.shape == cur.shape:
            if float(np.abs(cur.astype("int16") - prev.astype("int16")).mean()) <= tol:
                return cur
        prev = cur
    return prev


LAST_W = 88          # 末张完整宽度(源码布局常量 ✓)
SHOT_DIR = "data/calib/shots"      # 每档截图存档(供以后复核 ✓; 不进仓库 ✗)


def measure_row(img, n_truth: int, geom: G.GuandanGeom):
    """实测这一排的**真实左缘序列**(峰) —— 不是推导 ✓

    返回 (slots, ok, note): ok=False 时 slots 不可信(调用方不许写表 ✓)
    """
    y0, y1 = geom.hand_y0, geom.hand_y1
    peaks = [int(x) for x in P.card_edges(img, y0, y1)]
    if not peaks:
        return [], False, "没检测到任何边界峰"
    gaps = np.diff(peaks)
    good = gaps[(gaps >= 18) & (gaps <= 32)]
    pitch = float(np.median(good)) if len(good) else float(geom.pitch)
    # 取"最长等距串"当这一排(杂峰剔除 ✓)
    if len(peaks) >= 3:
        chain, best = [peaks[0]], [peaks[0]]
        for x in peaks[1:]:
            if abs((x - chain[-1]) - pitch) <= max(3.0, pitch * 0.18):
                chain.append(x)
            else:
                if len(chain) > len(best):
                    best = chain
                chain = [x]
        if len(chain) > len(best):
            best = chain
        peaks = best
    if len(peaks) != n_truth:
        return [], False, f"峰数 {len(peaks)} ≠ 真值 {n_truth}(不写表 ✗)"
    gg = np.diff(peaks)
    if len(gg) and (gg.min() < 18 or gg.max() > 32):
        return [], False, f"间距不规整(min {gg.min()}, max {gg.max()}) ✗"
    # ★★★ 关键修正(2026-09-18 由"点牌实验"反推出来):
    #   竖直边界峰测到的是每张牌的**右边界**(= 下一张牌的左缘) ✗
    #   证据: 点第0位→选中第1张 ✗, 点第13位→选中第12张 ✗, 而点**最后一位**→选中最后一位 ✓
    #         (最后一张没有后继 ⇒ 它的右边界不是牌间边界 ⇒ 对上了 ✓)
    #   ⇒ 真正的**左缘序列** = 每个峰左移一个牌距; 最后一张的左缘 = 右锚点(见下) ✓
    # 峰 = 牌的左缘(与"居中布局公式"互相印证: 26 张 ⇒ 首张 16 ✓ 实测也是 16 ✓)
    #   (2026-09-18 曾试过"峰=下一张左缘 ⇒ 整体减 24", 但那会得到 -8 这种越界值 ⇒ 已回退 ✗)
    lefts = [int(p) for p in peaks]
    return lefts, True, (f"峰 {len(peaks)} 个 → 左缘 {lefts[:3]}…{lefts[-1]}, 间距中位 {pitch:.1f}")


def save_shot(img, slots, n_truth: int, ok: bool, note: str = "") -> str:
    """**存档每档的截图** ✓(用户 2026-09-18 要求: "方便以后复核")

    内容: 上=整帧(带牌位竖线 + 编号), 下=手牌带放大 2 倍(能看清每张牌是什么) ✓
    路径: data/calib/shots/n{张数}.png —— **不进仓库**(牌局画面属敏感数据, 公开仓不可入库 ✗)
    """
    import cv2 as _cv

    os.makedirs(SHOT_DIR, exist_ok=True)
    y0, y1 = 790, 950                                  # 手牌及周边(含上方干扰区, 便于复核 ✓)
    full = img.copy()
    for i, x in enumerate(slots):
        x0 = int(x)
        _cv.line(full, (x0, y0), (x0, y1), (0, 255, 0), 1)
        _cv.putText(full, str(i), (x0, y0 - 4), _cv.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    band = img[y0 - 25:y1]
    band = _cv.resize(band, (band.shape[1] * 2, band.shape[0] * 2), interpolation=_cv.INTER_NEAREST)
    for i, x in enumerate(slots):
        xb = int(x) * 2
        _cv.line(band, (xb, 0), (xb, band.shape[0]), (0, 255, 0), 1)
        _cv.putText(band, str(i), (xb + 2, 14), _cv.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
    tag = f"{n_truth} 张  实测 {len(slots)} 位  {'✓ 合格' if ok else '✗ 不合格'}"
    _cv.putText(band, tag, (4, band.shape[0] - 6), _cv.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 255, 0) if ok else (0, 0, 255), 1)
    W = max(full.shape[1], band.shape[1])
    out = np.full((full.shape[0] + band.shape[0] + 8, W, 3), 20, np.uint8)
    out[:full.shape[0], :full.shape[1]] = full
    out[full.shape[0] + 8:, :band.shape[1]] = band
    # ★ 合格才叫 n{张数}.png(**绝不覆盖**已有的合格存档 ✓);
    #   不合格的另存 n{张数}_fail_{时间}.png —— 留证但不冒充合格存档 ✓
    #   (2026-09-18: 曾把合格的 n27.png 覆盖成失败帧 ✗ ⇒ 改成这样)
    if ok:
        p = os.path.join(SHOT_DIR, f"n{n_truth}.png")
    else:
        p = os.path.join(SHOT_DIR, f"n{n_truth}_fail_{time.strftime('%m%d_%H%M%S')}.png")
    _cv.imwrite(p, out)
    return p


def main() -> int:
    geom = L.geom()
    if "--show" in sys.argv:
        tbl = {k: v for k, v in (geom.slots_by_n or {}).items()}
        print(f"已标定 {len(tbl)} 档: ")
        for k in sorted(tbl, key=lambda s: -int(s)):
            v = tbl[k]
            print(f"  {k} 张: {len(v)} 位  {v[:4]} … {v[-2:]}")
        return 0

    sweep = "--sweep" in sys.argv
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    c = CDP()
    c.find_truth()
    mt = MaaTouch("127.0.0.1:5555")
    mt.start()

    for step in range(6 if sweep else 1):
        # 等"我的回合 + 干净"
        t = {}
        for _ in range(30):
            t = c.truth() or {}
            if t.get("phase") == "playing" and t.get("current") == 0 and not (t.get("selected") or []):
                break
            time.sleep(3)
        if (t.get("selected") or []):
            print("✗ 牌桌有选中 ⇒ 先复位")
            return 1
        truth = sorted((int(x) for x in ((t.get("hands") or {}).get("0") or [])), reverse=True)
        n = len(truth)
        img = wait_static(dev)
        slots, ok, note = measure_row(img, n, geom)
        print(f"[{n} 张] {note}")
        shot = save_shot(img, slots if slots else [], n, ok)     # ★ 每档存档 ✓
        print(f"  ✓ 截图存档: {shot}")
        if ok:
            geom.slots_by_n[str(n)] = slots
            G.save(geom)
            print(f"  ✓ 已写入 slots_by_n[{n}] = {slots[:4]} … {slots[-2:]}")
            # 与"右锚点推导"对比, 让偏差一眼可见 ✓
            x_hi = slots[-1] + geom.last_card_w
            formula = geom.slots_from_right(n, x_hi - geom.last_card_w)
            diff = [int(a) - int(b) for a, b in zip(slots, formula)]
            print(f"  (实测 − 推导 的偏差: {diff[:6]} … 中位 {int(np.median(diff))})")
        else:
            print("  ✗ 不写表")
        if not sweep:
            break
        # 打掉最右那张单牌(合法的单张 ⇒ 张数 −1 ⇒ 量下一档 ✓)
        if not ok:
            print("  (本档没量准 ⇒ 停止扫)")
            break
        x = slots[-1]
        import numpy as _np
        del _np

        # ★ 点击 = 牌位 + 6px(2026-09-18 实测): 点在牌的**左缘**上 ⇒ 游戏判给左边那张 ✗
        mt.tap(int(x) + 6, geom.hand_y())
        time.sleep(0.5)
        # 按出牌按钮(实测最亮那段)
        pb = L.play_button(dev.snap())
        if not pb:
            print("  (找不到出牌按钮 ⇒ 停止扫)")
            break
        mt.tap(pb[0], pb[1])
        time.sleep(2.0)
        t2 = c.truth() or {}
        n2 = len((t2.get("hands") or {}).get("0") or [])
        print(f"  → 出牌后 {n2} 张" + (" ✓" if n2 < n else " ✗ 没打出去, 停"))
        if n2 >= n:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
