#!/usr/bin/env python3
"""用**游戏真值当老师**, 在**实时帧**上自动采集"点数"模板(同源, 无格式差)。

原理: 真值给四家手牌(点数), 我读到的牌位(左→右)也是从大到小排 → 按顺序一一配对
      → 每张牌的竖条存入模板库(key = 0_<点数>, 0 表示花色未知 → 只用于**认点数**)。

花色仍需单独确定(红/黑用颜色 ✓, 同套内部靠用户确认/聚类 ✓) → 因此点数与花色分两级:
  第一级: 认点数(本脚本采集, 用于打牌合法性/记牌器)  ✓
  第二级: 认花色(同花顺/逢人配才需要)            ✓

用法: PYTHONPATH=src python3 tools/tm_collect_live.py [样本数=12] [间隔秒=2]
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from landlord_counter.guandan import percept as P          # noqa: E402
from landlord_counter.platform.cdp import CDP              # noqa: E402
from landlord_counter.platform.device import AdbDevice     # noqa: E402

OUT = "data/templates_rank"   # 点数级(实时真值采集)
NAME = {11: "J", 12: "Q", 13: "K", 14: "A", 15: "小王", 16: "大王"}


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    c = CDP()
    if not c.find_truth():
        print("没有真值钩子")
        return 2
    dev = AdbDevice(serial="127.0.0.1:5555", url="http://172.18.0.1:8123/index.html")
    os.makedirs(OUT, exist_ok=True)   # 追加式: 不清空(与花色级分目录)
    got = 0
    seen = {}
    for _ in range(n * 4):
        if got >= n:
            break
        t1 = c.truth()
        img = dev.snap()
        t2 = c.truth()
        if not t1 or t1.get("phase") != "playing":
            time.sleep(gap)
            continue
        h1 = t1.get("hands", {}).get("0")
        if not h1 or h1 != t2.get("hands", {}).get("0"):
            time.sleep(gap)
            continue
        # ★★ 硬条件(2026-09-17): 必须"没有任何牌被选中(抬起)"才采 —— 否则采到的是抬起态样本 ✗
        if (t1.get("selected") or []) or (t2.get("selected") or []):
            time.sleep(gap)
            continue
        truth = sorted((int(x) for x in h1), reverse=True)      # 从大到小 = 显示顺序
        y0, y1 = P.hand_band_measured(img)
        xs = P.card_slots(img, y0, y1)
        if len(xs) != len(truth):
            print(f"  跳过: 牌位 {len(xs)} 个 vs 真值 {len(truth)} 张")
            time.sleep(gap)
            continue
        got += 1
        card_h = y1 - y0 - 16
        # ★ 跳过"当前正被选中(抬起)"的牌(2026-09-17): 抬起状态的竖条若被当作"放平"存进模板库,
        #   那张牌的偏移会永远停在 -25 → 之后被判成"一直抬起" ✗(实测 x=172 就是这个误判)
        sel_ids = set(t1.get("selected") or [])
        for x, z in zip(xs, truth):
            x0 = int(x)
            # ★ 与读取端**同一口径**: 逐牌按自身顶边裁(游戏会把某些牌抬高显示 ✗
            #   若这里用固定带, 抬高的那几张会采到错位内容 → 读的时候永远对不上 ✗)
            ty = P.card_top_y(img, x0, y0 + 8)
            # 抬起代理: 该列上方 56px 内有成片白 → 当作"正抬起", 不采 ✓
            _win = img[max(0, y0 - 56):y0 - 4, x0:x0 + 24]
            if _win.size and (_win.min(axis=2) > 200).mean() > 0.35:
                continue
            patch = img[ty + 8:ty + 8 + card_h, x0:x0 + 24]
            if patch.size == 0 or float(patch.std()) < 10:
                continue
            seen[z] = seen.get(z, 0) + 1
            np.save(os.path.join(OUT, f"0_{z}_{got}_{x}.npy"), patch.astype(np.uint8))
        print(f"  样本 {got}: 采 {len(xs)} 张  点数 {[NAME.get(z, z) for z in truth]}")
        time.sleep(gap)
    print(f"✓ 共采 {got} 帧, 覆盖点数 {sorted(seen)}")
    P.clear_templates_cache()
    bank = P.load_templates_sr()
    print(f"  模板库现在 {len(bank)} 个 key, 其中点数级 {len([k for k in bank if k.startswith('0_')])} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
