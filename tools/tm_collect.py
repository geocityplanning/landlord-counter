#!/usr/bin/env python3
"""模板匹配读牌(实验台): 用真值当老师**自动采集**牌面模板, 再逐张比对。

为什么换掉 VLM:
    实测(2026-09-16) VLM 读手牌逐张只有 64~68% ✗, 且错的是**结构性**的:
    · 最左那张被"你"字框挡住 → 任何模型都读不到 ✗
    · 大小王渲染特殊 → 稳定读错 ✗
    而中间 7 张一直全对 ✓ → 说明牌面字形是稳定渲染的 → **模板比对**能到 99%+ ✓

做法(自监督):
    ① 同步取 (真值, 帧); 牌位用**卡边界实测**(不靠公式)
    ② 第 i 个牌位 ↔ 真值排序后的第 i 张 → 裁该牌的**左上角字形**存为该点数的样本
    ③ 每个点数取样本中位数 → 模板; 用真值交叉验证
输出: data/templates/<点数>.npy  + 一份混淆矩阵

用法: PYTHONPATH=src python3 tools/tm_collect.py [样本数=12]
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P                      # noqa: E402
from landlord_counter.platform.cdp import CDP                          # noqa: E402
from landlord_counter.platform.device import AdbDevice                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "data", "templates")
# 牌面字形在牌的左上角: 从牌的左缘往右 6px、牌顶往下 4px 起, 取一小块(够装下 10/A/王)
CORNER = (3, 3, 20, 34)     # dx, dy, w, h —— 牌重叠, 每张只露约 24px, 裁块必须更窄 ✗否则混进隔壁牌


def slots(img) -> list:
    """手牌各牌位的左缘坐标(卡边界实测)。"""
    y0, y1 = P.hand_band_measured(img)
    peaks = P.card_edges(img, y0, y1)
    return y0, y1, peaks


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    os.makedirs(TPL_DIR, exist_ok=True)
    c = CDP()
    if not c.find_truth():
        print("✗ 没有真值钩子")
        return 2
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    samples = defaultdict(list)
    got = 0
    for i in range(n * 3):
        if got >= n:
            break
        t1 = c.truth()
        f = dev.snap()
        t2 = c.truth()
        if not t1 or t1.get("phase") != "playing":
            time.sleep(1.5)
            continue
        if t1.get("hands", {}).get("0") != t2.get("hands", {}).get("0"):
            time.sleep(1.0)
            continue
        truth = sorted(int(x) for x in (t1.get("hands", {}).get("0") or []))
        if len(truth) < 3:
            continue
        y0, y1, peaks = slots(f)
        # 牌位: 每个峰=一张牌的左缘; 最后一张取到画面/牌区右界
        if len(peaks) < len(truth):
            # 峰少于真值张数: 用相邻间距外推补齐(实测牌距很稳)
            if len(peaks) >= 2:
                gap = float(np.median(np.diff(peaks)))
                while len(peaks) < len(truth):
                    peaks.append(int(peaks[-1] + gap))
            else:
                continue
        peaks = peaks[:len(truth)]
        dx, dy, w, h = CORNER
        for idx, z in enumerate(truth):
            x = peaks[idx] + dx
            y = y0 + dy
            patch = f[y:y + h, x:x + w]
            if patch.shape[:2] != (h, w):
                continue
            samples[z].append(patch.astype(np.float32))
        got += 1
        print(f"  样本 {got}: 手牌 {len(truth)} 张, 牌位 {len(peaks)} 个 → 采集 {len(truth)} 张字形")
        time.sleep(1.0)

    print()
    tpl = {}
    for z, arr in sorted(samples.items()):
        med = np.median(np.stack(arr), axis=0).astype(np.uint8)
        tpl[z] = med
        np.save(os.path.join(TPL_DIR, f"{z}.npy"), med)
        print(f"  点数 {z:<3} 模板 ✓ ({len(arr)} 个样本)")
    print(f"\n模板已存 {TPL_DIR}  (点数 {sorted(tpl)})")

    # 交叉验证: 用刚采的模板回读所有样本, 看能不能认对
    okk = tot = 0
    conf = Counter()
    for z, arr in samples.items():
        for a in arr:
            bestz, bestd = None, 1e18
            for tz, t in tpl.items():
                d = float(np.mean(np.abs(a - t.astype(np.float32))))
                if d < bestd:
                    bestd, bestz = d, tz
            tot += 1
            if bestz == z:
                okk += 1
            else:
                conf[(z, bestz)] += 1
    if tot:
        print(f"★ 模板自校验(回读训练样本): {okk}/{tot} = {okk / tot * 100:.1f}%")
        for (a, b), v in conf.most_common(6):
            print(f"    混淆: 真{a} → 认成{b} × {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
